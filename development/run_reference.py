#!/usr/bin/env python3
"""Rebuild the known three-client baseline entirely from local selected CSVs."""
import argparse
from collections import Counter
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'pvd_client_cohort_lab'))
from refresh import process
from export_signals import export as export_signals
from sig07_crr import export as export_crr
from alignment import apply as apply_alignment


def read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as handle:
        return list(csv.DictReader(handle))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',required=True,help='Fresh output directory; relative to this workspace')
    p.add_argument('--input',default='data/current_exports')
    p.add_argument('--ratings-input',default='data/application_ratings')
    p.add_argument('--base-as-of',default='2026-11-03')
    p.add_argument('--as-of',default='2026-11-04')
    p.add_argument('--test-observed-links',action='store_true')
    p.add_argument('--verify-reference',action='store_true')
    args=p.parse_args()
    date.fromisoformat(args.base_as_of);date.fromisoformat(args.as_of)
    resolve=lambda name:Path(name).resolve() if Path(name).is_absolute() else (ROOT/name).resolve()
    output,inputs,ratings=map(resolve,[args.out,args.input,args.ratings_input])
    if output.exists():raise ValueError('Output already exists; choose a new --out folder')
    # Guard the known misleading export even if an alternative incoming folder is selected.
    if any(inputs.glob('*covenants_extract*.csv')):
        raise ValueError('This folder contains the quarantined/mislabelled covenant export. Use data/current_exports or a reviewed new input folder.')
    if args.verify_reference:
        if not args.test_observed_links:raise ValueError('--verify-reference requires --test-observed-links to reproduce the documented development assumptions')
        expected=json.loads((ROOT/'REFERENCE_EXPECTATIONS.json').read_text())
        if args.base_as_of!=expected['base_as_of'] or args.as_of!=expected['as_of']:
            raise ValueError('Reference verification requires the documented assessment dates')
        for rel,digest in expected['input_sha256'].items():
            if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=digest:
                raise ValueError('Reference input changed: '+rel)
        if inputs!=ROOT/'data/current_exports' or ratings!=ROOT/'data/application_ratings':
            raise ValueError('Reference verification uses only the selected reference folders')
    output.mkdir(parents=True)
    baseline=process(inputs,output/'baseline',args.base_as_of,use_test_links=args.test_observed_links)
    signals=baseline/'signals'
    if not signals.exists():raise ValueError('No uniquely matched data for signal tests; inspect baseline/cohort/REPORT.md')
    core=export_signals(baseline/'cohort',signals,inputs,output/'CORE_SIGNAL_EVIDENCE.csv',export_date=args.as_of)
    crr=export_crr(ratings,core,output/'crr',args.as_of)
    # development-2: SIG02 event date = credit approval date linked from Application Ratings.
    final=output/'BOND_RADAR_SIGNAL_EVIDENCE.csv'
    aligned=apply_alignment(output/'crr'/'DCM_Run_003_All_Signal_Evidence_With_CRR.csv',ratings,final,args.base_as_of)
    rows=read(core);combined=read(final)
    counts=dict(core_rows=len(rows),combined_rows=crr['combined_rows'],crr_candidates=crr['application_crr_candidates'],
                populated_crr=crr['nonmissing_crr'],missing_crr=crr['missing_crr'],
                utilisation_above_70=sum(r.get('above_70_for_testing')=='True' for r in rows),
                recent_creation_candidates=sum(r.get('recent_creation_for_testing')=='True' for r in rows),
                recent_approval_candidates=sum(r.get('recent_creation_for_testing')=='True' for r in combined),
                sig02_approval_dates_linked=aligned['sig02_approval_linking'].get('approval_date_applied',0),
                material_drawing_candidates=sum(r.get('material_drawing_for_testing')=='True' for r in combined),
                covenant_pressure_candidates=sum(r.get('covenant_pressure_for_testing')=='True' for r in combined),
                sig01_zero_imputed=sum(r.get('current_drawn_imputed_zero')=='True' for r in rows),
                by_signal=dict(Counter(r['signal_id'] for r in rows)),
                combined_by_signal=dict(Counter(r['signal_id'] for r in combined)))
    if args.verify_reference:
        for key,value in expected['counts'].items():
            if counts.get(key)!=value:raise AssertionError(f'Reference mismatch for {key}: {counts.get(key)} != {value}')
    summary=dict(base_as_of=args.base_as_of,crr_as_of=args.as_of,counts=counts,
                 test_observed_links=args.test_observed_links,reference_verified=args.verify_reference,
                 rule_version='development-2',combined_csv='BOND_RADAR_SIGNAL_EVIDENCE.csv',sig02_approval_linking=aligned['sig02_approval_linking'],
                 qualification='Development evidence; business trigger flags remain unverified. Rules follow the DCM meeting decisions recorded in docs/MEETING_ALIGNMENT_REVIEW.md.')
    (output/'RUN_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
