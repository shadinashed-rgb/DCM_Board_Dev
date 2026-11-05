#!/usr/bin/env python3
"""PVD-first client cohort discovery, read-only extraction plans and CSV coverage tests."""
import argparse
from collections import Counter
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
import sqlite3
import sys
import tempfile

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'engine'))
import bond_radar as engine

REVIEW_COLUMNS=['review_id','mastergroup_id','origin_source','origin_column','identifier_value','proposed_type','approved_type','target_source','decision','evidence','valid_from','valid_to','scope_json','first_observed','last_observed','observed_rows']
IDENTIFIERS={
 'pvd':{'PVD_RELATIONSHIP_ID':['joi_relationship_id'],'PVD_SUPERGROUP_ID':['drr_supergroup_id'],'PVD_KEY':['joi_key']},
 'clo':{'MASTERGROUP_ID':['rct_mastergroup_id'],'CIN':['obligor_cin'],'GID':['rct_gid'],'FACILITY_ID':['facility_id'],'CLO_SUB_LIMIT_ID':['sub_lim_id'],'CLO_RCT_FACILITY_REF':['rct_facility_ref']},
 'counterparty':{'MASTERGROUP_ID':['mastergroup_esr_identifier'],'CIN':['customer_relationship_cin_identifier'],'GID':['customer_relationship_gid_identifier']},
 'facilities':{'CIN':['cin'],'RELATIONSHIP_ID':['relationship_id'],'CUSTOMER_ID':['customer_id'],'FACILITY_ID':['facility_id']},
 'kyc':{'CIN':['cin']},
 'drr':{'MASTERGROUP_ID':['drr_mastergroup_id'],'CIN':['cin'],'GID':['gid'],'DRR_RELATIONSHIP_ID':['app_relationship_id'],'FACILITY_ID':['facility_id']},
 'covenants':{'RELATIONSHIP_ID':['relationship_id'],'FACILITY_ID':['facility_id']}
}
NAME_COLUMNS={
 'pvd':['joi_relationship_name','omn_mastergroup_name','drr_supergroup_name'],
 'clo':['rct_mastergroup_name','rct_group_name','obligor_customer_name'],
 'kyc':['legal_name','cdd_topco_legal_name','mg_parent_legal_name'],
 'counterparty':[], 'facilities':[], 'drr':[], 'covenants':[]
}
ARRAY_NAME_COLUMNS={'kyc':{'cdd_topco_legal_name'}}
GROUP_FIELDS={'clo':'rct_mastergroup_id','counterparty':'mastergroup_esr_identifier','drr':'drr_mastergroup_id'}
SCOPE_FIELDS={'clo':['source_system','mapping_system','hsbc_booking_legal_entity'],'facilities':['source_system_name','country_code'],'covenants':['source_system_name','country_code'],'drr':['source_system_name','rpt_facility_country_code']}
# development-2: SIG03 split into SIG03A/SIG03B; SIG06 is financial covenant breach/pressure;
# SIG07 rating advisory comes from CME call reports (not integrated). Utilisation and
# credit category/CRR are context datasets, not signals.
SIGNALS=('SIG01','SIG02','SIG03A','SIG03B','SIG04','SIG06','SIG07','CTX_UTIL','CTX_CREDIT')
SIGNAL_SOURCES={'SIG01':['clo','facilities'],'SIG02':['facilities'],'SIG03A':[],'SIG03B':[],'SIG04':['kyc'],'SIG06':['covenants'],'SIG07':[],'CTX_UTIL':['clo','pvd','drr'],'CTX_CREDIT':['pvd','facilities']}

def dump(path,value):engine.dump(Path(path),value)
def write_csv(path,columns,rows):engine.write_csv(Path(path),columns,rows)
def norm(value):return engine.norm(value)
def day(value):return engine.day(value)
def digest(*values):return engine.digest(*values)
def ident(value):return engine.ident(value)
def literal(value):return 'CAST(NULL AS VARCHAR)' if value is None else "'"+str(value).replace("'","''")+"'"
def name_key(value):return re.sub(r'[^A-Z0-9]+',' ',str(value or '').upper()).strip()
def sql_norm(column):return f"UPPER(REGEXP_REPLACE(TRIM(CAST(t.{ident(column)} AS VARCHAR)), '\\s+', ' '))"
def sql_name(column,array=False):
    expression=f"ARRAY_JOIN(t.{ident(column)}, ' ')" if array else f'CAST(t.{ident(column)} AS VARCHAR)'
    return f"TRIM(REGEXP_REPLACE(UPPER(COALESCE({expression}, '')), '[^A-Z0-9]+', ' '))"

def config(path):
    cfg=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    groups=cfg['groups']
    if not isinstance(groups,list) or any(not isinstance(g.get('aliases'),list) or any(not isinstance(a,str) for a in g['aliases']) for g in groups):raise ValueError('groups must be a list; each aliases value must be a list of names')
    if not groups or len({norm(g['mastergroup_id']) for g in groups})!=len(groups):raise ValueError('Supply unique nonempty target mastergroup IDs')
    if any(not norm(g['mastergroup_id']) or not g['aliases'] or any(not name_key(a) for a in g['aliases']) for g in groups):raise ValueError('Every group needs an ID and nonempty discovery aliases')
    if type(cfg['counterparty_catalog_confirmed']) is not bool:raise ValueError('counterparty_catalog_confirmed must be JSON true/false')
    if cfg['freshness_days']<0 or len(cfg['csv_delimiter'])!=1:raise ValueError('Invalid freshness_days/csv_delimiter')
    if cfg.get('counterparty_lookback_days',120)<0:raise ValueError('counterparty_lookback_days must be nonnegative')
    if not isinstance(cfg.get('source_windows',{}),dict) or set(cfg.get('source_windows',{}))-set(engine.SOURCES):raise ValueError('source_windows contains an unknown source')
    cfg['invalid_identifiers']=[norm(v) for v in cfg['invalid_identifiers']]
    return cfg

def valid_id(value,cfg):return norm(value) is not None and norm(value) not in cfg['invalid_identifiers']

def seed_links(cfg):
    return [dict(mastergroup_id=norm(g['mastergroup_id']),approved_type='MASTERGROUP_ID',identifier_value=norm(g['mastergroup_id']),target_source='*',valid_from='',valid_to='',scope_json='{}',review_id='seed:'+norm(g['mastergroup_id']),evidence='User-supplied target mastergroup anchor') for g in cfg['groups']]

