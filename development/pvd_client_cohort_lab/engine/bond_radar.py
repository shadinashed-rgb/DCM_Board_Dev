#!/usr/bin/env python3
"""Offline CSV -> SQLite -> candidate signal evidence. Python 3.10+, stdlib only."""
import argparse
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import logging
from pathlib import Path
import re
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
# Signal catalogue after the DCM meeting decisions (rule version development-2):
# SIG03 is split into SIG03A (roll of an existing swap tied to maturing debt) and
# SIG03B (enquiry for a new pre-hedge swap); SIG07 rating advisory is sourced from
# CME call reports (not integrated). Context datasets are not signals.
SIGNALS = ('SIG01', 'SIG02', 'SIG03A', 'SIG03B', 'SIG04', 'SIG06', 'SIG07')
CONTEXTS = ('CTX_UTIL', 'CTX_CREDIT')
SOURCES = {
 'clo': dict(table='hive.clo_prod.clo_cda_contract_lvl', aliases=['clo.csv','clo_sample.csv'], date='run_date', format='compact', required=['run_date','source_system','mapping_system','hsbc_booking_legal_entity','sub_lim_id','rct_facility_ref','facility_id','obligor_cin','rct_mastergroup_id'], desired=['rct_gid','rct_mastergroup_name','local_product_type_lbs','facility_drawn_amount','facility_limit_amount','facility_currency','ag_acc_bal_drawn_sub_lim_usd']),
 'counterparty': dict(table='delta.prod_party_gda.counterparty_core', aliases=['counterparty.csv','counterparty_core.csv'], date='run_date', format='compact', required=['customer_relationship_cin_identifier','customer_relationship_gid_identifier','mastergroup_esr_identifier','customer_relationship_lifecycle_status_code','run_date'], desired=[]),
 'facilities': dict(table='delta.prod_credit_and_lending_gda.facilities_limits', aliases=['facilities.csv','facilities_limits_sample.csv'], date='run_date', format='compact', required=['run_date','facility_id'], desired=['cin','relationship_id','customer_id','source_system_name','country_code','facility_creation_date','product_code','limit_cat','limit_category_type','advised_ind']),
 'kyc': dict(table='delta.prod_party_gda.kyc', aliases=['kyc.csv','kyc_samples.csv'], date='run_date', format='compact', required=['run_date','cin','related_case_id'], desired=['review_purpose_code','review_purpose_desc','review_request_created_time_stamp','related_case_resolved_time','related_case_update_time']),
 'covenants': dict(table='delta.prod_credit_and_lending_gda.covenants', aliases=['covenants.csv','covenant_samples.csv'], date='run_date', format='compact', required=['run_date','facility_id','covenant_id','active_testing_id'], desired=['relationship_id','covenant_type','active_testing_actual_value','active_testing_final_value','active_testing_testing_threshold_value','active_testing_testing_threshold_operator','active_testing_approval_status','reporting_dt']),
 'drr': dict(table='delta.prod_credit_and_lending_mda.drr_facility_limits', aliases=['drr.csv','drr_facility_samples.csv'], date='reporting_date', format='compact', required=['reporting_date','facility_id'], desired=['run_date','cin','drr_mastergroup_id','approved_limit','utilisation','approved_limit_ccy','utilisation_ccy','source_system_name','rpt_facility_country_code']),
 'pvd': dict(table='hive.pvd_prod_wave.pvd_omnia_drr', aliases=['pvd.csv','omina_drr_samples.csv','omnia_drr_samples.csv'], date='joi_date', format='iso', required=['joi_date','joi_relationship_id'], desired=['joi_key','drr_utils','drr_act_limit','drr_carm_limit','drr_crr','drr_fac_category','joi_facility_category','etlmonth_drr','etlmonth'])
}

def norm(value):
    if value is None:
        return None
    value = re.sub(r'\s+', ' ', str(value)).strip().upper()
    return None if value in ('', 'NULL', 'NONE', '\\N') else value

def number(value):
    value = norm(value)
    if value is None:
        return None
    try:
        result = Decimal(value)
        return result if result.is_finite() else None
    except InvalidOperation:
        return None

def day(value):
    text = str(value or '').strip()
    try:
        if re.fullmatch(r'\d{8}', text):
            result = datetime.strptime(text, '%Y%m%d').date()
        else:
            result = date.fromisoformat(text[:10])
        return None if result.year in (1, 9999) else result.isoformat()
    except ValueError:
        return None

