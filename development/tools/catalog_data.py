#!/usr/bin/env python3
"""Inventory preserved raw/schema CSVs; no financial metrics or raw files are changed."""
from pathlib import Path
import csv
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pvd_client_cohort_lab'))
from import_exports import inspect_export
import cohort


def main():
    origins = json.loads((ROOT / 'PROVENANCE_ORIGINS.json').read_text())['copied_files']
    files = sorted(f for dirname in ['data', 'sql', 'sql_sample_extract'] for f in (ROOT / dirname).rglob('*.csv'))
    records, seen = [], {}
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            info = inspect_export(path)
        except Exception as exc:
            info = dict(kind='unclassified', source='', rows='', columns=[], inspection_error=str(exc))
        source = info.get('source') or ''
        columns = info.get('columns') or []
        kind = info.get('kind', 'unknown')
        if {'final_crr', 'cin', 'credit_proposal_serial_no'} <= set(columns):
            source, kind = 'application_ratings', 'data'
        if 'profile' in path.stem and {'observation_date', 'raw_rows'} <= set(columns):
            kind, source = 'date_profile', 'application_ratings'
        signals = {'clo': 'SIG01;SIG06', 'counterparty': 'identity enrichment', 'drr': 'SIG06',
                   'facilities': 'SIG02;SIG07', 'pvd': 'SIG06;SIG07;identity discovery',
                   'kyc': 'SIG04', 'covenants': 'SIG06 covenant investigation',
                   'application_ratings': 'SIG07 CRR'}.get(source, 'schema/profile/review only')
        role = 'historical reference'
        notes = 'Do not combine historical trees as one incoming round.'
        if rel.startswith('data/current_exports/'):
            role = 'reference input'
            notes = 'Primary selected export; usable scope/trigger subject to PROJECT_STATE.'
        elif rel.startswith('data/application_ratings/'):
            role = 'rating profile' if kind == 'date_profile' else 'reference rating sample'
            notes = ('Profile rows are counts, not supplied application records.' if kind == 'date_profile'
                     else 'Partial real sample; full 722-row cohort is absent locally.')
        elif rel.startswith('data/application_ratings_schema/'):
            role, notes = 'rating schema/query metadata', 'Metadata, not client rating data.'
        elif rel.startswith('data/history/'):
            role = 'partition history'
            notes = 'Siemens DE prior Facilities partition; not mixed into latest input.'
        if 'covenants_extract' in path.name:
            role, signals = 'QUARANTINED', 'none'
            notes = 'Mislabelled covenant result contains Counterparty data. Never ingest as covenant or additional CP observations.'
        if source == 'pvd_sector_aggregate':
            notes = 'Excluded from active scope; historical reference only.'
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        duplicate = seen.get(digest, '')
        seen.setdefault(digest, rel)
        date_col = 'run_date' if source == 'application_ratings' else cohort.engine.SOURCES.get(source, {}).get('date', '')
        if kind == 'date_profile':
            date_col = 'observation_date'
        dates, row_count = [], 0
        with path.open(encoding='utf-8-sig', newline='') as handle:
            for row in csv.DictReader(handle):
                row_count += 1
                if date_col in columns:
                    value = cohort.day(row.get(date_col))
                    if value:
                        dates.append(str(value))
        if kind in {'error', 'query_error'}:
            notes += ' Returned error; not an empty data export.'
        records.append(dict(path=rel, role=role, detected_source=source, detected_kind=kind,
                            possible_signals=signals, rows=row_count, columns=len(columns),
                            snapshot_column=date_col, snapshot_min=min(dates) if dates else '',
                            snapshot_max=max(dates) if dates else '', bytes=path.stat().st_size,
                            sha256=digest, same_bytes_as=duplicate, original_project_path=origins.get(rel, ''), notes=notes))
    for source, signals, notes in [
        ('application_ratings_full', 'SIG07', 'MISSING: only 207 sample data rows supplied; full profiled cohort unavailable.'),
        ('financial_covenants', 'SIG06', 'MISSING: genuine financial covenant tests not supplied.'),
        ('enquiries', 'SIG03', 'MISSING: suitable enquiry/pricing request source not identified.'),
    ]:
        records.append(dict(path='', role='missing source/data', detected_source=source,
                            detected_kind='missing', possible_signals=signals, notes=notes))
    fields = ['path', 'role', 'detected_source', 'detected_kind', 'possible_signals', 'rows', 'columns',
              'snapshot_column', 'snapshot_min', 'snapshot_max', 'bytes', 'sha256', 'same_bytes_as',
              'original_project_path', 'notes']
    with (ROOT / 'DATA_CATALOG.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(records)
    print(f'Catalogued {len(files)} CSVs and three missing source/data entries.')


if __name__ == '__main__':
    main()