def read_approvals(path,cfg):
    if path is None:return []
    if not Path(path).is_file():raise ValueError('Approval file does not exist: '+str(path))
    targets={norm(g['mastergroup_id']) for g in cfg['groups']};seen=set();result=[]
    with Path(path).open(encoding='utf-8-sig',newline='') as handle:
        reader=csv.DictReader(handle)
        if reader.fieldnames!=REVIEW_COLUMNS:raise ValueError('Approval CSV headers must match identifier_review.csv exactly')
        for line,row in enumerate(reader,2):
            if not row['review_id'].strip():raise ValueError(f'Approval record {line}: review_id is required')
            decision=row['decision'].strip().lower()
            if decision not in ('','pending','approve','reject'):raise ValueError(f'Approval record {line}: decision must be pending, approve or reject')
            if row['review_id'] in seen:raise ValueError(f'Duplicate review_id {row["review_id"]}')
            seen.add(row['review_id'])
            if decision!='approve':continue
            row['mastergroup_id']=norm(row['mastergroup_id']);row['identifier_value']=norm(row['identifier_value']);row['approved_type']=norm(row['approved_type']);row['target_source']=row['target_source'].strip()
            if row['mastergroup_id'] not in targets or not valid_id(row['identifier_value'],cfg) or not row['evidence'].strip():raise ValueError(f'Approval record {line}: require a target group, valid identifier and verification evidence')
            kind,target=row['approved_type'],row['target_source']
            if target not in IDENTIFIERS and target!='*':raise ValueError('Unknown approval target_source: '+target)
            if target=='*' and kind not in ('MASTERGROUP_ID','CIN','GID'):raise ValueError('Only reviewed MASTERGROUP_ID/CIN/GID namespaces may target *')
            if target!='*' and kind not in IDENTIFIERS[target]:raise ValueError(f'{kind} has no verified/configured column route in {target}')
            for col in ('valid_from','valid_to'):
                if row[col] and not day(row[col]):raise ValueError('Invalid approval validity date')
            if row['valid_from'] and row['valid_to'] and day(row['valid_from'])>day(row['valid_to']):raise ValueError('Approval validity interval is reversed')
            scope=json.loads(row['scope_json'] or '{}')
            if not isinstance(scope,dict) or any(not re.fullmatch(r'[a-z][a-z0-9_]*',key) or not valid_id(value,cfg) for key,value in scope.items()):raise ValueError('scope_json must contain valid source column names and nonempty identifier values')
            if target=='*' and scope:raise ValueError('Column scopes require a specific target_source')
            if kind in ('FACILITY_ID','CLO_SUB_LIMIT_ID','CLO_RCT_FACILITY_REF'):
                required=SCOPE_FIELDS.get(target,[])
                if not required or any(not norm(scope.get(k)) for k in required):raise ValueError(f'Facility approval for {target} requires explicit scope_json fields: {required}')
            row['_scope']={k:norm(v) for k,v in scope.items()}
            row['scope_json']=json.dumps(scope,sort_keys=True)
            result.append(row)
    return result

def applicable(link,source,payload,observed):
    if link['target_source'] not in ('*',source):return False
    if link.get('valid_from') and observed<day(link['valid_from']):return False
    if link.get('valid_to') and observed>day(link['valid_to']):return False
    if any(norm(payload.get(k))!=norm(v) for k,v in link.get('_scope',{}).items()):return False
    return any(norm(payload.get(col))==link['identifier_value'] for col in IDENTIFIERS[source].get(link['approved_type'],[]))

def input_files(folder,source):
    chunks=sorted((folder/source).glob('*.csv')) if (folder/source).is_dir() else []
    aliases=[folder/a for a in engine.SOURCES[source]['aliases'] if (folder/a).is_file()]
    if chunks and aliases or len(aliases)>1:raise ValueError(f'{source}: use one flat CSV or one chunk folder, not multiple input routes')
    return chunks or aliases

def create_db(db):
    db.executescript('''
    CREATE TABLE raw_rows(source TEXT, raw_id INTEGER, filename TEXT, csv_record INTEGER, observation_date TEXT, row_hash TEXT, payload TEXT, PRIMARY KEY(source,raw_id));
    CREATE TABLE source_status(source TEXT PRIMARY KEY, files INTEGER, raw_rows INTEGER, columns_json TEXT, invalid_dates INTEGER, excluded_future INTEGER, metadata_missing INTEGER, missing_id_headers_json TEXT, extraction_errors INTEGER);
    CREATE TABLE matches(source TEXT, raw_id INTEGER, mastergroup_id TEXT, status TEXT, routes_json TEXT, PRIMARY KEY(source,raw_id,mastergroup_id));
    CREATE INDEX match_group ON matches(mastergroup_id,source,status);
    CREATE TABLE approved_links(review_id TEXT,mastergroup_id TEXT,identifier_type TEXT,identifier_value TEXT,target_source TEXT,valid_from TEXT,valid_to TEXT,scope_json TEXT,evidence TEXT);
    CREATE TABLE coverage(mastergroup_id TEXT,group_name TEXT,source TEXT,status TEXT,raw_export_rows INTEGER,matched_rows INTEGER,matched_distinct_rows INTEGER,candidate_rows INTEGER,conflict_rows INTEGER,distinct_cins INTEGER,distinct_gids INTEGER,distinct_relationship_ids INTEGER,first_observed TEXT,last_observed TEXT,candidate_first_observed TEXT,candidate_last_observed TEXT,stale_rows INTEGER,invalid_dates INTEGER,future_rows INTEGER,metadata_missing INTEGER,qualification TEXT);
    CREATE TABLE signal_readiness(mastergroup_id TEXT,signal_id TEXT,status TEXT,sources_with_matches TEXT,qualification TEXT);
    ''')

def classify(source,payload,observed,cfg,links):
    trusted={};candidates={}
    for link in links:
        if applicable(link,source,payload,observed):trusted.setdefault(link['mastergroup_id'],[]).append('approved:'+link['approved_type']+':'+link['review_id'])
    for group in cfg['groups']:
        mg=norm(group['mastergroup_id'])
        if source=='pvd':
            for col in ('joi_relationship_id','drr_supergroup_id'):
                if norm(payload.get(col))==mg:candidates.setdefault(mg,[]).append('candidate_id:'+col)
        for col in NAME_COLUMNS[source]:
            value=name_key(payload.get(col))
            if value and any(name_key(alias) in value for alias in group['aliases']):candidates.setdefault(mg,[]).append('candidate_name:'+col)
    external_group=norm(payload.get(GROUP_FIELDS.get(source,'')))
    rows=[]
    for mg in sorted(set(trusted)|set(candidates)):
        contradiction=mg in trusted and (len(trusted)>1 or valid_id(external_group,cfg) and external_group!=mg)
        status='conflict' if contradiction else 'matched' if mg in trusted else 'candidate'
        rows.append((mg,status,trusted.get(mg,[])+candidates.get(mg,[])))
    return rows

