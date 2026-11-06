#!/usr/bin/env python3
"""PORTFOLIO mode: build the Bond Radar signals for every client found in the extracts.

The cohort workflow (refresh.py / cohort.py) starts from a reviewed list of target
mastergroups. Portfolio mode starts from nothing: it takes the full-portfolio
extracts produced by portfolio_sql.py and discovers the client groups from the data:

  1. check_inputs   every part of every source is present, headers agree, required columns exist
  2. build_links    Counterparty Core (latest snapshot <= as-of) maps CIN/GID -> mastergroup for
                    ALL clients; Facilities maps relationship_id -> CIN for covenants. Links are
                    labelled with their basis (counterparty_core_latest ...), never "verified"
  3. engine         the unchanged development-2 rules (bond_radar.py) over all rows
  4. export_core    one evidence row per signal/context record with group names and lineage
  5. crr_context    Application Ratings CRR for every CIN (shared crr_row rules)
  6. alignment      SIG02 credit approval dates (shared alignment.apply)
  7. summarise      group x signal matrix, candidates, maturity windows, source coverage, workbook

Raw inputs are never modified; every run writes a fresh folder.
"""
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'engine'))
sys.path.insert(0, str(ROOT))
from bond_radar import SOURCES, day, norm, number, run as run_engine  # noqa: E402
from sig07_crr import crr_row, flag_multiple_crrs, select_context  # noqa: E402
from alignment import apply as apply_alignment  # noqa: E402

ENGINE_SOURCES = ['counterparty', 'clo', 'facilities', 'drr', 'pvd', 'kyc', 'covenants']
AR_REQUIRED = ['run_date', 'cin', 'final_crr', 'crr_scale', 'record_start_dt', 'record_end_dt', 'credit_proposal_serial_no', 'approval_dt']
SIGNAL_NAMES = {
    'SIG01': 'Material drawing on a Cat A bank facility', 'SIG02': 'New RCF, term loan or bridge (credit approval)',
    'SIG03A': 'Swap roll on maturing debt', 'SIG03B': 'New pre-hedge swap enquiry', 'SIG04': 'KYC onboarding or signatory refresh',
    'SIG06': 'Financial covenant breach or pressure', 'SIG07': 'Rating advisory request (call reports)',
    'CTX_UTIL': 'Facility utilisation context', 'CTX_CREDIT': 'Credit category and rating context'}
PART = re.compile(r'part_(\d+)_of_(\d+)\.csv$')
csv.field_size_limit(64 * 1024 * 1024)


def read_rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return [c.strip().lower() for c in (reader.fieldnames or [])], [{k.strip().lower(): v for k, v in r.items()} for r in reader]


def iter_rows(paths):
    for path in paths:
        with Path(path).open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            for line, r in enumerate(reader, 2):
                yield path, line, {k.strip().lower(): v for k, v in r.items()}


def write_csv(path, rows, fields=None):
    fields = fields or (list(rows[0]) if rows else ['note'])
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def parts(input_dir, source):
    folder = Path(input_dir) / source
    return sorted(folder.glob('*.csv')) if folder.is_dir() else []


