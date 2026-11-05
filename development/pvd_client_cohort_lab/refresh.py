#!/usr/bin/env python3
"""Small current-snapshot SQL packs and offline signal tests. No database connection."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, timedelta
import json
from pathlib import Path
import re
import sqlite3
import sys

import cohort
from import_exports import import_exports, inspect_export

ROOT = Path(__file__).resolve().parent
GROUP_FIELDS = dict(cohort.GROUP_FIELDS, pvd='joi_relationship_id')


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        if any(None in row or None in row.values() for row in rows):
            raise ValueError(f'Malformed CSV: {path}')
        return reader.fieldnames, rows


def write_csv(path, columns, rows):
    cohort.write_csv(path, columns, ([r.get(c, '') for c in columns] for r in rows))


def select_current(source, rows, as_of, clo_dates=()):
    """Keep source snapshots, not the latest surviving row of each old facility."""
    stats = Counter(input_rows=len(rows))
    unique, seen = [], set()
    spec = cohort.engine.SOURCES[source]
    for row in rows:
        fingerprint = json.dumps(row, sort_keys=True)
        if fingerprint in seen:
            stats['exact_duplicates_removed'] += 1
            continue
        seen.add(fingerprint)
        observed = cohort.day(row.get(spec['date']))
        loads = [cohort.day(row.get('run_date'))]
        if source == 'pvd':
            loads += [cohort.day(row.get(c)) for c in ('etlmonth', 'etlmonth_drr')]
        if not observed or observed > as_of or any(d and d > as_of for d in loads):
            stats['invalid_or_future_rows_removed'] += 1
            continue
        unique.append(row)
    buckets = defaultdict(set)
    for row in unique:
        group = cohort.norm(row.get(GROUP_FIELDS.get(source, ''))) or 'COHORT_EXPORT'
        buckets[group].add(cohort.day(row[spec['date']]))
    selected_dates = {g: set(sorted(ds, reverse=True)[:2 if source == 'clo' else 1]) for g, ds in buckets.items()}
    if source == 'counterparty':
        # Retain the newest available snapshot plus snapshots preceding CLO dates.
        all_dates = sorted({cohort.day(r[spec['date']]) for r in unique})
        wanted = {max(all_dates)} if all_dates else set()
        for anchor in clo_dates:
            available = [d for d in all_dates if d <= anchor]
            if available:
                wanted.add(max(available))
        selected_dates = {g: wanted for g in buckets}
    result = []
    for row in unique:
        group = cohort.norm(row.get(GROUP_FIELDS.get(source, ''))) or 'COHORT_EXPORT'
        observed = cohort.day(row[spec['date']])
        if observed not in selected_dates[group]:
            stats['older_snapshot_rows_removed'] += 1
            continue
        if source == 'facilities':
            lower_raw, upper_raw = row.get('record_start_dt'), row.get('record_end_dt')
            lower, upper = cohort.day(lower_raw), cohort.day(upper_raw)
            open_end = str(upper_raw or '').replace('-', '')[:8] == '99991231'
            if (lower and lower > observed) or (upper and upper < observed):
                stats['out_of_effective_period_removed'] += 1
                continue
            if (cohort.norm(lower_raw) and not lower) or (cohort.norm(upper_raw) and not upper and not open_end):
                stats['unparseable_version_bounds_retained'] += 1
            if not lower_raw or not upper_raw:
                stats['unknown_version_bounds_retained'] += 1
        result.append(row)
    stats['selected_rows'] = len(result)
    stats['distinct_facility_id_strings'] = len({r['facility_id'] for r in result if r.get('facility_id')})
    stats['scientific_facility_id_rows'] = sum(bool(re.fullmatch(r'[+-]?\d+(?:\.\d+)?E[+-]?\d+', cohort.norm(r.get('facility_id')) or '')) for r in result)
    stats['shared_facility_rows'] = sum(cohort.norm(r.get('shared_facility_flag')) == 'Y' for r in result)
    return result, dict(stats), {g: sorted(ds) for g, ds in selected_dates.items()}


def observed_links(files, groups):
    """Extraction discovery only. Preserve provenance; never infer types from shapes."""
    found = {}
    for filename in files:
        _, rows = read_csv(filename)
        for row in rows:
            if 'proposed_type' in row:
                group, kind, value = row['mastergroup_id'], row['proposed_type'], row['identifier_value']
                candidates = [(group, kind, value, row.get('origin_source', ''), row.get('origin_column', ''))]
            else:
                group = row.get('drr_mastergroup_id') or row.get('rct_mastergroup_id') or row.get('mastergroup_esr_identifier')
                candidates = [(group, kind, row.get(col), 'supplied_export', col) for kind, col in [('CIN', 'cin'), ('CIN', 'obligor_cin'), ('GID', 'gid'), ('GID', 'rct_gid')]]
                # Facilities relationship IDs are candidate covenant discovery, not a join approval.
                if row.get('relationship_id'):
                    candidates.append(('', 'RELATIONSHIP_ID', row['relationship_id'], 'facilities', 'relationship_id'))
            for group, kind, value, origin, column in candidates:
                value = cohort.norm(value)
                if kind not in ('CIN', 'GID', 'RELATIONSHIP_ID') or not value or (group not in groups and kind != 'RELATIONSHIP_ID'):
                    continue
                found[(group or '', kind, value, origin, column)] = dict(mastergroup_id=group or '', kind=kind, value=value, origin_source=origin, origin_column=column)
    return list(found.values())


def sql_pack(output, identifiers, as_of, lookback=120):
    output = Path(output)
    if output.exists():
        raise ValueError('SQL output exists; choose a new folder')
    cfg = cohort.config(ROOT / 'config.json')
    groups = {g['mastergroup_id'] for g in cfg['groups']}
    links = observed_links(identifiers, groups)
    ids = ', '.join(cohort.literal(g) for g in sorted(groups))
    lower = (date.fromisoformat(as_of) - timedelta(days=lookback)).isoformat()
    output.mkdir(parents=True)
    write_csv(output / 'observed_identifier_candidates.csv', ['mastergroup_id', 'kind', 'value', 'origin_source', 'origin_column'], links)
    plan = []
    for source, spec in cohort.engine.SOURCES.items():
        table = cohort.qualified(source)
        cohort.dump(output / f'{source}_schema.sql', f'SHOW COLUMNS FROM {table};\n\nSHOW CREATE TABLE {table};\n')
        lo, hi = (lower, as_of) if spec['format'] == 'iso' else (lower.replace('-', ''), as_of.replace('-', ''))
        date_col = cohort.ident(spec['date'])
        route = []
        if source in GROUP_FIELDS:
            route.append(f'UPPER(TRIM(CAST(t.{cohort.ident(GROUP_FIELDS[source])} AS VARCHAR))) IN ({ids})')
        for kind, cols in cohort.IDENTIFIERS[source].items():
            if kind not in ('CIN', 'GID', 'RELATIONSHIP_ID'):
                continue
            values = sorted({r['value'] for r in links if r['kind'] == kind})
            if values:
                for col in cols:
                    route.append(f'UPPER(TRIM(CAST(t.{cohort.ident(col)} AS VARCHAR))) IN (' + ', '.join(cohort.literal(v) for v in values) + ')')
        if not route:
            cohort.dump(output / f'{source}_BLOCKED.txt', 'No source-compatible observed identifiers supplied. A verified bridge is still needed; no name or facility-ID equivalence was invented.\n')
            plan.append(dict(source=source, csv_filename='', status='no_identifier_route', signals=','.join(s for s, sources in cohort.SIGNAL_SOURCES.items() if source in sources)))
            continue
        constraints = [f't.{date_col} BETWEEN {cohort.literal(lo)} AND {cohort.literal(hi)}', '(' + ' OR '.join(route) + ')']
        # Avoid future processing versions of business-dated sources.
        if source == 'drr':
            constraints.append(f't.run_date <= {cohort.literal(as_of.replace("-", ""))}')
        if source == 'pvd':
            for col in ('etlmonth', 'etlmonth_drr'):
                constraints.append(f'(t.{col} IS NULL OR TRIM(CAST(t.{col} AS VARCHAR)) = \'\' OR SUBSTR(REPLACE(CAST(t.{col} AS VARCHAR), \'-\', \'\'), 1, 8) <= {cohort.literal(as_of.replace("-", ""))})')
        filtered = f'WITH filtered AS (\n  SELECT t.* FROM {table} t\n  WHERE ' + '\n    AND '.join(constraints) + '\n)'
        if source == 'counterparty':
            clo = cohort.qualified('clo')
            query = filtered + f''', clo_dates AS (
  SELECT DISTINCT rct_mastergroup_id, run_date FROM {clo}
  WHERE run_date BETWEEN '{lo}' AND '{hi}' AND rct_mastergroup_id IN ({ids})
), ranked_clo_dates AS (
  SELECT run_date, DENSE_RANK() OVER (PARTITION BY rct_mastergroup_id ORDER BY run_date DESC) AS snapshot_rank FROM clo_dates
), anchors AS (
  SELECT '{hi}' AS anchor_date
  UNION SELECT run_date FROM ranked_clo_dates WHERE snapshot_rank <= 2
), mapping_dates AS (
  SELECT MAX(f.run_date) AS mapping_date FROM filtered f CROSS JOIN anchors a
  WHERE f.run_date <= a.anchor_date GROUP BY a.anchor_date
)
SELECT DISTINCT f.* FROM filtered f
WHERE f.run_date IN (SELECT mapping_date FROM mapping_dates);
'''
        else:
            group = GROUP_FIELDS.get(source)
            partition = f'PARTITION BY {cohort.ident(group)} ' if group else ''
            query = filtered + f', ranked AS (\n  SELECT f.*, DENSE_RANK() OVER ({partition}ORDER BY {date_col} DESC) AS _extract_snapshot_rank\n  FROM filtered f\n)\nSELECT DISTINCT r.* FROM ranked r\nWHERE _extract_snapshot_rank <= {2 if source == "clo" else 1}'
            if source == 'facilities':
                query += '''
  AND (TRY(DATE_PARSE(NULLIF(TRIM(record_start_dt), ''), '%Y%m%d')) IS NULL OR record_start_dt <= run_date)
  AND (TRY(DATE_PARSE(NULLIF(TRIM(record_end_dt), ''), '%Y%m%d')) IS NULL OR record_end_dt = '99991231' OR record_end_dt >= run_date)'''
            query += ';\n'
        filename = f'{source}_current.csv' if source != 'clo' else 'clo_current_and_previous.csv'
        note = ('-- READ ONLY; copy into Starburst and export manually. No Python/database connection.\n'
                f'-- Save as {filename}. Keep identifiers as text; do not round in a spreadsheet.\n'
                '-- Observed ID routes are discovery candidates, not verified cross-source joins.\n'
                '-- SELECT DISTINCT removes identical rows only, never sums or chooses conflicting amounts.\n'
                '-- Latest AVAILABLE within the bounded window; may be stale. Retain reporting/load dates.\n')
        if source == 'counterparty':
            note += '-- Delta catalog corrected by user, 3 November 2026. Verify live columns/date format first.\n-- Latest snapshot and preceding CLO mapping snapshots; inactive/conflicting mappings retained.\n'
        if source == 'facilities':
            note += '-- Effective-period selection is a development rule to verify. Do not filter latest_record=CURRENT.\n'
        cohort.dump(output / f'{source}_extract.sql', note + query)
        cohort.dump(output / f'{source}_date_coverage.sql', note + filtered + f'\nSELECT {date_col}, COUNT(*) AS raw_rows FROM filtered GROUP BY {date_col} ORDER BY {date_col} DESC;\n')
        plan.append(dict(source=source, csv_filename=filename, status='query_generated', signals=','.join(s for s, sources in cohort.SIGNAL_SOURCES.items() if source in sources)))
    write_csv(output / 'extraction_plan.csv', ['source', 'csv_filename', 'status', 'signals'], plan)
    cohort.dump(output / 'README.md', f'''# Current extraction pack

Generated as of {as_of}; source search window {lower} to {as_of}. Change the
as-of date by regenerating with refresh.py sql. These queries have not run in Starburst.

Run each source's schema statements separately, then its extract SQL, manually.
Save the result under the filename in extraction_plan.csv, keep CSV headers even
when empty, and transfer all data CSVs into starburst_exports/round_005 inside the
package. Keep schema/error/profile downloads outside that data folder.

Counterparty now uses delta.prod_party_gda.counterparty_core. The schema query
checks live access and column names. The extraction includes target mastergroups
OR observed CIN/GID routes so contradictory group mappings remain visible.

CLO retains the latest two available group snapshots for SIG01 comparisons.
Other sources retain one latest available snapshot per explicit group (or the
whole cohort export when no verified group field exists). Counterparty also keeps
snapshots preceding CLO dates for point-in-time enrichment. An absent current
facility is not resurrected from its last historical row. All columns are retained
for this testing round; date/version reduction controls the main row expansion.

Facilities uses record_start_dt/record_end_dt, including open end 99991231;
overlapping versions remain for conflict checks. This rule requires source-owner
validation. latest_record=CURRENT is not used because it would drop valid-looking
rows in the supplied sample. DRR borrower associations and parent/child limits are
preserved; no financial totals or arbitrary ROW_NUMBER deduplication are applied.

PVD remains at its native relationship/key grain. No facility identity is inferred
from joi_key. Covenant relationship lookups, if present, are candidate discovery
only; a verified source-scoped bridge is needed before covenant signal assignment.
Latest available is not a guarantee of current or complete coverage. If a source is
empty, inspect its date_coverage query before widening the window.
''')


def test_links(data, as_of, cfg):
    """Explicit opt-in development associations, limited to observed target rows."""
    groups = {g['mastergroup_id'] for g in cfg['groups']}
    by_cin = defaultdict(set)
    for source in ('clo', 'drr', 'counterparty'):
        for row in data.get(source, []):
            mg = cohort.norm(row.get(cohort.GROUP_FIELDS[source]))
            for col in cohort.IDENTIFIERS[source].get('CIN', []):
                cin = cohort.norm(row.get(col))
                if cin and cohort.valid_id(mg,cfg):
                    by_cin[cin].add(mg)
    cp_index = defaultdict(list)
    cp_cfg = json.loads((ROOT/'engine/config.json').read_text())['counterparty']
    for row in data.get('counterparty', []):
        for kind, col in [('CIN','customer_relationship_cin_identifier'),('GID','customer_relationship_gid_identifier')]:
            value = cohort.norm(row.get(col))
            if value:
                cp_index[(kind,value)].append(row)

    def cp_candidates(kind, value, cutoff):
        lower = (date.fromisoformat(cutoff)-timedelta(days=cp_cfg['lookback_days'])).isoformat()
        rows = [r for r in cp_index.get((kind,value), []) if lower <= (cohort.day(r.get('run_date')) or '') <= cutoff]
        if not rows:
            return set()
        latest = max(cohort.day(r['run_date']) for r in rows)
        return {cohort.norm(r.get('mastergroup_esr_identifier')) for r in rows
                if cohort.day(r['run_date']) == latest
                and (cohort.norm(r.get('customer_relationship_lifecycle_status_code')) in cp_cfg['active_statuses']
                     or (not cohort.norm(r.get('customer_relationship_lifecycle_status_code')) and cp_cfg['allow_blank_status']))
                and cohort.valid_id(r.get('mastergroup_esr_identifier'),cfg)}

    links = {}
    for source in ('facilities', 'kyc', 'pvd', 'clo'):
        for row in data.get(source, []):
            if source == 'clo':
                if cohort.valid_id(row.get('rct_mastergroup_id'),cfg):
                    continue  # preserve a valid original; the engine records CP contradictions
                observed = cohort.day(row['run_date'])
                cin, gid = cohort.norm(row.get('obligor_cin')), cohort.norm(row.get('rct_gid'))
                candidates = cp_candidates('CIN',cin,observed) | cp_candidates('GID',gid,observed)
                value,kind,column = (cin,'CIN','obligor_cin') if cin else (gid,'GID','rct_gid')
                scope = {k:cohort.norm(row[k]) for k in cohort.SCOPE_FIELDS['clo'] if cohort.norm(row.get(k))}
                # Restrict a per-row combined CIN/GID decision to that association.
                scope.update({k:cohort.norm(row[k]) for k in ('obligor_cin','rct_gid','sub_lim_id','rct_facility_ref','facility_id') if cohort.norm(row.get(k))})
            elif source == 'pvd':
                value = cohort.norm(row.get('joi_relationship_id'))
                candidates = {value} if value in groups else set()
                kind, column, scope = 'PVD_RELATIONSHIP_ID', 'joi_relationship_id', {}
            else:
                value = cohort.norm(row.get('cin'))
                candidates = by_cin.get(value, set())
                kind, column = 'CIN', 'cin'
                scope = {k: cohort.norm(row[k]) for k in cohort.SCOPE_FIELDS.get(source, []) if cohort.norm(row.get(k))}
                if source == 'facilities' and any(k not in scope for k in cohort.SCOPE_FIELDS[source]):
                    continue
            if len(candidates) != 1 or not candidates <= groups:
                continue
            mg = next(iter(candidates))
            observed = cohort.day(row[cohort.engine.SOURCES[source]['date']])
            key = cohort.digest('refresh-development', source, mg, value, scope, observed)
            links[key] = dict(zip(cohort.REVIEW_COLUMNS, [key, mg, source, column, value, kind, kind, source, 'approve',
                'Explicit --test-observed-links development assumption: exact CIN associated with one target group in supplied native-group source rows, or exact supplied MG value in PVD native relationship field. CLO missing-group links require one combined CIN/GID Counterparty group at the latest per-key prior date, using unverified development lifecycle settings. Not production identity approval; no name/shape inference.', observed, observed, json.dumps(scope, sort_keys=True), observed, observed, 1]))
    return list(links.values())


def process(input_dir, output, as_of, use_test_links=False, approved=None):
    output = Path(output)
    if output.exists():
        raise ValueError('Run output exists; choose a new folder')
    import_exports(input_dir, output / 'imported')
    data, stats, columns = {}, [], {}
    dates = []
    for source in ['clo', 'counterparty', 'drr', 'facilities', 'pvd', 'kyc', 'covenants']:
        chunks = sorted((output / 'imported' / source).glob('*.csv'))
        if not chunks:
            continue
        raw = []
        for chunk in chunks:
            columns[source], records = read_csv(chunk)
            raw += records
        data[source], counts, selected_dates = select_current(source, raw, as_of, dates)
        if source == 'clo':
            dates = sorted({cohort.day(r['run_date']) for r in data[source]})
        stats.append(dict(source=source, **counts, selected_dates=json.dumps(selected_dates)))
        write_csv(output / 'current_inputs' / source / 'part-001.csv', columns[source], data[source])
        cohort.dump(output / 'current_inputs' / source / 'part-001.metadata.json', json.dumps({'selection':'refresh.py select_current; raw imports preserved', 'as_of':as_of, 'counts':counts, 'dates':selected_dates}, indent=2))
    # Preserve error-vs-empty outcomes for the downstream coverage report.
    cohort.dump(output / 'current_inputs/import_manifest.json', (output / 'imported/import_manifest.json').read_text())
    fields = list(dict.fromkeys(k for s in stats for k in s))
    write_csv(output / 'current_selection.csv', fields, stats)
    cfg = cohort.config(ROOT / 'profiles/current_20261103.json')
    links = []
    if approved:
        cohort.read_approvals(approved, cfg)
        _, links = read_csv(approved)
    if use_test_links:
        known = {r['review_id'] for r in links}
        links += [r for r in test_links(data, as_of, cfg) if r['review_id'] not in known]
    approvals = output / 'test_identifiers.csv'
    write_csv(approvals, cohort.REVIEW_COLUMNS, links)
    cohort.analyse(output / 'current_inputs', output / 'cohort', as_of, ROOT / 'profiles/current_20261103.json', approvals)
    if any(r['matched_rows'] != '0' for r in read_csv(output / 'cohort/coverage.csv')[1]):
        cohort.run_signals(output / 'cohort', output / 'signals', ROOT / 'profiles/current_signals_20261105_dev2.json')
    cohort.dump(output / 'README.md', '''# Current source and signal test results

Raw imports are in imported/. current_inputs/ contains selected snapshots and
effective Facilities versions. current_selection.csv explains row reductions.
cohort/REPORT.md describes group coverage; signals/results/exports/ contains
candidate signal evidence if any rows were uniquely linked. test_identifiers.csv
records explicit opt-in test associations and any supplied approvals. Never use
development test associations as proof of production identity or legal membership.

SIG01 alone imputes missing drawn amounts to zero and records each imputation;
missing comparison observations and invalid numbers remain unavailable. SIG06
does not inherit zero imputation. SIG07 retains limit_cat as candidate context;
no CAT code automatically proves advisory engagement. Definitions and product
eligibility remain unverified, so trigger booleans remain null by default.

No sums across currencies, dates, overlapping sources, or parent/child limits are
computed. DRR UIDs are candidate exposure keys; shared borrower associations are
consolidated only when non-association attributes agree, otherwise metrics are
withheld. Scientific facility IDs cannot support cross-source facility joins.
''')
    return output


def inventory(inputs, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Review output exists')
    files = sorted({p.resolve() for item in inputs for p in (Path(item).rglob('*.csv') if Path(item).is_dir() else [Path(item)])})
    records = []
    for p in files:
        profile = inspect_export(p)
        item = dict(file=str(p), kind=profile['kind'], source=profile.get('source'), rows=profile.get('rows', 0), sha256=profile['sha256'])
        if profile['kind'] == 'data':
            _, rows = read_csv(p)
            selected, stats, dates = select_current(profile['source'], rows, '2026-11-03')
            item.update(stats, selected_dates=json.dumps(dates), rowset_sha256=profile.get('rowset_sha256'))
        records.append(item)
    fields = list(dict.fromkeys(k for r in records for k in r))
    write_csv(output / 'export_inventory.csv', fields, records)
    cohort.dump(output / 'inventory.json', json.dumps(records, indent=2))
    return records


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    q = sub.add_parser('sql')
    q.add_argument('--identifiers', action='append', default=[])
    q.add_argument('--as-of', required=True)
    q.add_argument('--lookback-days', type=int, default=120)
    q.add_argument('--out', required=True)
    q = sub.add_parser('process')
    q.add_argument('--input', required=True)
    q.add_argument('--out', required=True)
    q.add_argument('--as-of', required=True)
    q.add_argument('--test-observed-links', action='store_true')
    q.add_argument('--approved')
    q = sub.add_parser('review')
    q.add_argument('--input', action='append', required=True)
    q.add_argument('--out', required=True)
    args = p.parse_args()
    if hasattr(args, 'as_of') and not cohort.day(args.as_of):
        p.error('Supply a valid as-of date')
    if args.command == 'sql':
        if args.lookback_days < 1:
            p.error('lookback-days must be positive')
        sql_pack(args.out, args.identifiers, args.as_of, args.lookback_days)
    elif args.command == 'process':
        process(args.input, args.out, args.as_of, args.test_observed_links, args.approved)
    else:
        inventory(args.input, args.out)


if __name__ == '__main__':
    main()