def analyse(input_dir,output,as_of,cfg_path,approved_path=None):
    cfg=config(cfg_path);as_of=day(as_of)
    if not as_of:raise ValueError('Supply --as-of YYYY-MM-DD')
    folder=Path(input_dir).resolve();output=Path(output).resolve()
    if not folder.is_dir():raise ValueError('Input folder does not exist')
    if output.exists():raise ValueError('Output exists; choose a new run directory')
    if folder==output or folder in output.parents:raise ValueError('Output must be outside the input folder')
    if approved_path and not Path(approved_path).is_file():raise ValueError('Explicit approval file does not exist')
    reviewed=read_approvals(approved_path,cfg);links=seed_links(cfg)+reviewed
    imported=json.loads((folder/'import_manifest.json').read_text()) if (folder/'import_manifest.json').exists() else {}
    import_errors=Counter(r.get('source') for r in imported.get('files',[]) if r.get('kind')=='error')
    if not any(input_files(folder,s) for s in engine.SOURCES) and not import_errors:raise ValueError('No recognised source CSVs found. Start with pvd.csv, use import-exports, or run the demo.')
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.'+output.name+'-',dir=output.parent));db=sqlite3.connect(temp/'cohort.sqlite');db.row_factory=sqlite3.Row
    handler=logging.FileHandler(temp/'run.log',encoding='utf-8');logging.getLogger().addHandler(handler)
    manifests=[];proposals={};names={};issues=[]
    try:
        create_db(db)
        for link in links:db.execute('INSERT INTO approved_links VALUES (?,?,?,?,?,?,?,?,?)',(link['review_id'],link['mastergroup_id'],link['approved_type'],link['identifier_value'],link['target_source'],link.get('valid_from',''),link.get('valid_to',''),link.get('scope_json','{}'),link['evidence']))
        for source,spec in engine.SOURCES.items():
            files=input_files(folder,source);columns=[];raw_id=0;invalid=future=metadata_missing=0
            for path in files:
                checksum=engine.file_hash(path)
                with path.open(encoding='utf-8-sig',newline='') as handle:
                    reader=csv.reader(handle,delimiter=cfg['csv_delimiter']);header=next(reader,None)
                    if not header:raise ValueError(str(path)+': missing CSV header')
                    header=[c.strip().lower() for c in header]
                    if len(set(header))!=len(header) or any(not c or c.startswith('__') for c in header):raise ValueError('Empty, duplicate or reserved CSV header')
                    if columns and columns!=header:raise ValueError(source+': chunk schema/header drift')
                    columns=header
                    if spec['date'] not in columns:raise ValueError(source+': required source date header absent: '+spec['date'])
                    if source=='pvd' and 'joi_relationship_id' not in columns:raise ValueError('PVD discovery requires joi_relationship_id')
                    rows=0
                    for record,values in enumerate(reader,2):
                        if len(values)!=len(header):raise ValueError(f'{path.name}:{record}: malformed CSV column count')
                        raw_id+=1;rows+=1;payload=dict(zip(header,values));observed=day(payload.get(spec['date']));row_hash=digest(payload)
                        db.execute('INSERT INTO raw_rows VALUES (?,?,?,?,?,?,?)',(source,raw_id,str(path.resolve()),record,observed,row_hash,json.dumps(payload)))
                        processing=[day(payload.get('run_date'))]+([day(payload.get('etlmonth')),day(payload.get('etlmonth_drr'))] if source=='pvd' else [])
                        if not observed:invalid+=1;continue
                        if observed>as_of or any(value and value>as_of for value in processing):future+=1;continue
                        matches=classify(source,payload,observed,cfg,links)
                        for mg,status,routes in matches:
                            db.execute('INSERT INTO matches VALUES (?,?,?,?,?)',(source,raw_id,mg,status,json.dumps(routes)))
                            for col in NAME_COLUMNS[source]:
                                if norm(payload.get(col)) and norm(payload.get(col)) not in cfg['invalid_identifiers']:
                                    key=(mg,source,col,payload[col]);names[key]=names.get(key,0)+1
                            if status=='conflict':continue
                            for kind,cols in IDENTIFIERS[source].items():
                                for col in cols:
                                    value=payload.get(col)
                                    if not valid_id(value,cfg) or kind=='MASTERGROUP_ID':continue
                                    scope={k:norm(payload[k]) for k in SCOPE_FIELDS.get(source,[]) if norm(payload.get(k))} if kind in ('FACILITY_ID','CLO_SUB_LIMIT_ID','CLO_RCT_FACILITY_REF') else {}
                                    scope_text=json.dumps(scope,sort_keys=True)
                                    review_id=digest(mg,source,col,norm(value),kind,scope_text)
                                    if review_id not in proposals:
                                        proposals[review_id]=dict(zip(REVIEW_COLUMNS,[review_id,mg,source,col,norm(value),kind,kind,'*' if kind in ('CIN','GID') else source,'pending','', '', '',scope_text,observed,observed,0]))
                                    p=proposals[review_id];p['observed_rows']+=1;p['first_observed']=min(p['first_observed'],observed);p['last_observed']=max(p['last_observed'],observed)
                if engine.file_hash(path)!=checksum:raise ValueError(path.name+' changed during import')
                meta=path.with_suffix('.metadata.json');metadata=json.loads(meta.read_text()) if meta.exists() else None
                metadata_missing+=not meta.exists()
                manifests.append(dict(source=source,path=str(path.resolve()),sha256=checksum,rows=rows,metadata=metadata))
            missing=sorted({c for cols in IDENTIFIERS[source].values() for c in cols}-set(columns)) if files else []
            db.execute('INSERT INTO source_status VALUES (?,?,?,?,?,?,?,?,?)',(source,len(files),raw_id,json.dumps(columns),invalid,future,metadata_missing,json.dumps(missing),import_errors[source]))
            if missing:issues.append(source+' export lacks candidate identifier headers: '+', '.join(missing)+'. Review full schema/export before judging match coverage.')
            if import_errors[source]:issues.append(source+': '+str(import_errors[source])+' query-error export(s) recorded; these are not source data.')
            if source=='pvd' and files:
                issues.append('PVD relationship/supergroup/key columns retain their own namespaces. No CIN/GID interpretation was inferred.')
        # Preserve prior decisions in the next review file; new discoveries stay pending.
        prior={}
        if approved_path:
            with Path(approved_path).open(encoding='utf-8-sig',newline='') as handle:prior={r['review_id']:r for r in csv.DictReader(handle)}
        for rid,row in proposals.items():
            if rid in prior:
                if any(norm(row[k])!=norm(prior[rid][k]) for k in ('mastergroup_id','origin_source','origin_column','identifier_value')):raise ValueError('A review_id was reused for a different identifier. Add a separate manual row with a new review_id.')
                for key in ('approved_type','target_source','decision','evidence','valid_from','valid_to','scope_json'):row[key]=prior[rid][key]
        for rid,row in prior.items():
            if rid not in proposals:
                proposals[rid]=dict(row,observed_rows=0)
        write_csv(temp/'identifier_review.csv',REVIEW_COLUMNS,([r[c] for c in REVIEW_COLUMNS] for r in sorted(proposals.values(),key=lambda r:(r['mastergroup_id'],r['origin_source'],r['proposed_type'],r['identifier_value']))))
        write_csv(temp/'name_variations.csv',['mastergroup_id','source','source_column','original_name','name_key','raw_observations'],([*key,name_key(key[3]),count] for key,count in sorted(names.items())))
        build_coverage(db,cfg,as_of)
        for table in ('source_status','matches','approved_links','coverage','signal_readiness'):
            cur=db.execute('SELECT * FROM '+ident(table));write_csv(temp/(table+'.csv'),[d[0] for d in cur.description],cur)
        export_summary(db,cfg,temp,proposals)
        dump(temp/'config_used.json',json.dumps(cfg,indent=2))
        dump(temp/'run_manifest.json',json.dumps({'as_of':as_of,'created_utc':datetime.now(timezone.utc).isoformat(),'membership_policy':cfg['membership_policy'],'code_sha256':engine.file_hash(Path(__file__)),'config_sha256':engine.file_hash(Path(cfg_path)),'approved_file_sha256':engine.file_hash(Path(approved_path)) if approved_path else None,'inputs':manifests,'issues':issues,'approved_links_count':len(reviewed)},indent=2))
        write_report(db,cfg,temp,as_of,issues)
        db.commit()
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('SQLite integrity check failed')
        collisions=db.execute("SELECT source,raw_id FROM matches WHERE status='matched' GROUP BY source,raw_id HAVING COUNT(*)>1").fetchall()
        if collisions:raise RuntimeError('A raw row was assigned to multiple groups')
        db.close();db=None;logging.getLogger().removeHandler(handler);handler.close();temp.rename(output)
        logging.info('Cohort analysis saved: %s',output)
        return output
    except Exception:
        logging.exception('Failed cohort run retained at %s',temp)
        raise
    finally:
        if db is not None:db.close()
        logging.getLogger().removeHandler(handler);handler.close()