def digest(*items):
    return hashlib.sha256(json.dumps(items, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()

def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def ident(name):
    return '"' + str(name).replace('"', '""') + '"'

def dump(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')

def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)

def load_config(path):
    config = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if config['counterparty']['as_of_policy'] not in ('point_in_time', 'current_group'):
        raise ValueError('counterparty.as_of_policy must be point_in_time or current_group')
    if config['counterparty']['lookback_days'] < 0 or config['freshness_days'] < 0:
        raise ValueError('Lookback/freshness days must be nonnegative')
    if len(config['csv_delimiter']) != 1:
        raise ValueError('csv_delimiter must be one character')
    if not 0 <= config['utilisation']['threshold_percent'] <= 100:
        raise ValueError('Utilisation threshold must be between 0 and 100')
    sig01 = config['sig01']
    if sig01.get('missing_drawn_as_zero', False) not in (True, False) or type(sig01.get('missing_drawn_as_zero', False)) is not bool:
        raise ValueError('sig01.missing_drawn_as_zero must be a JSON boolean')
    materiality = sig01['materiality']
    if number(materiality['threshold_amount']) is None or number(materiality['threshold_amount']) < 0:
        raise ValueError('sig01.materiality.threshold_amount must be a nonnegative number')
    if not norm(materiality['threshold_currency']):
        raise ValueError('sig01.materiality.threshold_currency is required')
    for ccy, rate in materiality.get('fx_to_threshold_currency', {}).items():
        if number(rate) is None or number(rate) <= 0:
            raise ValueError(f'sig01 FX rate for {ccy} must be a positive number')
    if type(sig01.get('require_eligible_limit_category', True)) is not bool:
        raise ValueError('sig01.require_eligible_limit_category must be a JSON boolean')
    pressure = config['covenants'].get('pressure_headroom_turns')
    if pressure is not None and (number(pressure) is None or number(pressure) < 0):
        raise ValueError('covenants.pressure_headroom_turns must be nonnegative or null')
    if sig01['maximum_comparison_gap_days'] is not None and sig01['maximum_comparison_gap_days']<1:
        raise ValueError('maximum_comparison_gap_days must be positive or null')
    for name in ('sig02','sig04','covenants'):
        if config[name]['event_lookback_days']<0:raise ValueError(name+'.event_lookback_days must be nonnegative')
    flags=[config['identity']['cin_namespace_verified'],config['counterparty']['catalog_confirmed'],config['counterparty']['settings_verified'],config['counterparty']['allow_blank_status'],config['sig01']['definitions_verified'],config['sig02']['definitions_verified'],config['sig04']['definitions_verified'],config['covenants']['definitions_verified'],config['utilisation']['pvd']['grain_verified']]+[config['utilisation'][source]['definitions_verified'] for source in ('clo','drr','pvd')]
    if any(type(flag) is not bool for flag in flags):raise ValueError('Verification flags must be JSON true/false, not quoted strings')
    return config

class Lab:
    def __init__(self, connection, config, as_of):
        self.db, self.config, self.as_of = connection, config, as_of
        self.db.row_factory = sqlite3.Row
        self.db.create_function('norm', 1, norm, deterministic=True)
        self.db.create_function('day', 1, day, deterministic=True)
        self.issues = []
        self.manifests = []
        self.cp_cache = {}

    def issue(self, source, check, severity, count, detail):
        self.issues.append(dict(source=source, check=check, severity=severity, count=count, detail=detail))

    def prepare(self):
        self.db.executescript('''
        CREATE TABLE source_manifest(source TEXT, filename TEXT, sha256 TEXT, rows INTEGER, columns_json TEXT, metadata_json TEXT);
        CREATE TABLE quality_issues(source TEXT, check_name TEXT, severity TEXT, affected_count INTEGER, detail TEXT);
        CREATE TABLE column_profile(source TEXT, column_name TEXT, rows INTEGER, missing INTEGER);
        CREATE TABLE source_profile(source TEXT, raw_rows INTEGER, earliest_observation TEXT, latest_observation TEXT, invalid_dates INTEGER, after_assessment INTEGER, latest_lag_days INTEGER);
        CREATE TABLE identity_links(source TEXT, identifier_type TEXT, identifier_value TEXT, client_id TEXT, mastergroup_id TEXT, valid_from TEXT, valid_to TEXT, link_basis TEXT);
        CREATE INDEX identity_lookup ON identity_links(source,identifier_type,identifier_value);
        CREATE TABLE clo_enriched(raw_id INTEGER PRIMARY KEY, facility_key TEXT, observation_date TEXT, cin TEXT, gid TEXT, original_mastergroup TEXT, final_mastergroup TEXT, original_name TEXT, final_name_from_clo TEXT, match_status TEXT, match_rule TEXT, cin_candidates TEXT, gid_candidates TEXT, combined_candidates TEXT, cin_mapping_date TEXT, gid_mapping_date TEXT, mapping_policy TEXT, settings_verified INTEGER, client_id TEXT, identity_status TEXT);
        CREATE TABLE observations(source TEXT, record_key TEXT, observation_date TEXT, client_id TEXT, mastergroup_id TEXT, mapping_status TEXT, payload TEXT, raw_ids TEXT, PRIMARY KEY(source,record_key,observation_date));
        CREATE TABLE signal_evidence(evidence_id TEXT PRIMARY KEY, signal_id TEXT, component TEXT, source TEXT, record_key TEXT, client_id TEXT, mastergroup_id TEXT, event_date TEXT, observation_date TEXT, assessment_date TEXT, value TEXT, previous_value TEXT, denominator TEXT, currency TEXT, metric_name TEXT, triggered INTEGER, assessment_status TEXT, stale INTEGER, mapping_status TEXT, reason TEXT, source_rows TEXT, details_json TEXT, rule_version TEXT);
        CREATE INDEX signal_client_lookup ON signal_evidence(client_id,signal_id);
        CREATE TABLE signal_assessments(client_id TEXT, signal_id TEXT, assessment_date TEXT, status TEXT, evidence_count INTEGER, triggered_count INTEGER, latest_observation TEXT, PRIMARY KEY(client_id,signal_id));
        CREATE VIEW client_signal_summary AS SELECT client_id,signal_id,assessment_date,status,evidence_count,triggered_count,latest_observation FROM signal_assessments;
        CREATE VIEW group_signal_summary AS SELECT mastergroup_id,signal_id,component,assessment_date,mapping_status,COUNT(DISTINCT evidence_id) AS evidence_items,COUNT(DISTINCT client_id) AS linked_clients,SUM(CASE WHEN triggered=1 AND stale=0 THEN 1 ELSE 0 END) AS fresh_candidate_items,MAX(observation_date) AS latest_observation FROM signal_evidence WHERE mastergroup_id IS NOT NULL GROUP BY mastergroup_id,signal_id,component,assessment_date,mapping_status;
        CREATE TABLE evidence_lineage(evidence_id TEXT, source TEXT, raw_id INTEGER, input_file TEXT, csv_record INTEGER, raw_hash TEXT);
        ''')

    def input_files(self, input_dir, source):
        folder = input_dir/source
        chunks = sorted(folder.glob('*.csv')) if folder.exists() else []
        aliases = [input_dir/name for name in SOURCES[source]['aliases'] if (input_dir/name).exists()]
        if chunks and aliases or len(aliases) > 1:
            raise ValueError(f'{source}: use either its chunk folder OR one flat input filename; multiple input routes found')
        return chunks or aliases

    def ingest(self, input_dir):
        csv.field_size_limit(64*1024*1024)
        if not any(self.input_files(input_dir, source) for source in SOURCES):
            raise ValueError('No source CSV files found. Export data into the input directory, or run the synthetic demo first.')
        for source, spec in SOURCES.items():
            files = self.input_files(input_dir, source)
            header = None
            total = 0
            missing = {}
            if not files:
                columns = list(dict.fromkeys(spec['required']+spec['desired']))
                self.create_raw(source, columns)
                self.issue(source, 'input_missing', 'WARN', 1, 'No CSV supplied. Dependent signal assessments remain unavailable.')
                continue
            for path in files:
                initial_hash = file_hash(path)
                with path.open(encoding='utf-8-sig', newline='') as handle:
                    reader = csv.reader(handle, delimiter=self.config['csv_delimiter'])
                    first = next(reader, None)
                    if not first:
                        raise ValueError(f'{path.name}: missing CSV header')
                    columns = [s.strip().lower() for s in first]
                    if any(not c or c.startswith('__') for c in columns) or len(set(columns)) != len(columns):
                        raise ValueError(f'{path.name}: empty, duplicate or reserved __ column names')
                    if header is None:
                        header = columns
                        self.create_raw(source, columns)
                        absent = sorted(set(spec['required'])-set(columns))
                        if absent:
                            raise ValueError(f'{source}: required headers missing: {absent}. No existing run is overwritten.')
                        desired = sorted(set(spec['desired'])-set(columns))
                        if desired:
                            self.issue(source, 'candidate_columns_missing', 'WARN', len(desired), ', '.join(desired))
                        missing = {c:0 for c in columns}
                    elif columns != header:
                        raise ValueError(f'{source}: chunk header/schema drift at {path.name}')
                    count = 0
                    sql = 'INSERT INTO '+ident('raw_'+source)+' ('+','.join(ident(c) for c in columns+['__file','__line','__hash'])+') VALUES ('+','.join('?' for _ in range(len(columns)+3))+')'
                    buffer = []
                    for line_no, values in enumerate(reader, 2):
                        if len(values) != len(columns):
                            raise ValueError(f'{path.name}:{line_no}: expected {len(columns)} columns, received {len(values)}; check export delimiter/quoting')
                        for c,v in zip(columns,values):
                            missing[c] += norm(v) is None
                        buffer.append(values+[str(path.resolve()),line_no,digest(values)])
                        count += 1
                        if len(buffer)>=1000:
                            self.db.executemany(sql,buffer); buffer=[]
                    self.db.executemany(sql,buffer)
                total += count
                if file_hash(path) != initial_hash:
                    raise ValueError(f'{path.name} changed during import; repeat with a stable export')
                meta_path = path.with_suffix('.metadata.json')
                metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {'provenance_status':'metadata_sidecar_missing'}
                manifest = dict(source=source,filename=str(path.resolve()),sha256=initial_hash,rows=count,columns=columns,metadata=metadata)
                self.manifests.append(manifest)
                self.db.execute('INSERT INTO source_manifest VALUES (?,?,?,?,?,?)',(source,str(path.resolve()),manifest['sha256'],count,json.dumps(columns),json.dumps(metadata)))
                if not meta_path.exists():
                    self.issue(source,'extraction_metadata_missing','WARN',1,f'{path.name}: add a .metadata.json sidecar with query/parameters and coverage')
                if not count:
                    self.issue(source,'empty_export','WARN',1,f'{path.name} has headers and no rows; this does not establish absence of activity')
            self.db.executemany('INSERT INTO column_profile VALUES (?,?,?,?)',[(source,c,total,n) for c,n in missing.items()])
            duplicates = self.db.execute('SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) n FROM '+ident('raw_'+source)+' GROUP BY __hash HAVING COUNT(*)>1)').fetchone()[0]
            if duplicates:
                self.issue(source,'exact_duplicate_rows','WARN',duplicates,'Raw records retained; derived observations deduplicate repeated values.')
            self.issue(source,'input_loaded','INFO',total,f'{len(files)} file(s); {len(header)} columns; raw values preserved as text')
            date_field=ident(spec['date'])
            profile=self.db.execute(f'SELECT MIN(day({date_field})),MAX(day({date_field})),SUM(CASE WHEN day({date_field}) IS NULL THEN 1 ELSE 0 END),SUM(CASE WHEN day({date_field})>? THEN 1 ELSE 0 END) FROM '+ident('raw_'+source),(self.as_of,)).fetchone()
            earliest,latest,invalid,future=profile
            lag=(date.fromisoformat(self.as_of)-date.fromisoformat(latest)).days if latest else None
            self.db.execute('INSERT INTO source_profile VALUES (?,?,?,?,?,?,?)',(source,total,earliest,latest,invalid or 0,future or 0,lag))
            if lag is not None and lag>self.config['freshness_days']:
                self.issue(source,'source_latest_observation_stale','WARN',total,f'Latest observed date {latest}; lag {lag} days. This says nothing about unexported source records.')
            if invalid:self.issue(source,'invalid_source_dates','WARN',invalid,'Invalid/missing source dates, including sentinel dates, cannot support an as-of assessment.')
            if future:self.issue(source,'future_source_dates','WARN',future,'Dates after assessment are retained raw and excluded from relevant calculations.')
            numeric_fields={
                'clo':set([self.config['sig01']['drawn_field'],self.config['utilisation']['clo']['drawn_field'],self.config['utilisation']['clo']['limit_field']]),
                'drr':set([self.config['utilisation']['drr']['drawn_field'],self.config['utilisation']['drr']['limit_field']]),
                'pvd':set([self.config['utilisation']['pvd']['drawn_field'],self.config['utilisation']['pvd']['limit_field']]),
                'covenants':set([self.config['covenants']['value_field'],'active_testing_testing_threshold_value'])
            }.get(source,set())
            for column in numeric_fields & set(header):
                invalid_numbers=sum(1 for (value,) in self.db.execute('SELECT '+ident(column)+' FROM '+ident('raw_'+source)) if norm(value) is not None and number(value) is None)
                if invalid_numbers:self.issue(source,'invalid_numeric_values','WARN',invalid_numbers,column+': nonempty values could not be parsed as finite dot-decimal numbers; no locale/thousands conversion is assumed.')
        if not self.config['counterparty']['settings_verified']:
            self.issue('counterparty','prior_settings_unverified','WARN',1,'Lifecycle, lookback and sentinel settings are previous configuration to validate, not approved Bond Radar defaults.')
        if not self.config['counterparty']['catalog_confirmed']:
            self.issue('counterparty','catalog_unconfirmed','WARN',1,'delta.prod_party_gda.counterparty_core is a proposed location; local CSV processing does not verify it.')
        if not self.config['identity']['cin_namespace_verified']:
            self.issue('identity','cin_namespace_unverified','WARN',1,'CIN joins are provisional. Verify country/source scope or supply explicit source-scoped identity links.')
        self.db.commit()

    def create_raw(self, source, columns):
        self.db.execute('CREATE TABLE '+ident('raw_'+source)+' (__id INTEGER PRIMARY KEY,'+','.join(ident(c)+' TEXT' for c in columns)+',__file TEXT,__line INTEGER,__hash TEXT)')

    def load_links(self, path):
        if not path or not path.exists():
            return
        required=['source','identifier_type','identifier_value','client_id','mastergroup_id','valid_from','valid_to']
        with path.open(encoding='utf-8-sig',newline='') as handle:
            reader=csv.DictReader(handle)
            # Optional 8th column link_basis records where a link came from (e.g. a reviewed
            # approval vs. a Counterparty Core derived mapping); reviewed files omit it.
            if reader.fieldnames not in (required, required+['link_basis']):
                raise ValueError('identity_links.csv headers must be '+','.join(required)+'[,link_basis]')
            for row in reader:
                if row['source'] not in SOURCES and row['source'] != '*':
                    raise ValueError('Unknown identity link source: '+row['source'])
                if not norm(row['client_id']) or not norm(row['identifier_value']):
                    raise ValueError('Identity links require client_id and identifier_value')
                lo,hi=day(row['valid_from']),day(row['valid_to'])
                if row['valid_from'] and not lo or row['valid_to'] and not hi or lo and hi and lo>hi:
                    raise ValueError('Invalid identity link validity interval')
                self.db.execute('INSERT INTO identity_links VALUES (?,?,?,?,?,?,?,?)',(row['source'],norm(row['identifier_type']),norm(row['identifier_value']),norm(row['client_id']),norm(row['mastergroup_id']),lo,hi,(row.get('link_basis') or 'verified_link').strip()))

    def identity(self, source, pairs, when, fallback):
        matches=set();bases=set()
        for kind,value in pairs:
            if norm(value):
                for row in self.db.execute("SELECT client_id,mastergroup_id,link_basis FROM identity_links WHERE source IN (?, '*') AND identifier_type=? AND identifier_value=? AND (valid_from IS NULL OR valid_from<=?) AND (valid_to IS NULL OR valid_to>=?)",(source,kind,norm(value),when,when)):
                    matches.add((row[0],row[1]));bases.add(row[2] or 'verified_link')
        if len(matches)>1:
            return source+':UNRESOLVED:'+fallback,None,'ambiguous_identity_link'
        if matches:
            client,group=next(iter(matches))
            return client,group,'+'.join(sorted(bases))
        cin=next((norm(v) for k,v in pairs if k=='CIN' and norm(v)),None)
        if cin:
            return 'CIN:'+cin,None,'verified_cin' if self.config['identity']['cin_namespace_verified'] else 'provisional_cin'
        return source+':'+fallback,None,'source_scoped_only'

    def build_cp(self):
        self.db.executescript('''CREATE TABLE cp_lookup AS SELECT norm(customer_relationship_cin_identifier) cin,norm(customer_relationship_gid_identifier) gid,norm(mastergroup_esr_identifier) mg,norm(customer_relationship_lifecycle_status_code) status,day(run_date) observed FROM raw_counterparty; CREATE INDEX cp_cin ON cp_lookup(cin,observed); CREATE INDEX cp_gid ON cp_lookup(gid,observed);''')

    def cp_candidates(self, route, key, cutoff):
        if not key:
            return [],None
        cache=(route,key,cutoff)
        if cache in self.cp_cache:
            return self.cp_cache[cache]
        cfg=self.config['counterparty']
        lower=(date.fromisoformat(cutoff)-timedelta(days=cfg['lookback_days'])).isoformat()
        latest=self.db.execute(f'SELECT MAX(observed) FROM cp_lookup WHERE {route}=? AND observed BETWEEN ? AND ?',(key,lower,cutoff)).fetchone()[0]
        candidates=set()
        if latest:
            for row in self.db.execute(f'SELECT mg,status FROM cp_lookup WHERE {route}=? AND observed=?',(key,latest)):
                status_ok=row['status'] in cfg['active_statuses'] or row['status'] is None and cfg['allow_blank_status']
                if status_ok and row['mg'] and row['mg'] not in cfg['invalid_mastergroups']:
                    candidates.add(row['mg'])
        result=(sorted(candidates),latest)
        if len(self.cp_cache)>20000:
            self.cp_cache.clear()
        self.cp_cache[cache]=result
        return result

    def enrich_clo(self, row, key, observed):
        cfg=self.config['counterparty']
        cin,gid=norm(row.get('obligor_cin')),norm(row.get('rct_gid'))
        cutoff=observed if cfg['as_of_policy']=='point_in_time' else self.as_of
        c,cd=self.cp_candidates('cin',cin,cutoff)
        g,gd=self.cp_candidates('gid',gid,cutoff)
        combined=sorted(set(c+g))
        original=norm(row.get('rct_mastergroup_id'))
        valid=original and original not in cfg['invalid_mastergroups']
        if valid:
            final=original; status='source_conflict' if any(v!=original for v in combined) else 'original_preserved'; rule='clo_original'
        elif len(combined)==1:
            final=combined[0];status='matched_unique';rule='counterparty_cin_gid' if c and g else 'counterparty_cin' if c else 'counterparty_gid'
        else:
            final=None;status='ambiguous' if combined else 'unmatched';rule=None
        client,linked_group,identity=self.identity('clo',[('CIN',cin),('GID',gid)],observed,key)
        if linked_group and final and linked_group!=final:
            identity+=';group_link_conflict'
        self.db.execute('INSERT INTO clo_enriched VALUES ('+','.join('?' for _ in range(20))+')',(row['__id'],key,observed,cin,gid,original,final,row.get('rct_mastergroup_name'),row.get('rct_mastergroup_name') if valid else None,status,rule,json.dumps(c),json.dumps(g),json.dumps(combined),cd,gd,cfg['as_of_policy'],int(cfg['settings_verified']),client,identity))
        return client,final,status+';'+identity+('' if cfg['settings_verified'] else ';counterparty_settings_unvalidated')

    def key_for(self, source, row):
        if source=='clo':
            scope=[norm(row.get(c)) for c in ('source_system','mapping_system','hsbc_booking_legal_entity')]
            chosen=next(((c,norm(row.get(c))) for c in ('sub_lim_id','rct_facility_ref','facility_id') if norm(row.get(c))),None)
            # Null scope components are explicit parts of a candidate key, as in the
            # supplied SQL example. Retain them and qualify identity/uniqueness.
            return json.dumps(scope+list(chosen),separators=(',',':')) if chosen else None
        if source=='drr':
            # DRR UID is a candidate exposure key, not a cross-source facility ID.
            # Shared borrower associations may repeat it; amount conflicts are withheld.
            if norm(row.get('drr_uid')):
                return json.dumps([norm(row.get(c)) for c in ('source_system_name','rpt_facility_country_code')]+['DRR_UID',norm(row['drr_uid'])],separators=(',',':'))
            if re.fullmatch(r'[+-]?\d+(?:\.\d+)?E[+-]?\d+',norm(row.get('facility_id')) or ''):
                return None  # Rounded/scientific IDs cannot establish facility identity.
        fields={
            'facilities':['source_system_name','country_code','facility_id'],
            'kyc':['cin','related_case_id'],
            'covenants':['source_system_name','country_code','facility_id','covenant_id','active_testing_id'],
            'drr':['source_system_name','rpt_facility_country_code','facility_id'],
            'pvd':['joi_relationship_id','joi_key']
        }[source]
        required={'facilities':['facility_id'],'kyc':['cin','related_case_id'],'covenants':['facility_id','covenant_id','active_testing_id'],'drr':['facility_id'],'pvd':['joi_relationship_id']}[source]
        if any(not norm(row.get(c)) for c in required):
            return None
        return json.dumps([norm(row.get(c)) for c in fields],separators=(',',':'))

    def observations(self):
        self.build_cp()
        for source,spec in SOURCES.items():
            if source=='counterparty':
                continue
            # Disk sort by key/date; only one observation group is held in memory.
            self.db.execute('CREATE TEMP TABLE work(raw_id INTEGER, record_key TEXT, observed TEXT, payload TEXT)')
            bad_key=bad_date=future=partial_scope=0
            for raw in self.db.execute('SELECT * FROM '+ident('raw_'+source)):
                row=dict(raw);key=self.key_for(source,row);observed=day(row.get(spec['date']))
                # DRR reporting date is business time; run_date also must not be after assessment.
                load_dates=[day(row.get('run_date'))]
                if source=='pvd':load_dates += [day(row.get('etlmonth')),day(row.get('etlmonth_drr'))]
                if not key:bad_key+=1;continue
                if not observed:bad_date+=1;continue
                if observed>self.as_of or any(d and d>self.as_of for d in load_dates):future+=1;continue
                client=group=status=None
                if source=='clo':
                    client,group,status=self.enrich_clo(row,key,observed)
                    if any(not norm(row.get(c)) for c in ('source_system','mapping_system','hsbc_booking_legal_entity')):
                        partial_scope+=1;status+=';incomplete_source_scope'
                row.update(__client=client,__group=group,__mapping=status)
                self.db.execute('INSERT INTO work VALUES (?,?,?,?)',(row['__id'],key,observed,json.dumps(row)))
            for check,count in [('missing_scoped_key',bad_key),('invalid_observation_date',bad_date),('after_assessment_date',future)]:
                if count:self.issue(source,check,'WARN',count,'Raw records retained; excluded from derived evidence. Review source/date/key contract.')
            if partial_scope:self.issue(source,'incomplete_source_scope','WARN',partial_scope,'Candidate facility keys retain null source-scope components explicitly; key uniqueness remains unverified.')
            current=None;group_rows=[]
            for record in self.db.execute('SELECT * FROM work ORDER BY record_key,observed,raw_id'):
                key=(record['record_key'],record['observed'])
                if current is not None and key!=current:
                    self.collapse(source,current,group_rows);group_rows=[]
                current=key;group_rows.append(json.loads(record['payload']))
            if current is not None:self.collapse(source,current,group_rows)
            self.db.execute('DROP TABLE work')
        self.db.commit()
        self.db.execute('CREATE INDEX observation_client_lookup ON observations(client_id)')
        if self.db.execute('SELECT COUNT(*) FROM clo_enriched').fetchone()[0]:
            statuses=dict(self.db.execute('SELECT match_status,COUNT(*) FROM clo_enriched GROUP BY match_status'))
            for status,count in statuses.items():
                self.issue('counterparty','enrichment_'+status,'INFO' if status in ('matched_unique','original_preserved') else 'WARN',count,'Counts are raw borrower-association observations, not distinct clients or recovered facilities.')
        for source,count in self.db.execute("SELECT source,COUNT(*) FROM observations WHERE mapping_status LIKE '%source_scoped_only%' OR mapping_status LIKE '%provisional_cin%' OR mapping_status LIKE '%ambiguous_identity_link%' GROUP BY source"):
            self.issue(source,'identity_requires_validation','WARN',count,'Observations retain source-scoped, provisional or ambiguous client identities; inspect mapping_status before cross-source interpretation.')

    def collapse(self, source, key_date, rows):
        key,observed=key_date
        raw_ids=[r['__id'] for r in rows]
        # Ignore export provenance and borrower association fields when checking facility amounts.
        if source=='clo':
            significant=set(['local_product_type_lbs',self.config['sig01']['drawn_field'],self.config['sig01']['currency_field'],self.config['utilisation']['clo']['drawn_field'],self.config['utilisation']['clo']['limit_field'],self.config['utilisation']['clo']['currency_field']]+[a['field'] for a in self.config['sig01'].get('alternative_drawn_fields',[])])
            clients={r['__client'] for r in rows};groups={r['__group'] for r in rows if r['__group']}
            client=next(iter(clients)) if len(clients)==1 else 'clo:FACILITY:'+key
            group=next(iter(groups)) if len(groups)==1 and all(r['__group'] for r in rows) else None
            status=';'.join(sorted(set(r['__mapping'] for r in rows)))
            if len(clients)>1:status+=';multiple_borrowers_unallocated'
            if len(groups)>1:status+=';multiple_groups_unallocated'
        elif source=='drr' and norm(rows[0].get('drr_uid')):
            invalid=set(self.config['counterparty']['invalid_mastergroups'])
            groups={norm(r.get('drr_mastergroup_id')) for r in rows if norm(r.get('drr_mastergroup_id')) and norm(r.get('drr_mastergroup_id')) not in invalid}
            client='drr:EXPOSURE:'+key
            group=next(iter(groups)) if len(groups)==1 else None
            status='source_drr_uid_candidate;source_mastergroup_unverified'
            if len(groups)>1:status+=';multiple_groups_unallocated'
            # These are borrower-association/provenance columns, not extra limits.
            association={'gid','cin','drr_customer_uid','grid','drr_gid_uid','source_system_unique_id','guci','guci_sub','scuid','scuid_sub','groupguci','groupguci_sub','lescuid','lescuid_sub'}
            significant={c for c in rows[0] if not c.startswith('__') and c not in association}
            if len(rows)>1:status+=';borrower_associations_consolidated'
        else:
            pairs=[('CIN',rows[0].get('cin')),('RELATIONSHIP_ID',rows[0].get('relationship_id')),('CUSTOMER_ID',rows[0].get('customer_id'))]
            if source=='pvd':pairs=[('JOI_RELATIONSHIP_ID',rows[0].get('joi_relationship_id'))]
            client,group,status=self.identity(source,pairs,observed,key)
            if source=='drr' and norm(rows[0].get('drr_mastergroup_id')) and norm(rows[0].get('drr_mastergroup_id')) not in self.config['counterparty']['invalid_mastergroups']:
                source_group=norm(rows[0]['drr_mastergroup_id'])
                if group and group!=source_group:status+=';group_link_conflict';group=None
                else:group=source_group;status+=';source_mastergroup_unverified'
            significant=set(c for c in rows[0] if not c.startswith('__'))
        conflicting=sorted(c for c in significant if len({norm(r.get(c)) for r in rows if norm(r.get(c)) is not None})>1)
        payload={}
        for c in significant | {c for c in rows[0] if not c.startswith('__')}:
            values=[r.get(c) for r in rows if norm(r.get(c)) is not None]
            payload[c]=values[0] if values else None
        if conflicting:
            status+=';conflicting_observation'
            self.issue(source,'conflicting_observation','WARN',1,f'Key {key} date {observed}: conflicting fields '+','.join(conflicting)+'; metrics withheld')
            if source!='clo' and set(conflicting)&{'cin','relationship_id','customer_id','joi_relationship_id','drr_mastergroup_id'}:
                client=source+':UNRESOLVED:'+key;group=None;status+=';ambiguous_source_identity'
        payload['__conflicts']=conflicting
        payload['__borrower_clients']=sorted({r['__client'] for r in rows if r.get('__client')})
        self.db.execute('INSERT INTO observations VALUES (?,?,?,?,?,?,?,?)',(source,key,observed,client,group,status,json.dumps(payload),json.dumps(raw_ids)))

    def add_evidence(self, obs, signal, component, *, event=None, value=None, previous=None, denominator=None, currency=None, metric=None, triggered=None, status='needs_validation', reason='', details=None):
        observed=obs['observation_date']
        stale=int((date.fromisoformat(self.as_of)-date.fromisoformat(observed)).days>self.config['freshness_days'])
        eid=digest(signal,component,obs['source'],obs['record_key'],event or observed, self.config['rule_version'])
        values=(eid,signal,component,obs['source'],obs['record_key'],obs['client_id'],obs['mastergroup_id'],event,observed,self.as_of,None if value is None else str(value),None if previous is None else str(previous),None if denominator is None else str(denominator),currency,metric,None if triggered is None else int(triggered),status,stale,obs['mapping_status'],reason,obs['raw_ids'],json.dumps(details or {},default=str),self.config['rule_version'])
        # Event evidence is emitted from the latest observation, once per source event.
        self.db.execute('INSERT INTO signal_evidence VALUES ('+','.join('?' for _ in values)+')',values)
        for raw_id in json.loads(obs['raw_ids']):
            self.db.execute('INSERT INTO evidence_lineage SELECT ?,?,__id,__file,__line,__hash FROM '+ident('raw_'+obs['source'])+' WHERE __id=?',(eid,obs['source'],raw_id))

    def util(self, obs, payload, config):
        source=obs['source'];drawn=number(payload.get(config['drawn_field']));limit=number(payload.get(config['limit_field']))
        if source=='drr':
            currencies=[norm(payload.get(config['drawn_currency_field'])),norm(payload.get(config['limit_currency_field']))]
            currency=currencies[0] if all(currencies) and currencies[0]==currencies[1] else None
        elif source=='pvd':currency=norm(config['verified_currency'])
        else:currency=norm(payload.get(config['currency_field']))
        reason=[]
        if drawn is None:reason.append('missing_or_invalid_numerator')
        if limit is None or limit<=0:reason.append('missing_invalid_or_nonpositive_denominator')
        if drawn is not None and drawn<0:reason.append('negative_numerator')
        if not currency:reason.append('currency_missing_or_incompatible')
        if payload.get('__conflicts'):reason.append('conflicting_observation')
        value=drawn/limit*100 if not reason else None
        verified=config['definitions_verified'] and (source!='pvd' or config['grain_verified'])
        status='unavailable' if value is None else 'assessed' if verified else 'needs_validation'
        triggered=value>Decimal(str(self.config['utilisation']['threshold_percent'])) if value is not None and verified else None
        self.add_evidence(obs,'CTX_UTIL','utilisation',value=value,denominator=limit,currency=currency,metric='utilisation_percent',triggered=triggered,status=status,reason=';'.join(reason or (['definitions_unverified'] if not verified else [])),details={'numerator':drawn,'numerator_field':config['drawn_field'],'denominator_field':config['limit_field'],'threshold_percent':self.config['utilisation']['threshold_percent'],'threshold_exceeded_for_testing':value>Decimal(str(self.config['utilisation']['threshold_percent'])) if value is not None else None,'scope':'Source-specific measure; do not sum across overlapping sources.','qualification':'Utilisation is supporting context. It is not the SIG06 covenant-pressure definition (leverage within half a turn of the covenant maximum).'})

    def build_signals(self):
        latest='''SELECT * FROM (SELECT o.*,ROW_NUMBER() OVER(PARTITION BY source,record_key ORDER BY observation_date DESC) rn FROM observations o) WHERE rn=1 ORDER BY source,record_key'''
        # Newest snapshot per source and group, computed once (a per-row MAX scan is quadratic at portfolio scale).
        newest_by_group={(r[0],r[1]):r[2] for r in self.db.execute('SELECT source,mastergroup_id,MAX(observation_date) FROM observations GROUP BY source,mastergroup_id')}
        for obs in self.db.execute(latest):
            p=json.loads(obs['payload']);source=obs['source']
            if self.config.get('current_snapshot_only',False):
                newest=newest_by_group.get((source,obs['mastergroup_id']))
                if obs['observation_date']!=newest:continue
            if source=='clo':
                self.util(obs,p,self.config['utilisation']['clo'])
                self.drawing_change(obs,p)
            elif source=='drr' or source=='pvd':self.util(obs,p,self.config['utilisation'][source])
            if source=='facilities':self.facility_event(obs,p)
            if source=='kyc':self.kyc_event(obs,p)
            if source=='covenants':self.covenant(obs,p)
            if source in ('facilities','pvd'):
                fields=['limit_cat','limit_category_type','advised_ind','facility_grade_code','facility_grade_desc','sustainable_risk_rating_impact_proposed','sustainable_risk_rating_impact_approved'] if source=='facilities' else ['drr_crr','drr_fac_category','joi_facility_category']
                context={c:p.get(c) for c in fields}
                context.update(credit_category=p.get('limit_cat') if source=='facilities' else p.get('drr_fac_category'),category_meaning_verified=False)
                # Cat A is the SIG01 eligibility filter (meeting decision); rating advisory
                # comes from call reports, so this is credit context, not SIG07 evidence.
                self.add_evidence(obs,'CTX_CREDIT','facility_category_context',reason='Credit category and rating context; category definitions remain unverified.',details=context)
        clients=[r[0] for r in self.db.execute('SELECT DISTINCT client_id FROM observations')]
        for client in clients:
            for signal in SIGNALS+CONTEXTS:
                stats=self.db.execute('SELECT COUNT(*),SUM(CASE WHEN triggered=1 AND stale=0 THEN 1 ELSE 0 END),SUM(CASE WHEN assessment_status="assessed" AND stale=0 THEN 1 ELSE 0 END),MAX(observation_date),SUM(CASE WHEN stale=0 THEN 1 ELSE 0 END),SUM(CASE WHEN assessment_status="needs_validation" AND stale=0 THEN 1 ELSE 0 END),SUM(CASE WHEN assessment_status="unavailable" AND stale=0 THEN 1 ELSE 0 END) FROM signal_evidence WHERE client_id=? AND signal_id=?',(client,signal)).fetchone()
                count,triggers,assessed,latest_date,fresh,pending,unavailable=stats
                state='unavailable' if not count else 'stale_evidence' if not fresh else 'candidate_trigger' if triggers else 'needs_validation' if pending else 'partial_assessment' if assessed and unavailable else 'assessed_no_trigger_in_supplied_records' if assessed else 'unavailable'
                self.db.execute('INSERT INTO signal_assessments VALUES (?,?,?,?,?,?,?)',(client,signal,self.as_of,state,count,triggers or 0,latest_date))
        for issue in self.issues:
            self.db.execute('INSERT INTO quality_issues VALUES (?,?,?,?,?)',(issue['source'],issue['check'],issue['severity'],issue['count'],issue['detail']))
        self.db.commit()

    def limit_category(self, p):
        """Cat A eligibility from Facilities limit_cat via a matching facility ID.

        CLO carries no limit category. The lookup uses observed equality of the CLO
        sub-limit/facility ID and the Facilities facility_id; it is a development
        link to validate, not an approved cross-source facility identity.
        """
        lookup=self.config['sig01']['limit_category_lookup']
        keys=[norm(p.get(c)) for c in lookup['clo_key_fields'] if norm(p.get(c))]
        if not keys:return None,'no_clo_facility_key',[]
        if not getattr(self,'_category_lookup_ready',False):
            # One indexed lookup table instead of a full scan per CLO observation (portfolio scale).
            self.db.execute('CREATE TEMP TABLE category_lookup AS SELECT DISTINCT norm('+ident(lookup['facility_field'])+') AS fid, norm('+ident(lookup['category_field'])+') AS cat FROM '+ident('raw_'+lookup['source']))
            self.db.execute('CREATE INDEX category_lookup_fid ON category_lookup(fid)');self._category_lookup_ready=True
        rows=self.db.execute('SELECT DISTINCT cat FROM category_lookup WHERE fid IN ('+','.join('?' for _ in keys)+')',keys).fetchall()
        values=sorted({r[0] for r in rows if r[0]})
        if not values:return None,'limit_category_unlinked',keys
        if len(values)>1:return None,'limit_category_conflicting',keys
        return values[0],'observed_facility_id_match_unverified',keys

    def materiality(self, delta, currency, p, imputed):
        """EUR 50m test on the drawing (HSBC share lower bound, then inferred total)."""
        m=self.config['sig01']['materiality'];threshold=Decimal(str(m['threshold_amount']));target=norm(m['threshold_currency'])
        out={'threshold_amount':threshold,'threshold_currency':target,'basis':m.get('basis','drawing_increase'),'drawing_in_threshold_currency':None,'hsbc_participation_share_percent':None,'inferred_total_drawing':None,'material_for_testing':None}
        if delta is None:out['materiality_status']='drawing_unavailable';return out
        if imputed:out['materiality_status']='imputed_values_not_assessable';return out
        if delta<=0:out.update(material_for_testing=False,materiality_status='no_drawing_increase');return out
        rate=Decimal(1) if currency==target else number(m.get('fx_to_threshold_currency',{}).get(currency or ''))
        if rate is None:out['materiality_status']='fx_rate_not_configured';return out
        converted=delta*rate;out['drawing_in_threshold_currency']=converted
        share=None
        if m.get('sole_lender_field') and norm(p.get(m['sole_lender_field']))=='Y':share=Decimal(100)
        elif m.get('participation_share_field'):
            value=number(p.get(m['participation_share_field']))
            share=value if value is not None and 0<value<=100 else None
        out['hsbc_participation_share_percent']=share
        if share:out['inferred_total_drawing']=converted*Decimal(100)/share
        # HSBC's share can never exceed the whole facility, so it is a valid lower bound.
        if converted>=threshold:out.update(material_for_testing=True,materiality_status='hsbc_share_meets_threshold')
        elif out['inferred_total_drawing'] is not None:
            material=out['inferred_total_drawing']>=threshold
            out.update(material_for_testing=material,materiality_status='inferred_total_meets_threshold' if material else 'inferred_total_below_threshold')
        else:out['materiality_status']='hsbc_share_below_threshold_participation_unknown'
        return out

    def drawing_change(self, obs, p):
        cfg=self.config['sig01']
        product=norm(p.get('local_product_type_lbs'))
        if product not in cfg['products']:
            return
        category,category_basis,category_keys=self.limit_category(p)
        measures=[dict(field=cfg['drawn_field'],currency_field=cfg['currency_field'],component='drawing_change',missing_as_zero=cfg.get('missing_drawn_as_zero',False))]
        measures+=[dict(field=a['field'],currency=a.get('currency'),currency_field=a.get('currency_field'),component=a['component'],missing_as_zero=False) for a in cfg.get('alternative_drawn_fields',[])]
        for measure in measures:
            self.drawing_measure(obs,p,cfg,measure,product,category,category_basis,category_keys)

    def drawing_measure(self, obs, p, cfg, measure, product, category, category_basis, category_keys):
        field=measure['field']
        currency_of=lambda payload:norm(measure['currency']) if measure.get('currency') else norm(payload.get(measure['currency_field']))
        previous=self.db.execute('SELECT * FROM observations WHERE source="clo" AND record_key=? AND observation_date<? ORDER BY observation_date DESC LIMIT 1',(obs['record_key'],obs['observation_date'])).fetchone()
        curr=number(p.get(field));currency=currency_of(p);old=None;gap=None;reason=[]
        current_imputed=measure['missing_as_zero'] and norm(p.get(field)) is None
        prior_imputed=False
        if current_imputed:curr=Decimal(0)
        if previous:
            old_p=json.loads(previous['payload']);old=number(old_p.get(field))
            prior_imputed=measure['missing_as_zero'] and norm(old_p.get(field)) is None
            if prior_imputed:old=Decimal(0)
            gap=(date.fromisoformat(obs['observation_date'])-date.fromisoformat(previous['observation_date'])).days
            if currency_of(old_p)!=currency:reason.append('comparison_currency_changed')
            if norm(old_p.get('local_product_type_lbs')) not in cfg['products']:reason.append('previous_product_not_eligible')
            if old_p.get('__conflicts'):reason.append('previous_observation_conflict')
        else:reason.append('no_prior_observation')
        if curr is None or old is None:reason.append('missing_or_invalid_drawn_amount')
        if not currency:reason.append('currency_missing')
        if p.get('__conflicts'):reason.append('current_observation_conflict')
        if cfg['maximum_comparison_gap_days'] is not None and gap is not None and gap>cfg['maximum_comparison_gap_days']:reason.append('comparison_gap_exceeds_setting')
        delta=curr-old if not reason else None
        imputed=current_imputed or prior_imputed
        mat=self.materiality(delta,currency,p,imputed)
        eligible=None if category is None else category in [norm(c) for c in cfg['eligible_limit_categories']]
        notes=[]
        if delta is not None:
            if mat['material_for_testing'] is None and mat['materiality_status'] not in ('imputed_values_not_assessable',):notes.append(mat['materiality_status'])
            if eligible is None:notes.append(category_basis)
            elif not eligible:notes.append('limit_category_not_eligible')
            if not cfg['definitions_verified']:notes.append('definitions_unverified')
            if imputed:notes.append('imputed_zero_drawn_values')
        determinable=delta is not None and mat['material_for_testing'] is not None and (eligible is not None or not cfg.get('require_eligible_limit_category',True))
        verified=cfg['definitions_verified']
        triggered=(bool(mat['material_for_testing']) and (eligible or not cfg.get('require_eligible_limit_category',True))) if determinable and verified else None
        status='unavailable' if delta is None else 'assessed' if determinable and verified else 'needs_validation'
        self.add_evidence(obs,'SIG01',measure['component'],value=delta,previous=old,currency=currency,metric='drawing_increase',triggered=triggered,status=status,reason=';'.join(reason or notes),details={'current_drawn':curr,'current_drawn_raw':p.get(field),'current_missing_imputed_zero':current_imputed,'previous_missing_imputed_zero':prior_imputed,'missing_drawn_policy':'zero_for_SIG01_only' if measure['missing_as_zero'] else 'unavailable','previous_observation_date':previous['observation_date'] if previous else None,'previous_source_rows':json.loads(previous['raw_ids']) if previous else [],'comparison_gap_days':gap,'drawn_field':field,'product':product,'eligible_products':cfg['products'],'limit_category':category,'limit_category_basis':category_basis,'limit_category_lookup_keys':category_keys,'cat_a_eligible':eligible,**mat,'definition':'Meeting decision: any drawing on any Cat A bank facility (RCF, term loan, bilateral) above EUR 50m is material; HSBC share and inferred total both considered.'})

    def facility_event(self, obs, p):
        """SIG02 event date is the internal credit approval date (meeting decision).

        Fields are tried in configured order. Facilities loan_approva_dt is a "0"
        placeholder in current exports, so facility_creation_date is retained as a
        candidate approval date and labelled as such. The Application Ratings
        approval date is attached downstream by alignment.py where a credit proposal
        serial number links the two sources.
        """
        cfg=self.config['sig02'];product=norm(p.get('product_code'));event=None;basis=None
        for candidate in cfg['event_fields']:
            value=day(p.get(candidate['field']))
            if value:event,basis=value,candidate['basis'];break
        valid=event and event<=obs['observation_date'] and not p.get('__conflicts')
        verified=cfg['definitions_verified'] and bool(cfg['qualifying_product_codes'])
        age=(date.fromisoformat(self.as_of)-date.fromisoformat(event)).days if event else None
        reason='missing_invalid_future_or_conflicting_event_date' if not valid else ';'.join(r for r in ['event_date_is_candidate_approval_date' if basis!='credit_approval_date' else '','event_and_product_meaning_unverified' if not verified else ''] if r)
        self.add_evidence(obs,'SIG02','facility_approval_event',event=event if valid else None,triggered=product in cfg['qualifying_product_codes'] and age<=cfg['event_lookback_days'] if valid and verified else None,status='unavailable' if not valid else 'assessed' if verified else 'needs_validation',reason=reason,details={'product_code':product,'event_basis':basis,'event_fields_tried':[c['field'] for c in cfg['event_fields']],'loan_approval_raw':p.get('loan_approva_dt'),'facility_creation_date':day(p.get('facility_creation_date')),'credit_proposal_serial_no':p.get('credit_proposal_serial_no'),'limit_category':p.get('limit_cat'),'event_age_days':age,'event_lookback_days':cfg['event_lookback_days'],'limit':p.get('proposed_limit'),'currency':p.get('facility_ccy'),'definition':'Meeting decision: bridge/new-facility date is the internal credit approval date, not the signing date.'})

    def kyc_event(self, obs, p):
        cfg=self.config['sig04'];event=day(p.get(cfg['event_field']));purpose=norm(p.get('review_purpose_code'))
        valid=event and event<=obs['observation_date'] and not p.get('__conflicts')
        verified=cfg['definitions_verified']
        age=(date.fromisoformat(self.as_of)-date.fromisoformat(event)).days if event else None
        self.add_evidence(obs,'SIG04','kyc_case',event=event if valid else None,triggered=purpose in cfg['review_purpose_codes'] and age<=cfg['event_lookback_days'] if valid and verified else None,status='unavailable' if not valid else 'assessed' if verified else 'needs_validation',reason='missing_invalid_future_or_conflicting_case_date' if not valid else 'purpose_and_event_meaning_unverified' if not verified else '',details={'purpose':purpose,'purpose_description':p.get('review_purpose_desc'),'case_status':p.get('related_case_status'),'resolved_time':p.get('related_case_resolved_time'),'event_field':cfg['event_field'],'event_age_days':age,'event_lookback_days':cfg['event_lookback_days'],'qualification':'A KYC case does not establish financing activity.'})

    def covenant(self, obs, p):
        cfg=self.config['covenants'];actual=number(p.get(cfg['value_field']));threshold=number(p.get('active_testing_testing_threshold_value'));operator=norm(p.get('active_testing_testing_threshold_operator'))
        financial=norm(p.get('covenant_type')) in cfg['financial_types'];approved=norm(p.get(cfg['approval_field'])) in cfg['approved_statuses'];reason=[]
        if not financial:reason.append('not_verified_financial_type')
        if actual is None or threshold is None:reason.append('missing_financial_value_or_threshold')
        if operator not in ('<','<=','>','>=','='):reason.append('unsupported_operator')
        if norm(p.get('active_testing_testing_threshold_value_2')) is not None:reason.append('second_threshold_requires_separate_rule')
        if p.get('__conflicts'):reason.append('conflicting_observation')
        event=day(p.get(cfg['event_field']))
        if not event:reason.append('missing_or_invalid_financial_test_date')
        elif event>obs['observation_date']:reason.append('financial_test_date_after_observation')
        elif (date.fromisoformat(self.as_of)-date.fromisoformat(event)).days>cfg['event_lookback_days']:reason.append('financial_test_outside_development_event_window')
        # Threshold operator describes the compliance condition, to be confirmed by source owner.
        comparison={'<':lambda a,b:a<b,'<=':lambda a,b:a<=b,'>':lambda a,b:a>b,'>=':lambda a,b:a>=b,'=':lambda a,b:a==b}
        evaluable=not reason and approved and cfg['definitions_verified']
        breached=not comparison[operator](actual,threshold) if evaluable else None
        # Meeting decision: pressure = leverage within half a turn of a maximum covenant
        # (e.g. >= 2.5x against a 3.0x maximum). Applies to maximum-type operators only.
        headroom=threshold-actual if not reason and operator in ('<','<=') else None
        turns=Decimal(str(cfg['pressure_headroom_turns'])) if cfg.get('pressure_headroom_turns') is not None else None
        pressure=headroom is not None and turns is not None and headroom<=turns
        triggered=(breached or pressure) if evaluable else None
        self.add_evidence(obs,'SIG06','financial_covenant',event=event,value=actual,denominator=threshold,metric='financial_covenant_test',triggered=triggered,status='unavailable' if reason else 'assessed' if evaluable else 'needs_validation',reason=';'.join(reason or ([] if evaluable else ['approval_units_and_operator_semantics_unverified'])),details={'operator':operator,'covenant_type':p.get('covenant_type'),'reported_status':p.get('covenant_status'),'approval_status':p.get(cfg['approval_field']),'testing_id':p.get('active_testing_id'),'event_field':cfg['event_field'],'event_lookback_days':cfg['event_lookback_days'],'qualification':'Overdue non-financial reporting is not a financial breach.','headroom_turns':headroom,'pressure_headroom_turns':turns,'pressure_for_testing':pressure if headroom is not None else None,'breach_for_testing':(not comparison[operator](actual,threshold)) if not reason else None})

    def export(self, output):
        for table in ('source_manifest','source_profile','quality_issues','column_profile','clo_enriched','observations','signal_evidence','evidence_lineage','client_signal_summary','group_signal_summary'):
            cursor=self.db.execute('SELECT * FROM '+ident(table))
            write_csv(output/'exports'/(table+'.csv'),[d[0] for d in cursor.description],cursor)
        counts={table:self.db.execute('SELECT COUNT(*) FROM '+ident(table)).fetchone()[0] for table in ('clo_enriched','observations','signal_evidence','signal_assessments')}
        cpcounts=dict(self.db.execute('SELECT match_status,COUNT(*) FROM clo_enriched GROUP BY match_status'))
        report={'assessment_date':self.as_of,'counts':counts,'counterparty_match_status_counts':cpcounts,'inputs':self.manifests,'issues':self.issues,'limitations':['Development evidence, not production alerts.','No supplied CSV establishes source-wide completeness.','SIG03A/SIG03B derivatives sources absent; SIG07 rating advisory requires CME call reports (not integrated).','Cross-source monetary totals are not computed.','Group names are not populated from Counterparty IDs.']}
        dump(output/'validation.json',json.dumps(report,indent=2,default=str))
        lines=['# Local Bond Radar test results','',f'Assessment date: {self.as_of}','','Development/test outputs. Business definitions and mappings remain subject to the recorded qualifications.','','## Run outputs','',*[f'- {k}: {v}' for k,v in counts.items()],'','## Quality checks','','| Source | Check | Level | Count | Interpretation |','| --- | --- | --- | --- | --- |']
        lines += [f"| {i['source']} | {i['check']} | {i['severity']} | {i['count']} | {i['detail'].replace('|','/')} |" for i in self.issues]
        lines += ['','## How to interpret the results','','- `signal_evidence`: metrics and context, with source-row references and qualifications. `triggered` stays blank until applicable definitions/settings are verified.','- `client_signal_summary`: all six signals per observed client identity. No-evidence means unavailable. An assessed no-trigger result only describes supplied records.','- `clo_enriched`: one record per accepted raw CLO association, including both identifier routes and mapping dates.','- `group_signal_summary`: counts of evidence only; no monetary totals across sources. Unverified and ambiguous mappings need review.','- `stale`: observation lag exceeds the configurable development freshness setting; inspect event dates separately.','- `raw_*`: original CSV values as text. `__id` connects derived lineage to source file and CSV line.','','## Limits','','No live SQL was executed by the local process. Daily coverage, approved production definitions, financial units, facility equivalence and full client mappings are not established by a successful run.']
        dump(output/'REPORT.md','\n'.join(lines)+'\n')

def run(input_dir, output, config_path, as_of, links=None):
    config=load_config(config_path)
    as_of=day(as_of)
    if not as_of:raise ValueError('Use an explicit valid --as-of date (YYYY-MM-DD)')
    input_dir=Path(input_dir).resolve();output=Path(output).resolve()
    if not input_dir.is_dir():raise ValueError('Input directory does not exist: '+str(input_dir))
    if links and not Path(links).is_file():raise ValueError('Explicit --links file does not exist: '+str(links))
    if output.exists():raise ValueError('Output already exists; choose a new run directory: '+str(output))
    if output==input_dir or input_dir in output.parents:raise ValueError('Output must be outside the input directory')
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix='.'+output.name+'-',dir=output.parent))
    db=None
    log_handler=logging.FileHandler(temporary/'run.log',encoding='utf-8')
    log_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logging.getLogger().addHandler(log_handler)
    try:
        logging.info('Loading CSV inputs into an isolated SQLite run')
        db=sqlite3.connect(temporary/'bond_radar.sqlite')
        lab=Lab(db,config,as_of);lab.prepare();lab.ingest(input_dir);lab.load_links(Path(links) if links else input_dir/'identity_links.csv');lab.observations();lab.build_signals();lab.export(temporary)
        integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity!='ok':raise RuntimeError('SQLite integrity check: '+integrity)
        expected=db.execute('SELECT COUNT(*) FROM raw_clo WHERE day(run_date) IS NOT NULL AND day(run_date)<=?',(as_of,)).fetchone()[0]
        actual=db.execute('SELECT COUNT(*) FROM clo_enriched').fetchone()[0]
        if actual>expected:raise RuntimeError('CLO enrichment multiplied rows')
        dump(temporary/'config_used.json',json.dumps(config,indent=2))
        dump(temporary/'run_manifest.json',json.dumps({'assessment_date':as_of,'created_utc':datetime.now(timezone.utc).isoformat(),'config_sha256':file_hash(Path(config_path)),'program_sha256':file_hash(Path(__file__)),'identity_links_sha256':file_hash(Path(links) if links else input_dir/'identity_links.csv') if (Path(links) if links else input_dir/'identity_links.csv').exists() else None,'input_files':lab.manifests},indent=2))
        db.close();db=None
        logging.info('Validation complete; saving the new run')
        logging.getLogger().removeHandler(log_handler);log_handler.close()
        temporary.rename(output)
        logging.info('Completed: %s',output)
        return output
    except Exception:
        if db is not None:db.close()
        # Preserve partial diagnostics without ever replacing a successful run.
        logging.exception('Failed run retained for inspection at %s',temporary)
        raise
    finally:
        logging.getLogger().removeHandler(log_handler);log_handler.close()