# ── 1. Inputs ────────────────────────────────────────────────────────────────
def check_inputs(input_dir):
    """Fail early if a part is missing or headers drift: a missing part silently loses clients."""
    input_dir = Path(input_dir)
    report, problems = {}, []
    for alias in [a for s in SOURCES.values() for a in s['aliases']]:
        if (input_dir / alias).exists():
            problems.append(f'Flat file {alias} found: portfolio mode expects <source>/part_XX_of_NN.csv folders')
    for source in ENGINE_SOURCES + ['application_ratings']:
        files = parts(input_dir, source)
        info = dict(parts=len(files), rows=0, header=None, sha256={}, expected_parts=None, missing_parts=[])
        required = AR_REQUIRED if source == 'application_ratings' else SOURCES[source]['required']
        totals = set()
        for p in files:
            m = PART.search(p.name)
            if m:
                totals.add(int(m.group(2)))
            header, rows = read_rows(p)
            if info['header'] is None:
                info['header'] = header
            elif header != info['header']:
                problems.append(f'{source}: header of {p.name} differs from the first part; re-run that part with the same SQL')
            info['rows'] += len(rows)
            info['sha256'][p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
        if files:
            missing = sorted(set(required) - set(info['header'] or []))
            if missing:
                problems.append(f'{source}: required columns missing {missing}')
            if len(totals) > 1:
                problems.append(f'{source}: parts come from different splits {sorted(totals)}')
            elif totals:
                n = totals.pop()
                present = {int(PART.search(p.name).group(1)) for p in files if PART.search(p.name)}
                info['expected_parts'] = n
                info['missing_parts'] = sorted(set(range(1, n + 1)) - present)
                if info['missing_parts']:
                    problems.append(f'{source}: missing parts {info["missing_parts"]} of {n}')
        info.pop('header')
        report[source] = info
    if not report['counterparty']['parts']:
        problems.append('counterparty: no parts. Counterparty Core is required to discover client groups')
    return report, problems


# ── 2. Identity links ────────────────────────────────────────────────────────
def build_links(input_dir, as_of, config, out_path, extra_links=None):
    """CIN/GID -> mastergroup from the latest Counterparty Core snapshot <= as-of, for every client."""
    cfg = config['counterparty']
    active = set(cfg['active_statuses'])
    invalid = set(cfg['invalid_mastergroups'])
    cin_latest, gid_latest, group_dim = {}, {}, {}
    for _, _, r in iter_rows(parts(input_dir, 'counterparty')):
        observed = day(r.get('run_date'))
        if not observed or observed > as_of:
            continue
        cin, gid, mg = norm(r.get('customer_relationship_cin_identifier')), norm(r.get('customer_relationship_gid_identifier')), norm(r.get('mastergroup_esr_identifier'))
        status = norm(r.get('customer_relationship_lifecycle_status_code'))
        if mg and mg not in invalid:
            dim = group_dim.get(mg)
            if dim is None or observed >= dim['observed']:
                group_dim[mg] = dict(mastergroup_id=mg, group_name=(r.get('mastergroup_name') or '').strip(), observed=observed,
                                     business_line=norm(r.get('mastergroup_business_line_code')) or '', designation=(r.get('mastergroup_designation_name') or '').strip(),
                                     principal_country=norm(r.get('mastergroup_principal_country_code')) or '', sector=(r.get('mastergroup_industry_classification_sector_name') or '').strip(),
                                     supergroup_id=norm(r.get('mastergroup_supergroup_identifier')) or '', supergroup_name=(r.get('mastergroup_supergroup_name') or '').strip(),
                                     group_lifecycle=norm(r.get('mastergroup_lifecycle_status_code')) or '')
        ok = (status in active or status is None and cfg['allow_blank_status']) and mg and mg not in invalid
        for key, store, value in ((cin, cin_latest, mg), (gid, gid_latest, (cin, mg))):
            if not key:
                continue
            seen = store.get(key)
            if seen is None or observed > seen[0]:
                store[key] = [observed, set()]
            if store[key][0] == observed and ok:
                store[key][1].add(value)
    links = []
    for cin, (observed, mgs) in cin_latest.items():
        for mg in sorted(mgs):
            links.append(dict(source='*', identifier_type='CIN', identifier_value=cin, client_id='CIN:' + cin, mastergroup_id=mg,
                              valid_from='', valid_to='', link_basis='counterparty_core_latest'))
    for gid, (observed, pairs) in gid_latest.items():
        for cin, mg in sorted(pairs, key=lambda x: (x[0] or '', x[1])):
            links.append(dict(source='*', identifier_type='GID', identifier_value=gid, client_id='CIN:' + cin if cin else 'GID:' + gid,
                              mastergroup_id=mg, valid_from='', valid_to='', link_basis='counterparty_core_latest'))
    cin_map = {cin: set(mgs) for cin, (_, mgs) in cin_latest.items() if mgs}
    # Second route, only where Counterparty Core has no mapping for a CIN: the CIN -> mastergroup
    # association the source systems record themselves (CLO rct_mastergroup_id, DRR drr_mastergroup_id),
    # from each CIN's latest observation and only when unambiguous. Labelled as a development link.
    native = {}
    for source, cin_col, mg_col, date_col, name_col in (('clo', 'obligor_cin', 'rct_mastergroup_id', 'run_date', 'rct_mastergroup_name'),
                                                        ('drr', 'cin', 'drr_mastergroup_id', 'reporting_date', None)):
        for _, _, r in iter_rows(parts(input_dir, source)):
            cin, mg, observed = norm(r.get(cin_col)), norm(r.get(mg_col)), day(r.get(date_col))
            if not cin or not mg or mg in invalid or not observed or observed > as_of:
                continue
            seen = native.get(cin)
            if seen is None or observed > seen[0]:
                native[cin] = [observed, set()]
            if native[cin][0] == observed:
                native[cin][1].add(mg)
            if name_col and mg not in group_dim and (r.get(name_col) or '').strip():
                group_dim[mg] = dict(mastergroup_id=mg, group_name=r[name_col].strip(), observed=observed, business_line='', designation='',
                                     principal_country='', sector='', supergroup_id='', supergroup_name='', group_lifecycle='', name_source=source)
    native_links = 0
    for cin, (observed, mgs) in native.items():
        if cin in cin_map or len(mgs) != 1:
            continue
        mg = next(iter(mgs))
        cin_map[cin] = {mg}
        links.append(dict(source='*', identifier_type='CIN', identifier_value=cin, client_id='CIN:' + cin, mastergroup_id=mg,
                          valid_from='', valid_to='', link_basis='native_source_cin_mastergroup'))
        native_links += 1
    # Covenants carry relationship_id only. Facilities pairs relationship_id with CIN, giving a
    # development route relationship -> CIN -> mastergroup. Applied to covenants only.
    rel_cins = defaultdict(set)
    for _, _, r in iter_rows(parts(input_dir, 'facilities')):
        rel, cin = norm(r.get('relationship_id')), norm(r.get('cin'))
        if rel and cin:
            rel_cins[rel].add(cin)
    rel_links = 0
    for rel, cins in rel_cins.items():
        mgs = set().union(*(cin_map.get(c, set()) for c in cins))
        if len(mgs) == 1:
            client = 'CIN:' + next(iter(cins)) if len(cins) == 1 else 'REL:' + rel
            links.append(dict(source='covenants', identifier_type='RELATIONSHIP_ID', identifier_value=rel, client_id=client,
                              mastergroup_id=next(iter(mgs)), valid_from='', valid_to='', link_basis='facilities_relationship_to_cin+counterparty_core_latest'))
            rel_links += 1
    extra = 0
    if extra_links:
        # Reviewed mappings (e.g. PVD relationship -> mastergroup) supplied by the user, in identity_links format.
        _, reviewed = read_rows(extra_links)
        for r in reviewed:
            links.append(dict(source=r['source'], identifier_type=r['identifier_type'], identifier_value=r['identifier_value'], client_id=r['client_id'],
                              mastergroup_id=r['mastergroup_id'], valid_from=r.get('valid_from', ''), valid_to=r.get('valid_to', ''),
                              link_basis=r.get('link_basis') or 'reviewed_extra_link'))
            if r['identifier_type'].upper() == 'CIN' and norm(r['mastergroup_id']):
                cin_map.setdefault(norm(r['identifier_value']), set()).add(norm(r['mastergroup_id']))
            extra += 1
    write_csv(out_path, links, ['source', 'identifier_type', 'identifier_value', 'client_id', 'mastergroup_id', 'valid_from', 'valid_to', 'link_basis'])
    stats = dict(cins=len(cin_latest), cins_linked=sum(1 for v in cin_latest.values() if v[1]), cins_ambiguous=sum(1 for v in cin_latest.values() if len(v[1]) > 1),
                 gids=len(gid_latest), relationships_linked=rel_links, cins_linked_by_native_source=native_links, reviewed_extra_links=extra, groups=len(group_dim), links_written=len(links))
    return cin_map, group_dim, stats


# ── 3. Configuration ─────────────────────────────────────────────────────────
def prepare_config(base_config, input_dir, as_of, out_dir, fx_from_clo=False):
    config = json.loads(Path(base_config).read_text())
    fx_used = []
    if fx_from_clo:
        ref = Path(input_dir) / 'reference' / 'clo_fx_reference.csv'
        if not ref.exists():
            raise ValueError('--fx-from-clo needs reference/clo_fx_reference.csv (03_reference/clo_fx_reference.sql)')
        _, rows = read_rows(ref)
        by_date = defaultdict(dict)
        for r in rows:
            d, ccy, med = day(r.get('run_date')), norm(r.get('currency')), number(r.get('fx_to_usd_median'))
            if d and d <= as_of and ccy and med and med > 0:
                by_date[d][ccy] = med
        usable = sorted(d for d, rates in by_date.items() if 'EUR' in rates)
        if not usable:
            raise ValueError('CLO FX reference has no EUR rate on or before the as-of date')
        d = usable[-1]
        eur = by_date[d]['EUR']
        rates = {ccy: str(round(med / eur, 10)) for ccy, med in by_date[d].items() if ccy != 'EUR'}
        m = config['sig01']['materiality']
        m['fx_to_threshold_currency'] = rates
        m['fx_note'] = f'UNVALIDATED: derived from CLO instrument_currency_fx_to_usd medians on {d} (ccy->EUR = median(ccy)/median(EUR)). Agree an FX source before relying on it.'
        fx_used = [dict(fx_date=d, currency=c, eur_per_unit=v) for c, v in sorted(rates.items())]
    path = Path(out_dir) / 'config_portfolio.json'
    path.write_text(json.dumps(config, indent=2) + '\n')
    return path, config, fx_used


# ── 4. Core export ───────────────────────────────────────────────────────────
EXPORT_FIELDS = ['client', 'client_id', 'mastergroup_id', 'group_name', 'signal_id', 'signal_name', 'source', 'component', 'review_type',
                 'assessment_status', 'business_trigger', 'above_70_for_testing', 'recent_creation_for_testing', 'material_drawing_for_testing',
                 'covenant_pressure_for_testing', 'observation_date', 'event_date', 'assessment_date', 'export_date', 'stale', 'facility_ids',
                 'clo_sub_limit_ids', 'clo_facility_references', 'drr_uids', 'pvd_keys', 'cins', 'gids', 'source_countries', 'product_codes',
                 'limit_categories', 'rating_values', 'facility_grade_codes', 'advised_ind_values', 'source_creation_dates', 'metric',
                 'metric_value', 'previous_metric_value', 'current_drawn', 'previous_drawn', 'utilisation_amount', 'approved_limit', 'currency',
                 'proposed_limit', 'source_currencies', 'threshold_percent', 'event_age_days', 'event_lookback_days', 'previous_observation_date',
                 'comparison_gap_days', 'current_drawn_imputed_zero', 'previous_drawn_imputed_zero', 'drawn_field', 'limit_category',
                 'limit_category_basis', 'cat_a_eligible', 'materiality_status', 'materiality_threshold', 'drawing_in_threshold_currency',
                 'hsbc_participation_share_percent', 'inferred_total_drawing', 'event_basis', 'credit_proposal_serial_no', 'credit_approval_date',
                 'credit_approval_source', 'approval_matches_creation_date', 'covenant_headroom_turns', 'covenant_breach_for_testing',
                 'conflicting_fields', 'validation_reason', 'mapping_status', 'cohort_mapping_status', 'source_table', 'source_record_references',
                 'previous_source_record_references', 'record_key', 'evidence_id',
                 # CRR context columns (Application Ratings rows; blank for other sources)
                 'crr', 'crr_raw', 'crr_scale', 'previous_crr', 'proposed_crr', 'approved_crr', 'proposed_manual_crr', 'overriden_crr',
                 'approval_date', 'record_start_date', 'record_end_raw', 'latest_record', 'latest_approved_appl_flag', 'multiple_crrs_for_cin',
                 'source_system_unique_id', 'customer_id', 'relationship_id', 'customer_name', 'original_mastergroup_name', 'details_json']


def export_core(engine_dir, out_csv, group_dim, as_of, export_date, cin_map=None):
    db = sqlite3.connect((Path(engine_dir) / 'bond_radar.sqlite').resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    columns = {s: [r[1] for r in db.execute(f'PRAGMA table_info("raw_{s}")')] for s in SOURCES}

    def raw(source, raw_id):
        r = db.execute(f'SELECT * FROM "raw_{source}" WHERE __id=?', (raw_id,)).fetchone()
        return dict(r) if r else {}

    def ref(source, raw_id):
        r = db.execute(f'SELECT __file, __line FROM "raw_{source}" WHERE __id=?', (raw_id,)).fetchone()
        return f'{source}/{Path(r[0]).name}:record {r[1]}' if r else ''

    def values(rows, *cols):
        return ' | '.join(sorted({str(r.get(c)).strip() for r in rows for c in cols if norm(r.get(c)) is not None}))

    count = 0
    with Path(out_csv).open('w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=EXPORT_FIELDS)
        w.writeheader()
        for e in db.execute('SELECT * FROM signal_evidence ORDER BY mastergroup_id, signal_id, source, record_key'):
            e = dict(e)
            d = json.loads(e['details_json'] or '{}')
            source = e['source']
            ids = json.loads(e['source_rows'] or '[]')
            rows = [raw(source, i) for i in ids]
            obs = db.execute('SELECT payload FROM observations WHERE source=? AND record_key=? AND observation_date=?', (source, e['record_key'], e['observation_date'])).fetchone()
            conflicts = json.loads(obs[0]).get('__conflicts', []) if obs else []
            sig, comp, status = e['signal_id'], e['component'], e['assessment_status']
            high = d.get('threshold_exceeded_for_testing') if comp == 'utilisation' else None
            recent = (d.get('event_age_days') is not None and 0 <= d['event_age_days'] <= d['event_lookback_days'] and status != 'unavailable') if sig == 'SIG02' else None
            material = d.get('material_for_testing') if sig == 'SIG01' else None
            pressure = d.get('pressure_for_testing') if comp == 'financial_covenant' else None
            # A SIG01 candidate needs both parts of the definition: material (> EUR 50m) AND on a Cat A facility.
            sig01_candidate = bool(material) and d.get('cat_a_eligible') is True
            review = ('unavailable' if status == 'unavailable' else 'material_drawing_for_testing' if sig01_candidate
                      else 'material_drawing_not_cat_a' if material else 'covenant_pressure_for_testing' if pressure
                      else 'recent_approval_for_testing' if recent else 'utilisation_above_70_context' if high else 'credit_category_context' if sig == 'CTX_CREDIT'
                      else 'drawing_comparison' if sig == 'SIG01' else 'other_evidence_for_review')
            mg = e['mastergroup_id'] or ''
            group_basis = 'portfolio_counterparty_link' if mg else 'no_group_link'
            if not mg and cin_map and str(e['client_id'] or '').startswith('CIN:'):
                # The engine found an identity link for this record's CIN but the source carried no
                # group (e.g. a CLO row with a blank mastergroup). Use the link only when unambiguous.
                linked = cin_map.get(e['client_id'][4:], set())
                if len(linked) == 1:
                    mg, group_basis = next(iter(linked)), 'group_from_identity_link'
            dim = group_dim.get(mg, {})
            name = dim.get('group_name') or values(rows, 'rct_mastergroup_name') or ''
            w.writerow(dict(
                client=name, client_id=e['client_id'], mastergroup_id=mg, group_name=name, signal_id=sig, signal_name=SIGNAL_NAMES.get(sig, sig),
                source=source, component=comp, review_type=review, assessment_status=status, business_trigger=e['triggered'] if e['triggered'] is not None else '',
                above_70_for_testing=high, recent_creation_for_testing=recent, material_drawing_for_testing=material, covenant_pressure_for_testing=pressure,
                observation_date=e['observation_date'], event_date=e['event_date'] or '', assessment_date=e['assessment_date'], export_date=export_date,
                stale=bool(e['stale']), facility_ids=values(rows, 'facility_id'), clo_sub_limit_ids=values(rows, 'sub_lim_id'),
                clo_facility_references=values(rows, 'rct_facility_ref'), drr_uids=values(rows, 'drr_uid'), pvd_keys=values(rows, 'joi_key'),
                cins=values(rows, 'cin', 'obligor_cin'), gids=values(rows, 'gid', 'rct_gid'), source_countries=values(rows, 'country_code', 'rpt_facility_country_code'),
                product_codes=values(rows, 'product_code', 'facility_type_code', 'local_product_type_lbs'),
                limit_categories=values(rows, 'limit_cat', 'drr_fac_category', 'joi_facility_category'), rating_values=values(rows, 'drr_crr'),
                facility_grade_codes=values(rows, 'facility_grade_code'), advised_ind_values=values(rows, 'advised_ind'),
                source_creation_dates=values(rows, 'facility_creation_date'), metric=e['metric_name'], metric_value=e['value'],
                previous_metric_value=e['previous_value'], current_drawn=d.get('current_drawn'), previous_drawn=e['previous_value'] if sig == 'SIG01' else '',
                utilisation_amount=d.get('numerator') if comp == 'utilisation' else '', approved_limit=e['denominator'],
                currency=e['currency'] or d.get('currency', ''), proposed_limit=d.get('limit'),
                source_currencies=values(rows, 'facility_ccy', 'facility_currency', 'approved_limit_ccy', 'utilisation_ccy'),
                threshold_percent=d.get('threshold_percent'), event_age_days=d.get('event_age_days'), event_lookback_days=d.get('event_lookback_days'),
                previous_observation_date=d.get('previous_observation_date'), comparison_gap_days=d.get('comparison_gap_days'),
                current_drawn_imputed_zero=d.get('current_missing_imputed_zero'), previous_drawn_imputed_zero=d.get('previous_missing_imputed_zero'),
                drawn_field=d.get('drawn_field') if sig == 'SIG01' else '', limit_category=d.get('limit_category') if sig == 'SIG01' else '',
                limit_category_basis=d.get('limit_category_basis') if sig == 'SIG01' else '', cat_a_eligible=d.get('cat_a_eligible') if sig == 'SIG01' else '',
                materiality_status=d.get('materiality_status') if sig == 'SIG01' else '',
                materiality_threshold=f"{d.get('threshold_currency')} {d.get('threshold_amount')}" if sig == 'SIG01' else '',
                drawing_in_threshold_currency=d.get('drawing_in_threshold_currency') if sig == 'SIG01' else '',
                hsbc_participation_share_percent=d.get('hsbc_participation_share_percent') if sig == 'SIG01' else '',
                inferred_total_drawing=d.get('inferred_total_drawing') if sig == 'SIG01' else '',
                event_basis=d.get('event_basis') if sig == 'SIG02' else '', credit_proposal_serial_no=d.get('credit_proposal_serial_no') if sig == 'SIG02' else '',
                credit_approval_date='', credit_approval_source='', approval_matches_creation_date='',
                covenant_headroom_turns=d.get('headroom_turns') if sig == 'SIG06' else '', covenant_breach_for_testing=d.get('breach_for_testing') if sig == 'SIG06' else '',
                conflicting_fields=' | '.join(conflicts), validation_reason=e['reason'], mapping_status=e['mapping_status'],
                cohort_mapping_status=group_basis, source_table=SOURCES[source]['table'],
                source_record_references=' | '.join(ref(source, i) for i in ids),
                previous_source_record_references=' | '.join(ref(source, i) for i in d.get('previous_source_rows') or []),
                record_key=e['record_key'], evidence_id=e['evidence_id'], details_json=e['details_json']))
            count += 1
    db.close()
    return count


# ── 5. CRR context for every client ──────────────────────────────────────────
def crr_context(input_dir, as_of, cin_map, group_dim):
    raw = []
    for path, line, r in iter_rows(parts(input_dir, 'application_ratings')):
        r.update(_input_file=f'application_ratings/{Path(path).name}', _input_record=str(line))
        raw.append(r)
    if not raw:
        return [], {}
    selected, counts = select_context(raw, as_of)
    rows = []
    for r in selected:
        mgs = cin_map.get(norm(r['cin']), set())
        mg = next(iter(mgs)) if len(mgs) == 1 else None
        name = group_dim.get(mg, {}).get('group_name', '') if mg else (r.get('mastergroup_name') or '')
        row = crr_row(r, name, mg, len(mgs) == 1, as_of, EXPORT_FIELDS, mapping=('counterparty_core_latest', 'unresolved_counterparty_cin'),
                      unresolved_reason='cin_group_link_unresolved')
        row.update(group_name=name, client_id='CIN:' + (norm(r['cin']) or ''), cohort_mapping_status='portfolio_counterparty_link' if mg else 'no_group_link')
        rows.append(row)
    flag_multiple_crrs(rows)
    return rows, counts


# ── 6. Maturity windows (DASH03) ─────────────────────────────────────────────
def maturity_windows(engine_dir, as_of):
    """Facilities and CLO maturities within 24 months, at source grain. Counts only; no cross-currency totals."""
    db = sqlite3.connect((Path(engine_dir) / 'bond_radar.sqlite').resolve().as_uri() + '?mode=ro', uri=True)
    out = []
    latest = '''SELECT * FROM (SELECT o.*, ROW_NUMBER() OVER (PARTITION BY source, record_key ORDER BY observation_date DESC) rn
                FROM observations o WHERE source IN ('facilities','clo')) WHERE rn = 1'''
    fields = {'facilities': ['loan_maturity_dt', 'final_loan_maturity_dt', 'facility_expiry_dt'], 'clo': ['facility_maturity_date']}
    for source, record_key, observed, client, mg, status, payload, *_ in db.execute(latest):
        p = json.loads(payload)
        if p.get('__conflicts'):
            continue
        basis = next((f for f in fields[source] if day(p.get(f))), None)
        if not basis:
            continue
        matures = day(p[basis])
        days_left = (date.fromisoformat(matures) - date.fromisoformat(as_of)).days
        if not 0 <= days_left <= 730:
            continue
        out.append(dict(mastergroup_id=mg or '', source=source, facility=p.get('facility_id') or p.get('sub_lim_id') or '', product=p.get('product_code') or p.get('local_product_type_lbs') or '',
                        maturity_date=matures, maturity_basis=basis, days_to_maturity=days_left, window='<12m' if days_left <= 365 else '12-24m',
                        limit=p.get('proposed_limit') if source == 'facilities' else p.get('facility_limit_amount'),
                        currency=p.get('facility_ccy') if source == 'facilities' else p.get('facility_currency'),
                        limit_category=p.get('limit_cat') or '', observation_date=observed, record_key=record_key))
    db.close()
    return out


# ── 7. Summaries ─────────────────────────────────────────────────────────────
def is_true(v):
    return v is True or str(v) == 'True'


def summarise(rows, maturity, group_dim, business_lines=None):
    by_group = defaultdict(list)
    for r in rows:
        if r['mastergroup_id']:
            by_group[r['mastergroup_id']].append(r)
    mat = defaultdict(Counter)
    for m in maturity:
        if m['mastergroup_id']:
            mat[m['mastergroup_id']][m['window']] += 1
    matrix, candidates = [], []
    for mg in sorted(set(by_group) | set(mat)):
        ev = by_group.get(mg, [])
        dim = group_dim.get(mg, {})
        if business_lines and dim.get('business_line') not in business_lines:
            continue
        sig = lambda s: [r for r in ev if r['signal_id'] == s]
        s1, s2, s6, cu, cc = sig('SIG01'), sig('SIG02'), sig('SIG06'), sig('CTX_UTIL'), sig('CTX_CREDIT')
        cand = ([r for r in s1 if is_true(r['material_drawing_for_testing']) and is_true(r['cat_a_eligible'])] + [r for r in s2 if is_true(r['recent_creation_for_testing'])]
                + [r for r in s6 if is_true(r['covenant_pressure_for_testing']) or is_true(r['covenant_breach_for_testing'])])
        util = [float(r['metric_value']) for r in cu if r['assessment_status'] == 'needs_validation' and r['metric_value'] not in ('', None)]
        drawn_no_prior = sorted([r for r in s1 if not r['metric_value'] and number(r['current_drawn']) and number(r['current_drawn']) > 0],
                                key=lambda r: -float(r['current_drawn']))
        approvals = sorted(r['credit_approval_date'] or r['event_date'] for r in s2 if is_true(r['recent_creation_for_testing']))
        signals_firing = len({r['signal_id'] for r in cand})
        row = dict(mastergroup_id=mg, group_name=dim.get('group_name') or (ev[0]['group_name'] if ev else ''), business_line=dim.get('business_line', ''),
                   principal_country=dim.get('principal_country', ''), sector=dim.get('sector', ''),
                   signals_with_candidates=signals_firing, candidate_records=len(cand),
                   sig01_comparisons=len(s1), sig01_material=sum(is_true(r['material_drawing_for_testing']) for r in s1),
                   sig01_material_cat_a=sum(is_true(r['material_drawing_for_testing']) and is_true(r['cat_a_eligible']) for r in s1),
                   sig01_largest_drawn_without_prior=f"{drawn_no_prior[0]['currency']} {float(drawn_no_prior[0]['current_drawn']):,.0f}" if drawn_no_prior else '',
                   sig02_contexts=len(s2), sig02_recent_approvals=len(approvals), sig02_newest_approval=approvals[-1] if approvals else '',
                   sig04_cases=len(sig('SIG04')), sig06_tests=len(s6), sig06_pressure=sum(is_true(r['covenant_pressure_for_testing']) for r in s6),
                   sig06_breach=sum(is_true(r['covenant_breach_for_testing']) for r in s6),
                   ctx_util_usable=len(util), ctx_util_over_70=sum(is_true(r['above_70_for_testing']) for r in cu), ctx_util_peak_pct=round(max(util), 2) if util else '',
                   crr_populated=sum(1 for r in cc if r['component'] == 'crr_context' and r.get('crr')),
                   crr_values=' | '.join(sorted({r['crr'] for r in cc if r.get('crr')})),
                   maturity_lt_12m=mat[mg]['<12m'], maturity_12_24m=mat[mg]['12-24m'],
                   sources=' | '.join(sorted({r['source'] for r in ev})), evidence_records=len(ev),
                   unavailable_records=sum(r['assessment_status'] == 'unavailable' for r in ev))
        matrix.append(row)
        for r in cand:
            candidates.append(dict(mastergroup_id=mg, group_name=row['group_name'], business_line=row['business_line'], signal_id=r['signal_id'],
                                   signal_name=r['signal_name'], review_type=r['review_type'], identifier=r['clo_sub_limit_ids'] or r['facility_ids'],
                                   product_codes=r['product_codes'], event_date=r['credit_approval_date'] or r['event_date'], metric_value=r['metric_value'],
                                   currency=r['currency'], proposed_limit=r['proposed_limit'], materiality_status=r['materiality_status'],
                                   validation_reason=r['validation_reason'], evidence_id=r['evidence_id'], source_record_references=r['source_record_references']))
    # Development ordering, not a score: firing signals, then candidates, then near maturities, then evidence volume.
    matrix.sort(key=lambda r: (-r['signals_with_candidates'], -r['candidate_records'], -r['maturity_lt_12m'], -r['evidence_records'], r['group_name']))
    for i, r in enumerate(matrix, 1):
        r['development_order'] = i
    order = {r['mastergroup_id']: r['development_order'] for r in matrix}
    candidates.sort(key=lambda r: (order.get(r['mastergroup_id'], 1e9), r['signal_id'], r['event_date']))
    return matrix, candidates


def coverage(input_report, engine_dir, rows):
    db = sqlite3.connect((Path(engine_dir) / 'bond_radar.sqlite').resolve().as_uri() + '?mode=ro', uri=True)
    out = []
    for s in ENGINE_SOURCES + ['application_ratings']:
        info = input_report.get(s, {})
        ev = [r for r in rows if r['source'] == s]
        rec = dict(source=s, parts=info.get('parts', 0), input_rows=info.get('rows', 0), evidence_records=len(ev),
                   evidence_with_group=sum(1 for r in ev if r['mastergroup_id']), groups_with_evidence=len({r['mastergroup_id'] for r in ev if r['mastergroup_id']}))
        if s in SOURCES:
            rec['observations'] = db.execute('SELECT COUNT(*) FROM observations WHERE source=?', (s,)).fetchone()[0]
            dates = db.execute('SELECT MIN(observation_date), MAX(observation_date) FROM observations WHERE source=?', (s,)).fetchone()
            rec['observation_dates'] = f'{dates[0]} .. {dates[1]}' if dates[0] else ''
        rec['group_link_rate'] = f"{rec['evidence_with_group'] / rec['evidence_records']:.0%}" if rec['evidence_records'] else ''
        out.append(rec)
    db.close()
    return out


def write_workbook(path, sheets):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        return False
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows, note in sheets:
        ws = wb.create_sheet(title)
        ws.append([note])
        ws['A1'].font = Font(name='Arial', italic=True, size=9)
        ws.append([])
        fields = list(rows[0]) if rows else ['note']
        ws.append(fields)
        for c in ws[3]:
            c.font = Font(name='Arial', bold=True, color='FFFFFF', size=10)
            c.fill = PatternFill('solid', fgColor='111111')
        for r in rows:
            ws.append([r.get(f) for f in fields])
        if not rows:
            ws.append(['No records'])
        ws.freeze_panes = 'A4'
        for i, f in enumerate(fields, 1):
            ws.column_dimensions[ws.cell(row=3, column=i).column_letter].width = min(max(12, len(f) + 2), 40)
    wb.save(path)
    return True


def run(input_dir, out, as_of, base_config, fx_from_clo=False, business_lines=None, extra_links=None):
    input_dir, out = Path(input_dir).resolve(), Path(out).resolve()
    as_of = day(as_of)
    if not as_of:
        raise ValueError('Use an explicit --as-of date (YYYY-MM-DD)')
    if out.exists():
        raise ValueError(f'{out} exists; choose a new run folder')
    out.mkdir(parents=True)
    started = datetime.now(timezone.utc).isoformat()
    report, problems = check_inputs(input_dir)
    (out / 'INPUT_CHECK.json').write_text(json.dumps(dict(problems=problems, sources=report), indent=2) + '\n')
    if problems:
        raise ValueError('Input check failed (see INPUT_CHECK.json):\n- ' + '\n- '.join(problems))
    config_path, config, fx_used = prepare_config(base_config, input_dir, as_of, out, fx_from_clo)
    cin_map, group_dim, link_stats = build_links(input_dir, as_of, config, out / 'identity_links_portfolio.csv', extra_links)
    run_engine(input_dir, out / 'engine', config_path, as_of, out / 'identity_links_portfolio.csv')
    core = out / 'core_evidence.csv'
    n_core = export_core(out / 'engine', core, group_dim, as_of, as_of, cin_map)
    _, core_rows = read_rows(core)
    crr_rows, crr_counts = crr_context(input_dir, as_of, cin_map, group_dim)
    combined = out / 'combined_before_approval_dates.csv'
    write_csv(combined, core_rows + crr_rows, EXPORT_FIELDS)
    final = out / 'BOND_RADAR_SIGNAL_EVIDENCE.csv'
    if parts(input_dir, 'application_ratings'):
        aligned = apply_alignment(combined, input_dir / 'application_ratings', final, as_of)
    else:
        final.write_bytes(combined.read_bytes())
        aligned = dict(rows=len(core_rows), sig02_approval_linking={'no_application_ratings_input': 1})
    _, rows = read_rows(final)
    maturity = maturity_windows(out / 'engine', as_of)
    for m in maturity:
        m['group_name'] = group_dim.get(m['mastergroup_id'], {}).get('group_name', '')
    matrix, candidates = summarise(rows, maturity, group_dim, set(business_lines) if business_lines else None)
    cov = coverage(report, out / 'engine', rows)
    groups = sorted(({k: v for k, v in d.items() if k != 'observed'} for d in group_dim.values()), key=lambda d: d['mastergroup_id'])
    write_csv(out / 'GROUP_SIGNAL_MATRIX.csv', matrix)
    write_csv(out / 'CANDIDATES.csv', candidates)
    write_csv(out / 'MATURITY_WINDOWS.csv', maturity)
    write_csv(out / 'SOURCE_COVERAGE.csv', cov)
    write_csv(out / 'GROUPS.csv', groups)
    if fx_used:
        write_csv(out / 'FX_USED.csv', fx_used)
    by_signal = Counter(r['signal_id'] for r in rows)
    summary = dict(as_of=as_of, started_utc=started, finished_utc=datetime.now(timezone.utc).isoformat(), rule_version=config['rule_version'],
                   records=len(rows), core_records=n_core, crr_records=len(crr_rows), by_signal=dict(by_signal),
                   groups_in_counterparty=len(group_dim), groups_with_evidence=len({r['mastergroup_id'] for r in rows if r['mastergroup_id']}),
                   records_without_group=sum(1 for r in rows if not r['mastergroup_id']), candidate_records=len(candidates),
                   groups_with_candidates=sum(1 for r in matrix if r['signals_with_candidates']), maturity_windows=len(maturity),
                   links=link_stats, crr_selection=crr_counts, sig02_approval_linking=aligned['sig02_approval_linking'],
                   fx_from_clo=bool(fx_used), business_line_filter=sorted(business_lines) if business_lines else None,
                   qualification='Development evidence for the whole portfolio. Group links come from Counterparty Core (latest snapshot) and are not reviewed approvals. No business trigger is confirmed.')
    (out / 'RUN_SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n')
    write_workbook(out / 'PORTFOLIO_SIGNALS.xlsx', [
        ('Group matrix', matrix, 'One row per mastergroup. development_order is a transparent ordering (firing signals, candidates, near maturities), not a score.'),
        ('Candidates', candidates, 'Development test candidates: SIG01 material drawing, SIG02 approved within 90 days, SIG06 covenant pressure/breach. Not confirmed triggers.'),
        ('Maturity windows', maturity, 'Facilities and CLO maturities within 24 months (DASH03). Native currency; no totals across currencies.'),
        ('Source coverage', cov, 'Rows per source, evidence produced and share linked to a mastergroup.'),
        ('Groups', groups, 'Group dimension from Counterparty Core (latest snapshot <= as-of).')])
    write_review(out, summary, matrix, cov)
    combined.unlink()
    return summary


def write_review(out, s, matrix, cov):
    top = matrix[:15]
    lines = [f"# Portfolio run review — as of {s['as_of']}", '',
             'Development evidence for every client found in the portfolio extracts. Group links come from Counterparty Core '
             '(latest snapshot on or before the as-of date) and are labelled `counterparty_core_latest`; they are not reviewed approvals. '
             'No business trigger is confirmed.', '',
             '## Headline', '',
             '| Measure | Value |', '|---|---:|',
             f"| Records (signal evidence + context) | {s['records']} |",
             f"| Mastergroups in Counterparty Core | {s['groups_in_counterparty']} |",
             f"| Mastergroups with evidence | {s['groups_with_evidence']} |",
             f"| Groups with at least one test candidate | {s['groups_with_candidates']} |",
             f"| Candidate records | {s['candidate_records']} |",
             f"| Maturities within 24 months | {s['maturity_windows']} |",
             f"| Records without a group link | {s['records_without_group']} |", '',
             '## Records by signal', '', '| Signal | Records |', '|---|---:|']
    lines += [f'| {k} | {v} |' for k, v in sorted(s['by_signal'].items())]
    lines += ['', '## First groups in development order', '',
              '| # | Group | Signals firing | Candidates | SIG02 recent approvals | SIG01 material | Peak util. | Maturities <12m |', '|---:|---|---:|---:|---:|---:|---:|---:|']
    lines += [f"| {r['development_order']} | {r['group_name'] or r['mastergroup_id']} | {r['signals_with_candidates']} | {r['candidate_records']} | "
              f"{r['sig02_recent_approvals']} | {r['sig01_material']} | {r['ctx_util_peak_pct']} | {r['maturity_lt_12m']} |" for r in top]
    lines += ['', '## Source coverage', '', '| Source | Parts | Input rows | Evidence | Linked to a group |', '|---|---:|---:|---:|---:|']
    lines += [f"| {c['source']} | {c['parts']} | {c['input_rows']} | {c['evidence_records']} | {c['group_link_rate']} |" for c in cov]
    lines += ['', '## Identity links', '', '```', json.dumps(s['links'], indent=2), '```', '',
              'Files: `BOND_RADAR_SIGNAL_EVIDENCE.csv` (all records), `GROUP_SIGNAL_MATRIX.csv`, `CANDIDATES.csv`, `MATURITY_WINDOWS.csv`, '
              '`SOURCE_COVERAGE.csv`, `GROUPS.csv`, `PORTFOLIO_SIGNALS.xlsx`, `INPUT_CHECK.json`, `RUN_SUMMARY.json`, `engine/` (SQLite, lineage, quality report).']
    (out / 'REVIEW.md').write_text('\n'.join(lines) + '\n')