def build_coverage(db,cfg,as_of):
    for group in cfg['groups']:
        mg=norm(group['mastergroup_id'])
        for source in engine.SOURCES:
            ss=db.execute('SELECT * FROM source_status WHERE source=?',(source,)).fetchone()
            records=db.execute('SELECT r.*,m.status FROM raw_rows r JOIN matches m USING(source,raw_id) WHERE m.mastergroup_id=? AND r.source=?',(mg,source))
            accepted=candidate=conflict=stale=0;first=last=candidate_first=candidate_last=None
            cins=set();gids=set();rels=set()
            for row in records:
                if row['status']=='conflict':conflict+=1;continue
                if row['status']=='candidate':
                    candidate+=1;candidate_first=min(candidate_first,row['observation_date']) if candidate_first else row['observation_date'];candidate_last=max(candidate_last,row['observation_date']) if candidate_last else row['observation_date'];continue
                accepted+=1;first=min(first,row['observation_date']) if first else row['observation_date'];last=max(last,row['observation_date']) if last else row['observation_date']
                stale+=(date.fromisoformat(as_of)-date.fromisoformat(row['observation_date'])).days>cfg['freshness_days']
                payload=json.loads(row['payload'])
                for kind,bucket in [('CIN',cins),('GID',gids),('PVD_RELATIONSHIP_ID',rels),('RELATIONSHIP_ID',rels),('DRR_RELATIONSHIP_ID',rels)]:
                    bucket.update(norm(payload.get(col)) for col in IDENTIFIERS[source].get(kind,[]) if valid_id(payload.get(col),cfg))
            distinct=db.execute("SELECT COUNT(DISTINCT r.row_hash) FROM raw_rows r JOIN matches m USING(source,raw_id) WHERE m.mastergroup_id=? AND r.source=? AND m.status='matched'",(mg,source)).fetchone()[0]
            state='extraction_failed' if not ss['files'] and ss['extraction_errors'] else 'missing_file' if not ss['files'] else 'empty_export' if not ss['raw_rows'] else 'matched_stale' if accepted and stale==accepted else 'matched_with_conflicts' if accepted and conflict else 'matched' if accepted else 'mapping_conflict' if conflict else 'candidates_only' if candidate else 'no_matches_in_supplied_export'
            qualification='Counts refer to supplied exports only; whole-group completeness is unknown. Missing files are not zero activity.'
            if source=='counterparty' and not cfg['counterparty_catalog_confirmed']:qualification+=' Catalog location remains unconfirmed.'
            if ss['invalid_dates'] or ss['excluded_future']:qualification+=' Invalid/future-dated rows are excluded from matching.'
            if json.loads(ss['missing_id_headers_json']):qualification+=' Missing identifier headers: '+ss['missing_id_headers_json']+'.'
            if ss['extraction_errors']:qualification+=' '+str(ss['extraction_errors'])+' failed query export(s) were excluded; see import_manifest.json.'
            db.execute('INSERT INTO coverage VALUES ('+','.join('?' for _ in range(21))+')',(mg,group['name'],source,state,ss['raw_rows'],accepted,distinct,candidate,conflict,len(cins),len(gids),len(rels),first,last,candidate_first,candidate_last,stale,ss['invalid_dates'],ss['excluded_future'],ss['metadata_missing'],qualification))
        for signal,sources in SIGNAL_SOURCES.items():
            matched=[s for s in sources if db.execute('SELECT matched_rows FROM coverage WHERE mastergroup_id=? AND source=?',(mg,s)).fetchone()[0]]
            state='source_not_identified' if signal in ('SIG03A','SIG03B') else 'source_not_integrated' if signal=='SIG07' else 'source_records_present_definition_unverified' if matched else 'no_linked_source_records'
            qualification='Run signal tests to check fields/history/units. Source records alone do not validate the signal.'
            if signal=='SIG07':qualification='Rating advisory requests are recorded in CME call reports; integration depends on MNPI/entitlement decisions (as SIG05).'
            if signal=='SIG06':qualification='Needs genuine financial covenant tests (net debt/EBITDA actual vs maximum); pressure = within half a turn of the maximum.'
            if signal.startswith('CTX_'):qualification='Context dataset, not a signal.'
            db.execute('INSERT INTO signal_readiness VALUES (?,?,?,?,?)',(mg,signal,state,json.dumps(matched),qualification))