def generate_sql(output, start, end, cp_confirmed=False, row_limit=None):
    start,end=day(start),day(end)
    if not start or not end or start>end:raise ValueError('Valid ordered --start and --end dates are required')
    output=Path(output)
    if output.exists():raise ValueError('SQL output exists; choose another directory')
    if row_limit is not None and row_limit<1:raise ValueError('--row-limit must be positive')
    output.mkdir(parents=True)
    for source,spec in SOURCES.items():
        qualified='.'.join(ident(part) for part in spec['table'].split('.'))
        folder=output/source
        preface='-- READ ONLY. Execute statements separately. Save each result independently.\n'
        dump(folder/'01_schema.sql',preface+f'SHOW COLUMNS FROM {qualified};\n\nSHOW CREATE TABLE {qualified};\n')
        if source=='counterparty' and not cp_confirmed:
            dump(folder/'02_LOCATION_UNCONFIRMED.txt','Verify the proposed delta.prod_party_gda.counterparty_core catalog object, required fields, run_date type/format and its equivalence to the reviewed Delta source. Then regenerate with --counterparty-confirmed. No Counterparty extraction query is emitted by default.\n')
            continue
        lo,hi=(start.replace('-',''),end.replace('-','')) if spec['format']=='compact' else (start,end)
        date_col=ident(spec['date'])
        predicate=f't.{date_col} >= \'{lo}\' AND t.{date_col} <= \'{hi}\''
        if source=='counterparty':
            # CP needs a lookback before the first CLO history date, for point-in-time tests.
            lo=(date.fromisoformat(start)-timedelta(days=120)).strftime('%Y%m%d')
            predicate=f't.{date_col} >= \'{lo}\' AND t.{date_col} <= \'{hi}\''
        limit=f'\nLIMIT {row_limit}' if row_limit else ''
        comments='-- Review live schema and partition properties first. Native date formats follow supplied schemas.\n-- Capture all relevant fields and history within these bounds. No product/materiality/utilisation filters.\n-- Add verified country/client/partition predicates to control volume; split into non-overlapping chunks.\n-- SELECT t.* preserves candidate fields for development. Review complex types/export format in your SQL client.\n'
        if source=='counterparty':comments+='-- Candidate run_date varchar YYYYMMDD is UNVERIFIED; adapt if live schema differs. 120-day extraction lookback is a prior setting to validate.\n'
        if row_limit:comments+='-- LIMITED ARBITRARY SAMPLE: cannot establish history, population completeness or match rates.\n'
        dump(folder/'02_extract.sql',preface+comments+f'SELECT t.*\nFROM {qualified} t\nWHERE {predicate}{limit};\n')
        dump(folder/'03_date_profile.sql',preface+f'SELECT t.{date_col} AS source_date, COUNT(*) AS raw_rows\nFROM {qualified} t\nWHERE {predicate}\nGROUP BY t.{date_col}\nORDER BY t.{date_col};\n')
        dump(folder/'metadata.example.json',json.dumps({'source':source,'table':spec['table'],'query_file':'02_extract.sql','requested_start':lo,'requested_end':hi,'row_limit':row_limit,'extracted_at_utc':'FILL_AFTER_EXPORT','sql_client':'FILL','filters':'FILL_EXACT_PREDICATES','query_sha256':'FILL_IF_AVAILABLE','coverage':'bounded development extract; completeness unverified'},indent=2))
    dump(output/'README.md','# Generated read-only extraction SQL\n\nRun schema statements first, verify dates/partitions and source identity, then run bounded extracts. Save data as `<source>.csv` or `<source>/part-001.csv` in your input directory. Save schema and DDL outside the source data folders. Copy each metadata example beside the CSV as `<csv-stem>.metadata.json` and fill in the actual submitted query/parameters and extraction outcome.\n\nCounterparty catalog location and date format require confirmation. The other queries follow supplied schema exports, not a live verification. Date profiles describe exported raw-row coverage, not unique facilities. No query is automatically submitted.\n\nSyntax reference: https://trino.io/docs/current/sql/select.html and https://trino.io/docs/current/sql/show-columns.html.\n')

