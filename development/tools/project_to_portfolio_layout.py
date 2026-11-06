#!/usr/bin/env python3
"""Project earlier full-column extracts (SELECT t.*) into the portfolio input layout.

Use it to re-run an older round (e.g. data/current_exports) through run_portfolio.py, or to
check that the portfolio column lists keep everything the signal rules need. Each source is
reduced to the portfolio SQL's columns, de-duplicated with identical-row DISTINCT, and written
as <out>/<source>/part_01_of_01.csv.

Usage (from development/):
  python3 -B tools/project_to_portfolio_layout.py --out data/portfolio_from_current_exports \
      --source counterparty=data/current_exports/counterparty_current.csv \
      --source clo=data/current_exports/clo_current_and_previous.csv \
      --source facilities=data/current_exports/facilities_current.csv \
      --source drr=data/current_exports/drr_current.csv --source pvd=data/current_exports/pvd_current.csv \
      --source kyc=data/current_exports/kyc_current.csv \
      --source 'application_ratings=data/application_ratings_full/*.csv'
"""
import argparse
import csv
import glob
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pvd_client_cohort_lab'))
from portfolio_sql import SOURCES, output_columns  # noqa: E402

csv.field_size_limit(64 * 1024 * 1024)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', required=True)
    p.add_argument('--source', action='append', required=True, help='name=path or name=glob')
    a = p.parse_args()
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f'{out} exists; choose a new folder')
    for item in a.source:
        name, pattern = item.split('=', 1)
        if name not in SOURCES:
            raise SystemExit(f'Unknown source {name}')
        cols = output_columns(name)
        seen, rows, missing = set(), [], set()
        for path in sorted(glob.glob(str(ROOT / pattern) if not Path(pattern).is_absolute() else pattern)):
            if 'profile' in Path(path).stem:
                continue
            with open(path, encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                header = {h.strip().lower(): h for h in reader.fieldnames}
                missing |= {c for c in cols if c not in header}
                for r in reader:
                    values = tuple((r.get(header[c]) or '') if c in header else '' for c in cols)
                    if values not in seen:
                        seen.add(values)
                        rows.append(values)
        (out / name).mkdir(parents=True)
        with (out / name / 'part_01_of_01.csv').open('w', encoding='utf-8', newline='') as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        print(f'{name}: {len(rows)} rows' + (f' (columns absent in the input, left blank: {sorted(missing)})' if missing else ''))


if __name__ == '__main__':
    main()