def export_summary(db,cfg,out,proposals):
    columns=['mastergroup_id','group_name','discovered_cins','discovered_gids','approved_cins','approved_gids']+[s+'_matched_rows' for s in engine.SOURCES]+['sources_with_matches','sources_with_candidates','sources_missing']
    rows=[]
    for g in cfg['groups']:
        mg=norm(g['mastergroup_id']);values=[mg,g['name']]
        for kind in ('CIN','GID'):values.append(len({r['identifier_value'] for r in proposals.values() if r['mastergroup_id']==mg and r['proposed_type']==kind}))
        for kind in ('CIN','GID'):values.append(db.execute('SELECT COUNT(DISTINCT identifier_value) FROM approved_links WHERE mastergroup_id=? AND identifier_type=?',(mg,kind)).fetchone()[0])
        coverage={r['source']:dict(r) for r in db.execute('SELECT * FROM coverage WHERE mastergroup_id=?',(mg,))}
        values += [coverage[s]['matched_rows'] for s in engine.SOURCES]
        values += [sum(v['matched_rows']>0 for v in coverage.values()),sum(v['candidate_rows']>0 for v in coverage.values()),sum(v['status']=='missing_file' for v in coverage.values())]
        rows.append(values)
    write_csv(out/'coverage_summary.csv',columns,rows)

def write_report(db,cfg,out,as_of,issues):
    lines=['# PVD-first cohort extraction review','',f'Assessment date: {as_of}', '',cfg['membership_policy'],'','## Coverage by group and source','','| Group | Source | State | Matched rows | Distinct matched rows | Candidates | Conflicts | Latest matched date |','| --- | --- | --- | ---: | ---: | ---: | ---: | --- |']
    for r in db.execute('SELECT * FROM coverage ORDER BY mastergroup_id,source'):
        lines.append(f"| {r['group_name']} ({r['mastergroup_id']}) | {r['source']} | {r['status']} | {r['matched_rows']} | {r['matched_distinct_rows']} | {r['candidate_rows']} | {r['conflict_rows']} | {r['last_observed'] or 'Unavailable'} |")
    lines += ['','## Interpretation','','- PVD exact ID/name discovery remains candidate evidence until the identifier role/group association is reviewed.','- `identifier_review.csv` contains distinct candidate IDs, original source columns, observation ranges and pending decisions. No CIN is inferred from the shape of `joi_key` or `joi_relationship_id`.','- A source row matching conflicting approved group links or disagreeing with its explicit mastergroup is quarantined. Group expansion is not transitive.','- `name_variations.csv` is a discovery/review inventory. Names do not become authoritative join keys.','- Missing, empty, unmatched, candidate-only and conflicting results have separate coverage states. Counts cannot establish source-wide completeness.','- Coverage counts preserve raw observations and separately show distinct row hashes. Financial balances are not summed here.','','## Next steps','','1. Review identifiers and save reviewed decisions in an approval CSV. Approve only with evidence and the correct namespace/source scope.','2. Generate source SQL from approved links and target mastergroup anchors. Export the resulting source data and rerun analysis.','3. Repeat as DRR/Counterparty/CLO reveal additional CIN/GID/relationship mappings. A new identifier is proposed for review; it is not silently approved.','4. Run the bundled signal tests on uniquely linked rows. Business triggers remain unverified by default.','','## Qualifications','',*[f'- {issue}' for issue in issues],'- As-of checks use exported observation/processing dates, not historical database version recovery.','- Counterparty table location, PVD grain/units and cross-source facility equivalence still require verification.']
    dump(out/'REPORT.md','\n'.join(lines)+'\n')

def bounds(source,cfg,start,end):
    setting=cfg.get('source_windows',{}).get(source,{})
    lower,upper=start,end
    if source=='counterparty' and 'start' not in setting:
        clo=cfg.get('source_windows',{}).get('clo',{})
        base=day(clo.get('start',start))
        if not base:raise ValueError('Invalid CLO date for Counterparty lookback')
        lower=(date.fromisoformat(base)-timedelta(days=cfg.get('counterparty_lookback_days',120))).isoformat()
        upper=clo.get('end',end)
    lo,hi=day(setting.get('start',lower)),day(setting.get('end',upper))
    if not lo or not hi or lo>hi:raise ValueError('Invalid extraction window for '+source)
    compact=engine.SOURCES[source]['format']=='compact'
    return (lo.replace('-',''),hi.replace('-','')) if compact else (lo,hi)

def date_predicate(source,cfg,start,end):
    lo,hi=bounds(source,cfg,start,end);col=ident(engine.SOURCES[source]['date'])
    return f't.{col} >= {literal(lo)} AND t.{col} <= {literal(hi)}'

def qualified(source):return '.'.join(ident(p) for p in engine.SOURCES[source]['table'].split('.'))

def name_predicate(source,cfg):
    return ' OR\n    '.join(f'STRPOS({sql_name(col,col in ARRAY_NAME_COLUMNS.get(source,set()))}, {literal(name_key(alias))}) > 0' for col in NAME_COLUMNS[source] for g in cfg['groups'] for alias in g['aliases'])

def sql_header():return '-- READ ONLY: run in your Starburst/Trino SQL client; no statement is submitted by this package.\n-- Verify live schema, native date format and partition properties. Capture all selected columns.\n-- No business materiality/product/utilisation filters. Counts are raw observations, not facilities.\n'

def seed_sql(output,cfg_path,start,end):
    cfg=config(cfg_path);output=Path(output)
    if output.exists():raise ValueError('SQL output exists; choose a new directory')
    where=date_predicate('pvd',cfg,start,end);table=qualified('pvd')
    exact=' OR '.join(f'{sql_norm(col)} IN ('+', '.join(literal(norm(g['mastergroup_id'])) for g in cfg['groups'])+')' for col in ('joi_relationship_id','drr_supergroup_id'))
    predicate='('+exact+' OR\n    '+name_predicate('pvd',cfg)+')'
    dump(output/'00_pvd_partitions.sql',sql_header()+'-- Metadata only. Availability depends on the Hive connector and permissions.\n-- Inspect these values before choosing source/partition dates.\nSELECT portfolio, etlmonth\nFROM "hive"."pvd_prod_wave"."pvd_omnia_drr$partitions"\nORDER BY etlmonth DESC, portfolio;\n')
    dump(output/'01_pvd_schema.sql',sql_header()+f'SHOW COLUMNS FROM {table};\n\nSHOW CREATE TABLE {table};\n')
    dump(output/'02_pvd_discovery.sql',sql_header()+'-- CANDIDATE DISCOVERY ONLY: exact values in PVD ID fields do not establish their identifier namespace.\n-- Name searches may include unrelated entities. Export all results as pvd.csv.\n'+f'SELECT t.*\nFROM {table} t\nWHERE {where}\n  AND {predicate};\n')
    dump(output/'03_pvd_date_coverage.sql',sql_header()+f'SELECT t.joi_date, COUNT(*) AS raw_rows\nFROM {table} t\nWHERE {where}\n  AND {predicate}\nGROUP BY t.joi_date ORDER BY t.joi_date;\n')
    ids=', '.join(literal(norm(g['mastergroup_id'])) for g in cfg['groups'])
    id_filter=f'{sql_norm("joi_relationship_id")} IN ({ids})'
    dump(output/'04_pvd_mastergroup_ids.sql',sql_header()+'-- ID-FIRST: exact supplied mastergroup values observed in joi_relationship_id.\n-- No name filter. This extracts their records; identifier semantics remain a separate review.\n'+f'SELECT t.* FROM {table} t\nWHERE {where}\n  AND {id_filter};\n')
    dump(output/'05_pvd_name_candidates.sql',sql_header()+'-- SUPPLEMENTARY NAME DISCOVERY: may return other mastergroups/supergroup members.\n'+f'SELECT t.* FROM {table} t\nWHERE {where}\n  AND ({name_predicate("pvd",cfg)});\n')
    dump(output/'06_pvd_id_date_coverage.sql',sql_header()+f'SELECT t.joi_relationship_id, t.joi_date, COUNT(*) AS raw_rows\nFROM {table} t\nWHERE {where}\n  AND {id_filter}\nGROUP BY t.joi_relationship_id, t.joi_date\nORDER BY t.joi_relationship_id, t.joi_date;\n')
    dump(output/'metadata.example.json',json.dumps({'source':'pvd','query_file':'02_pvd_discovery.sql','start':start,'end':end,'filters':'seed ID equality and candidate name aliases','extracted_at_utc':'FILL','execution_status':'FILL','export_row_limit':'FILL','coverage':'Discovery candidates; not a complete group entity roster.'},indent=2))