def query(database, sql):
    connection=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)
    connection.execute('PRAGMA query_only=ON')
    try:
        cursor=connection.execute(sql)
        writer=csv.writer(sys.stdout);writer.writerow([c[0] for c in cursor.description]);writer.writerows(cursor)
    finally:connection.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('sql',help='Generate read-only Starburst/Trino SQL; no database connection')
    p.add_argument('--out',required=True);p.add_argument('--start',required=True);p.add_argument('--end',required=True);p.add_argument('--counterparty-confirmed',action='store_true');p.add_argument('--row-limit',type=int)
    p=sub.add_parser('run',help='Build a new local SQLite test run from CSV files')
    p.add_argument('--input',required=True);p.add_argument('--out',required=True);p.add_argument('--as-of',required=True);p.add_argument('--config',default=str(ROOT/'config.json'));p.add_argument('--links')
    p=sub.add_parser('demo',help='Generate synthetic inputs and execute the complete workflow')
    p.add_argument('--out',required=True)
    p=sub.add_parser('query',help='Run a single read-only SQLite SELECT and print CSV')
    p.add_argument('--database',required=True);p.add_argument('--sql',required=True)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    try:
        if args.command=='sql':generate_sql(args.out,args.start,args.end,args.counterparty_confirmed,args.row_limit)
        elif args.command=='run':run(args.input,args.out,args.config,args.as_of,args.links)
        elif args.command=='demo':
            from demo_data import build_demo
            folder=Path(args.out).resolve()
            build_demo(folder)
            run(folder/'input',folder/'results',folder/'demo_config.json','2026-10-29')
        elif args.command=='query':query(args.database,args.sql)
        return 0
    except (ValueError,OSError,csv.Error,json.JSONDecodeError,sqlite3.Error,KeyError,TypeError) as exc:
        logging.error('%s',exc)
        return 2

if __name__=='__main__':
    sys.exit(main())
