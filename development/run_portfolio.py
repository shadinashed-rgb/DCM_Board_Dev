#!/usr/bin/env python3
"""Build Bond Radar signals for the WHOLE portfolio from the full-portfolio extracts.

Input layout (produced by the SQL pack pvd_client_cohort_lab/sql_templates/portfolio_<date>/):
  data/portfolio_<date>/
    counterparty/part_01_of_04.csv ...   clo/part_01_of_08.csv ...   facilities/ ...   drr/ ...
    pvd/ ...   kyc/ ...   covenants/ ...   application_ratings/ ...   reference/clo_fx_reference.csv (optional)

Example (from development/):
  python3 -B run_portfolio.py --input data/portfolio_20261106 --as-of 2026-11-06 --out runs/portfolio_20261106_001
  python3 -B run_portfolio.py ... --fx-from-clo            # optional: unvalidated CLO-derived FX for the EUR 50m test
  python3 -B run_portfolio.py ... --business-lines GB,CMB  # optional: limit the summaries to these business lines
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'pvd_client_cohort_lab'))
import portfolio  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--input', required=True, help='folder with one sub-folder per source (part_XX_of_NN.csv files)')
    p.add_argument('--out', required=True, help='fresh run folder, e.g. runs/portfolio_20261106_001')
    p.add_argument('--as-of', required=True, help='assessment date YYYY-MM-DD (same as the SQL pack)')
    p.add_argument('--config', default=str(ROOT / 'pvd_client_cohort_lab/profiles/portfolio_dev2.json'))
    p.add_argument('--fx-from-clo', action='store_true', help='derive ccy->EUR rates from reference/clo_fx_reference.csv (unvalidated)')
    p.add_argument('--business-lines', default='', help='comma list of mastergroup_business_line_code to keep in the summaries')
    p.add_argument('--extra-links', help='reviewed identity links CSV (identity_links format), e.g. PVD relationship -> mastergroup')
    a = p.parse_args()
    resolve = lambda x: Path(x) if Path(x).is_absolute() else ROOT / x
    summary = portfolio.run(resolve(a.input), resolve(a.out), a.as_of, resolve(a.config), a.fx_from_clo,
                            [x.strip().upper() for x in a.business_lines.split(',') if x.strip()] or None,
                            resolve(a.extra_links) if a.extra_links else None)
    print(json.dumps({k: summary[k] for k in ('records', 'by_signal', 'groups_with_evidence', 'groups_with_candidates', 'candidate_records', 'records_without_group')}, indent=2))


if __name__ == '__main__':
    main()