def source_sql(output,cfg_path,start,end,approved_path=None,observed_links=None):
    cfg=config(cfg_path);links=seed_links(cfg)+read_approvals(approved_path,cfg)+(observed_links or []);output=Path(output)
    if output.exists():raise ValueError('SQL output exists; choose a new directory')
    plans=[]
    for source in engine.SOURCES:
        folder=output/source;table=qualified(source);window=date_predicate(source,cfg,start,end)
        dump(folder/'01_schema.sql',sql_header()+f'SHOW COLUMNS FROM {table};\n\nSHOW CREATE TABLE {table};\n')
        selected=[r for r in links if r['target_source'] in ('*',source) and r['approved_type'] in IDENTIFIERS[source]]
        if source=='counterparty' and not cfg['counterparty_catalog_confirmed']:
            status='catalog_unconfirmed';dump(folder/'02_BLOCKED.txt','The proposed Counterparty catalog table and date format require live confirmation. Set counterparty_catalog_confirmed=true only after verifying them, then generate a new SQL pack.\n')
        elif not selected:
            status='no_approved_identifier_route';dump(folder/'02_BLOCKED.txt','No approved source-compatible identifiers are available. Review PVD-native identifiers, or use DRR/Counterparty/CLO group anchors to discover CIN/GID mappings and approve those before regenerating. Name candidates are in a separate query where verified name columns exist.\n')
        else:
            scopes=sorted({k for r in selected for k in r.get('_scope',{})})
            columns=['identifier_type','identifier_value','valid_from','valid_to']+['scope_'+str(i) for i in range(len(scopes))]
            records=[]
            for row in selected:
                compact=engine.SOURCES[source]['format']=='compact'
                validity=[day(row.get(k)) for k in ('valid_from','valid_to')]
                if compact:validity=[v.replace('-','') if v else None for v in validity]
                values=[row['approved_type'],row['identifier_value']]+validity+[row.get('_scope',{}).get(k) for k in scopes]
                records.append('('+', '.join(literal(v) for v in values)+')')
            cte='WITH cohort('+', '.join(columns)+') AS (\n  VALUES\n    '+',\n    '.join(records)+'\n)\n'
            routes=' OR '.join(f'(c.identifier_type={literal(kind)} AND {sql_norm(col)}=c.identifier_value)' for kind,cols in IDENTIFIERS[source].items() for col in cols if any(r['approved_type']==kind for r in selected))
            date_col='t.'+ident(engine.SOURCES[source]['date'])
            constraints=[f'({routes})',f'(c.valid_from IS NULL OR {date_col} >= c.valid_from)',f'(c.valid_to IS NULL OR {date_col} <= c.valid_to)']+[f'(c.scope_{i} IS NULL OR {sql_norm(k)}=c.scope_{i})' for i,k in enumerate(scopes)]
            predicate='EXISTS (SELECT 1 FROM cohort c WHERE '+' AND '.join(constraints)+')'
            note='-- SOURCE-OBSERVED CANDIDATE LOOKUP: CIN/GID values come from linked source records.\n-- This is extraction discovery, not approval of a shared identifier namespace.\n' if observed_links is not None else ''
            dump(folder/'02_extract.sql',sql_header()+note+'-- EXISTS returns each source row once even if several identifiers match.\n'+cte+f'SELECT t.*\nFROM {table} t\nWHERE {window}\n  AND {predicate};\n')
            dump(folder/'03_date_coverage.sql',sql_header()+cte+f'SELECT {date_col} AS source_date, COUNT(*) AS raw_rows\nFROM {table} t\nWHERE {window}\n  AND {predicate}\nGROUP BY {date_col} ORDER BY {date_col};\n')
            status='query_generated'
        names=name_predicate(source,cfg)
        if names and source!='counterparty':dump(folder/'04_name_candidates.sql',sql_header()+'-- NAME CANDIDATES ONLY: save separately as a chunk for this source; review before linking.\n'+f'SELECT t.* FROM {table} t\nWHERE {window}\n  AND ({names});\n')
        lo,hi=bounds(source,cfg,start,end)
        dump(folder/'metadata.example.json',json.dumps({'source':source,'table':engine.SOURCES[source]['table'],'start':lo,'end':hi,'query_file':'FILL_ACTUAL_QUERY','extracted_at_utc':'FILL','execution_status':'FILL','complete_or_limited':'FILL','coverage':'User-selected cohort; completeness unverified'},indent=2))
        plans.append((source,status,len(selected),lo,hi))
    write_csv(output/'extraction_plan.csv',['source','status','applicable_candidate_links' if observed_links is not None else 'applicable_approved_links','start','end'],plans)
    dump(output/'README.md','# Reviewed cohort SQL pack\n\nRun schema statements separately first. Execute 02_extract.sql only after source/schema/date checks. 04_name_candidates.sql is supplementary candidate discovery, never an approved identifier match. Missing 02_extract.sql is explained by 02_BLOCKED.txt. No source table writes or staging privileges are required. No SQL was executed by generation.\n\nCIN/GID links must be discovered and reviewed to unlock sources without direct mastergroup fields. Preserve full query text, parameters and export outcome. CSVs keep original headers/values.\n')
    if observed_links is not None:
        dump(output/'README.md','# Source-observed candidate SQL pack\n\nThese read-only lookups use IDs seen on linked source rows; they do not approve a shared client namespace. Run schema statements separately first, then copy 02_extract.sql into Starburst and execute/export manually. Name queries are supplementary only. Read 02_BLOCKED.txt for missing routes, and inspect observed_identifier_candidates.csv for provenance. No source or approval file is changed by generation.\n')

def candidate_sql(cohort_run,output,start,end,cfg_path=None):
    """Prepare read-only lookups from observed source IDs, without approving links."""
    cohort_run=Path(cohort_run).resolve();cfg_path=Path(cfg_path) if cfg_path else cohort_run/'config_used.json';cfg=config(cfg_path)
    db=sqlite3.connect((cohort_run/'cohort.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    observed={};provenance={}
    try:
        for row in db.execute("SELECT r.*,m.mastergroup_id FROM raw_rows r JOIN matches m USING(source,raw_id) WHERE m.status='matched'"):
            payload=json.loads(row['payload'])
            for kind in ('CIN','GID'):
                for col in IDENTIFIERS[row['source']].get(kind,[]):
                    value=norm(payload.get(col))
                    if not valid_id(value,cfg):continue
                    key=(row['mastergroup_id'],kind,value)
                    observed[key]=dict(mastergroup_id=key[0],approved_type=kind,identifier_value=value,target_source='*',valid_from='',valid_to='',_scope={})
                    pkey=key+(row['source'],col);provenance[pkey]=provenance.get(pkey,0)+1
    finally:db.close()
    source_sql(output,cfg_path,start,end,observed_links=list(observed.values()))
    write_csv(Path(output)/'observed_identifier_candidates.csv',['mastergroup_id','identifier_type','identifier_value','origin_source','origin_column','supporting_rows','status'],([*key,count,'source_observed_candidate_not_approved'] for key,count in sorted(provenance.items())))
    dump(Path(output)/'CANDIDATE_LOOKUP_README.md','# Source-observed identifier lookups\n\nCIN/GID values were taken from uniquely linked input records. Use these read-only SQL queries to look for corresponding source records; no approval file was created or changed. Verify cross-source identifier meaning, country scope and dates before joining results. Existing source mastergroup conflicts remain quarantined by analyse.\n\nExecute each SQL file manually in Starburst, export to your drive, transfer the files to a local folder, then run import-exports and analyse. Missing routes and the unconfirmed Counterparty catalog remain explicit.\n')

def run_signals(cohort_run,output,engine_config=None):
    cohort_run=Path(cohort_run).resolve();output=Path(output).resolve()
    if output.exists():raise ValueError('Signal output already exists; choose a new directory')
    cfg=json.loads((cohort_run/'config_used.json').read_text());manifest=json.loads((cohort_run/'run_manifest.json').read_text())
    db=sqlite3.connect((cohort_run/'cohort.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    if not db.execute("SELECT COUNT(*) FROM matches WHERE status='matched'").fetchone()[0]:db.close();raise ValueError('No uniquely linked rows. Review identifiers and rerun analyse before signal testing.')
    output.parent.mkdir(parents=True,exist_ok=True);temp=Path(tempfile.mkdtemp(prefix='.'+output.name+'-',dir=output.parent));result=None
    try:
        with (temp/'cohort_row_groups.csv').open('w',encoding='utf-8',newline='') as lineage_handle:
            lineage_writer=csv.writer(lineage_handle);lineage_writer.writerow(['source','raw_id','mastergroup_id','cohort_raw_id'])
            for source in engine.SOURCES:
                count=db.execute("SELECT COUNT(*) FROM raw_rows WHERE source=?",(source,)).fetchone()[0] if source=='counterparty' else db.execute("SELECT COUNT(*) FROM matches WHERE status='matched' AND source=?",(source,)).fetchone()[0]
                if not count:continue
                if source=='counterparty':
                    # A contradictory/non-target mapping is essential reference evidence.
                    # Filtering it to matched target groups would hide enrichment conflicts.
                    records=db.execute("SELECT r.*,NULL AS mastergroup_id FROM raw_rows r WHERE r.source=? AND r.observation_date<=? ORDER BY r.raw_id",(source,manifest['as_of']))
                else:
                    records=db.execute("SELECT r.*,m.mastergroup_id FROM raw_rows r JOIN matches m USING(source,raw_id) WHERE m.status='matched' AND r.source=? ORDER BY r.raw_id",(source,))
                header=json.loads(db.execute('SELECT columns_json FROM source_status WHERE source=?',(source,)).fetchone()[0])
                def output_rows():
                    for index,row in enumerate(records,1):
                        lineage_writer.writerow((source,index,row['mastergroup_id'],row['raw_id']))
                        payload=json.loads(row['payload']);yield [payload.get(c,'') for c in header]
                write_csv(temp/'signal_inputs'/(source+'.csv'),header,output_rows())
                dump(temp/'signal_inputs'/(source+'.metadata.json'),json.dumps({'cohort_run':str(cohort_run),'membership_policy':cfg['membership_policy'],'selection':'all in-date Counterparty mapping reference rows, including non-target/conflicting mappings' if source=='counterparty' else 'uniquely linked rows only; candidates and conflicts excluded','upstream_manifest_sha256':engine.file_hash(cohort_run/'run_manifest.json')},indent=2))
        links=[]
        for r in db.execute('SELECT * FROM approved_links'):
            kind=r['identifier_type'];source=r['target_source']
            if kind in ('CIN','GID','RELATIONSHIP_ID','CUSTOMER_ID','PVD_RELATIONSHIP_ID'):
                target='pvd' if kind=='PVD_RELATIONSHIP_ID' else source
                # This adapter tests at group-cohort level. It does not claim that
                # several CINs/GIDs identify one legal entity.
                client='COHORT_GROUP:'+r['mastergroup_id']
                links.append((target,'JOI_RELATIONSHIP_ID' if kind=='PVD_RELATIONSHIP_ID' else kind,r['identifier_value'],client,r['mastergroup_id'],r['valid_from'],r['valid_to']))
        # Source-scope conditions are not expressible in the bundled engine link CSV;
        # keep those mappings in the cohort lineage view instead of broadening them.
        permitted={(r['identifier_type'],r['identifier_value'],r['target_source']) for r in db.execute("SELECT * FROM approved_links WHERE scope_json IN ('{}','')")}
        links=[r for r in links if (('PVD_RELATIONSHIP_ID' if r[1]=='JOI_RELATIONSHIP_ID' else r[1]),r[2],r[0]) in permitted]
        write_csv(temp/'signal_inputs'/'identity_links.csv',['source','identifier_type','identifier_value','client_id','mastergroup_id','valid_from','valid_to'],links)
        engine.run(temp/'signal_inputs',temp/'results',engine_config or ROOT/'engine/config.json',manifest['as_of'])
        result=sqlite3.connect(temp/'results/bond_radar.sqlite')
        # The completed parent directory will move from staging to its final path.
        # Preserve resolvable local CSV provenance after that atomic move.
        for source in engine.SOURCES:
            result.execute('UPDATE '+ident('raw_'+source)+' SET __file=REPLACE(__file,?,?)',(str(temp),str(output)))
        result.execute('UPDATE source_manifest SET filename=REPLACE(filename,?,?)',(str(temp),str(output)))
        result.execute('UPDATE evidence_lineage SET input_file=REPLACE(input_file,?,?)',(str(temp),str(output)))
        result.execute('CREATE TABLE cohort_row_groups(source TEXT,raw_id INTEGER,mastergroup_id TEXT,cohort_raw_id INTEGER,PRIMARY KEY(source,raw_id))')
        with (temp/'cohort_row_groups.csv').open(encoding='utf-8',newline='') as handle:
            reader=csv.reader(handle);next(reader);result.executemany('INSERT INTO cohort_row_groups VALUES (?,?,?,?)',reader)
        result.executescript('''CREATE VIEW cohort_signal_evidence AS SELECT e.*,CASE WHEN COUNT(DISTINCT g.mastergroup_id)=1 AND COUNT(g.mastergroup_id)=COUNT(l.raw_id) THEN MIN(g.mastergroup_id) END AS cohort_mastergroup_id,CASE WHEN COUNT(DISTINCT g.mastergroup_id)=1 AND COUNT(g.mastergroup_id)=COUNT(l.raw_id) THEN 'unique_reviewed_cohort_group' ELSE 'shared_or_unresolved_group' END AS cohort_group_status FROM signal_evidence e JOIN evidence_lineage l ON l.evidence_id=e.evidence_id LEFT JOIN cohort_row_groups g ON g.source=l.source AND g.raw_id=l.raw_id GROUP BY e.evidence_id;''')
        cur=result.execute('SELECT * FROM cohort_signal_evidence');write_csv(temp/'results/exports/cohort_signal_evidence.csv',[d[0] for d in cur.description],cur)
        summary=[]
        for group in cfg['groups']:
            for sig in SIGNALS:
                count,pending,triggered=result.execute("SELECT COUNT(*),SUM(CASE WHEN assessment_status='needs_validation' THEN 1 ELSE 0 END),SUM(CASE WHEN triggered=1 AND stale=0 THEN 1 ELSE 0 END) FROM cohort_signal_evidence WHERE cohort_mastergroup_id=? AND signal_id=?",(norm(group['mastergroup_id']),sig)).fetchone()
                summary.append((group['mastergroup_id'],group['name'],sig,count,pending or 0,triggered or 0,'not_issuance_confirmation; inspect evidence status, dates and source coverage'))
        write_csv(temp/'results/exports/cohort_signal_summary.csv',['mastergroup_id','group_name','signal_id','evidence_items','needs_validation_items','fresh_development_candidates','qualification'],summary)
        result.commit();result.close();db.close();db=None
        def rebase(value):
            if isinstance(value,str):return value.replace(str(temp),str(output))
            if isinstance(value,list):return [rebase(v) for v in value]
            if isinstance(value,dict):return {k:rebase(v) for k,v in value.items()}
            return value
        path=temp/'results/run_manifest.json'
        dump(path,json.dumps(rebase(json.loads(path.read_text())),indent=2))
        for filename in ('source_manifest.csv','evidence_lineage.csv'):
            path=temp/'results/exports'/filename
            dump(path,path.read_text().replace(str(temp),str(output)))
        dump(temp/'cohort_link_manifest.json',json.dumps({'cohort_run':str(cohort_run),'cohort_manifest_sha256':engine.file_hash(cohort_run/'run_manifest.json'),'adapter_sha256':engine.file_hash(Path(__file__)),'membership_policy':cfg['membership_policy'],'identity_level':'COHORT_GROUP identifiers are test grouping keys, not legal-entity equivalence.'},indent=2))
        dump(temp/'README.md','# Cohort signal test\n\nOnly uniquely linked cohort rows were sent to the bundled local signal engine. Business definitions remain unverified by default. Use results/exports/cohort_signal_summary.csv and cohort_signal_evidence.csv to inspect the three groups. The cohort group is a separate lineage-derived field; original source/Counterparty mastergroups were not overwritten. Shared facility evidence remains unallocated if it spans groups. Upstream coverage and approval records remain authoritative for mapping qualifications.\n')
        temp.rename(output);logging.info('Signal tests saved: %s',output);return output
    except Exception:
        logging.exception('Failed signal test retained at %s',temp);raise
    finally:
        if db is not None:db.close()
        if result is not None:result.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    for name in ('seed-sql','source-sql'):
        p=sub.add_parser(name);p.add_argument('--start',required=True);p.add_argument('--end',required=True);p.add_argument('--out',required=True);p.add_argument('--config',default=str(ROOT/'config.json'))
        if name=='source-sql':p.add_argument('--approved')
    p=sub.add_parser('analyse');p.add_argument('--input',required=True);p.add_argument('--out',required=True);p.add_argument('--as-of',required=True);p.add_argument('--approved');p.add_argument('--config',default=str(ROOT/'config.json'))
    p=sub.add_parser('run-signals');p.add_argument('--cohort',required=True);p.add_argument('--out',required=True);p.add_argument('--engine-config')
    p=sub.add_parser('demo');p.add_argument('--out',required=True)
    p=sub.add_parser('import-exports');p.add_argument('--input',required=True);p.add_argument('--out',required=True)
    p=sub.add_parser('candidate-sql');p.add_argument('--cohort',required=True);p.add_argument('--out',required=True);p.add_argument('--start',required=True);p.add_argument('--end',required=True);p.add_argument('--config')
    args=parser.parse_args();logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    try:
        if args.command=='seed-sql':seed_sql(args.out,args.config,args.start,args.end)
        elif args.command=='source-sql':source_sql(args.out,args.config,args.start,args.end,args.approved)
        elif args.command=='analyse':analyse(args.input,args.out,args.as_of,args.config,args.approved)
        elif args.command=='run-signals':run_signals(args.cohort,args.out,args.engine_config)
        elif args.command=='import-exports':
            from import_exports import import_exports
            import_exports(args.input,args.out)
        elif args.command=='candidate-sql':candidate_sql(args.cohort,args.out,args.start,args.end,args.config)
        else:
            from demo import demo
            demo(args.out)
        return 0
    except (OSError,ValueError,KeyError,TypeError,csv.Error,sqlite3.Error) as exc:
        logging.error('%s',exc);return 2

if __name__=='__main__':sys.exit(main())
