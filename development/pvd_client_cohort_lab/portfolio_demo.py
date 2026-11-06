#!/usr/bin/env python3
"""Synthetic full-portfolio extract for testing and demonstrating run_portfolio.py.

Made-up records only — never bank data. Every file uses the exact column lists of the
portfolio SQL pack (portfolio_sql.output_columns), so the SQL output contract and the
pipeline are tested together. Sources are split into parts like real chunked downloads.

Groups:
  MGA0001 Alpha Telecom    SIG01 material: Cat A REV sub-limit drawn EUR 10m -> 80m; KYC case; maturity in 9 months
  MGB0002 Beta Energy      SIG01 in USD (needs FX: material only with --fx-from-clo); DRR utilisation 85%
  MGC0003 Gamma Holdings   SIG02: new facility, credit approval 20 days before as-of (Application Ratings)
  MGD0004 Delta Industries SIG06: leverage 2.6x against a 3.0x maximum (pressure); PVD row linked by a reviewed link
  One CIN maps to two groups (ambiguous -> no group); one DRR row has mastergroup "NO MSG" (not a group).

Usage: python3 -B pvd_client_cohort_lab/portfolio_demo.py --out data/portfolio_demo
"""
import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from portfolio_sql import output_columns  # noqa: E402

AS_OF = '2026-11-06'


def write(folder, source, rows, parts=1):
    cols = output_columns(source)
    (folder / source).mkdir(parents=True, exist_ok=True)
    for i in range(parts):
        chunk = rows[i::parts]
        with (folder / source / f'part_{i + 1:02d}_of_{parts:02d}.csv').open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows({c: r.get(c, '') for c in cols} for r in chunk)


def build(out):
    out = Path(out)
    if out.exists():
        raise SystemExit(f'{out} exists; choose a new folder')
    out.mkdir(parents=True)
    cp = lambda cin, gid, mg, name, line='GBM', status='Active', run='20261105': dict(
        run_date=run, source_system_name='DEMO', source_system_instance_country='GB', customer_relationship_cin_identifier=cin,
        customer_relationship_gid_identifier=gid, customer_relationship_lifecycle_status_code=status, mastergroup_esr_identifier=mg,
        mastergroup_name=name, mastergroup_business_line_code=line, mastergroup_principal_country_code='GB', mastergroup_industry_classification_sector_name='CORPORATES')
    write(out, 'counterparty', [
        cp('C100', 'G100', 'MGA0001', 'Alpha Telecom'), cp('C200', 'G200', 'MGB0002', 'Beta Energy'),
        cp('C300', 'G300', 'MGC0003', 'Gamma Holdings', 'CMB'), cp('C400', 'G400', 'MGD0004', 'Delta Industries'),
        cp('C900', 'G900', 'MGA0001', 'Alpha Telecom'), cp('C900', 'G901', 'MGB0002', 'Beta Energy'),          # ambiguous CIN
        cp('C100', 'G100', 'MGOLD', 'Old Group', run='20261001'),                                              # older snapshot ignored
        cp('C500', 'G500', 'MGE0005', 'Epsilon Closed', status='CLOSED')], parts=2)
    clo = lambda sub, cin, mg, run, drawn_usd, product='REV', ccy='EUR', limit='100000000': dict(
        run_date=run, source_system='DEMO', mapping_system='DEMO', hsbc_booking_legal_entity='HBEU', sub_lim_id=sub, obligor_cin=cin,
        rct_mastergroup_id=mg, local_product_type_lbs=product, facility_currency=ccy, facility_limit_amount=limit, facility_drawn_amount=drawn_usd,
        ag_acc_bal_drawn_sub_lim_usd='', deal_indicator_sole_lender='N', facility_maturity_date='2027-08-01', rct_mastergroup_name='')
    write(out, 'clo', [
        clo('SUBA1', 'C100', 'MGA0001', '20261030', '10000000'), clo('SUBA1', 'C100', 'MGA0001', '20261105', '80000000'),
        clo('SUBB1', 'C200', 'MGB0002', '20261030', '0', 'TERM', 'USD'), clo('SUBB1', 'C200', 'MGB0002', '20261105', '90000000', 'TERM', 'USD'),
        clo('SUBX9', 'C900', '', '20261030', '0'), clo('SUBX9', 'C900', '', '20261105', '70000000')], parts=3)
    fac = lambda fid, cin, rel, created, serial, product='RCF', cat='CAT-A', limit='60000000': dict(
        run_date='20261105', source_system_name='DEMO', country_code='GB', facility_id=fid, cin=cin, relationship_id=rel, product_code=product,
        limit_cat=cat, facility_creation_date=created, loan_approva_dt='0', credit_proposal_serial_no=serial, proposed_limit=limit,
        facility_ccy='EUR', loan_maturity_dt='20270801')
    write(out, 'facilities', [
        fac('SUBA1', 'C100', 'RA', '20150101', 'S0001'), fac('SUBB1', 'C200', 'RB', '20180101', 'S0002', cat='CAT-B'),
        fac('FACC1', 'C300', 'RC', '20261010', 'S0003', product='BRIDGE'), fac('FACD1', 'C400', 'RD', '20160101', 'S0004')], parts=2)
    write(out, 'drr', [
        dict(reporting_date='20261105', run_date='20261105', source_system_name='DEMO', rpt_facility_country_code='GB', drr_mastergroup_id='MGB0002',
             cin='C200', facility_id='DRRB1', drr_uid='U200', facility_type_code='FLNS', approved_limit='100', approved_limit_ccy='USD', utilisation='85', utilisation_ccy='USD'),
        dict(reporting_date='20261105', run_date='20261105', source_system_name='DEMO', rpt_facility_country_code='GB', drr_mastergroup_id='NO MSG',
             cin='C777', facility_id='DRRX1', drr_uid='U777', facility_type_code='FLNS', approved_limit='100', approved_limit_ccy='USD', utilisation='10', utilisation_ccy='USD')])
    write(out, 'pvd', [dict(joi_date='2026-10-31', joi_relationship_id='PVDREL4', joi_key='K4', drr_utils='50', drr_act_limit='100', drr_fac_category='CAT-A', drr_crr='3.1')])
    write(out, 'kyc', [dict(run_date='20261105', source_system_name='DEMO', cin='C100', related_case_id='CASE1', review_purpose_code='NTB',
                            review_request_created_time_stamp='2026-10-20 09:00:00', related_case_status='OPEN')])
    write(out, 'covenants', [dict(run_date='20261105', source_system_name='DEMO', country_code='GB', relationship_id='RD', facility_id='FACD1',
                                  covenant_id='COV1', covenant_type='FINANCIAL', active_testing_id='T1', active_testing_final_value='2.6',
                                  active_testing_testing_threshold_value='3', active_testing_testing_threshold_operator='<=',
                                  active_testing_approval_status='APPROVED', reporting_dt='2026-10-15')])
    ar = lambda cin, serial, approval, crr: dict(source_system_unique_id='U' + serial, source_system_name='DEMO', country_code='GB', carm_instance='X', cin=cin,
                                                 credit_proposal_serial_no=serial, run_date='20261105', record_start_dt='20260101', record_end_dt='99991231',
                                                 latest_record='CURRENT', approval_dt=approval, crr_scale='1', final_crr=crr)
    write(out, 'application_ratings', [ar('C100', 'S0001', '20150110', '2.2'), ar('C300', 'S0003', '20261017', '3.1'), ar('C400', 'S0004', '20160105', '4.1')])
    (out / 'reference').mkdir()
    with (out / 'reference' / 'clo_fx_reference.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['run_date', 'currency', 'rows_with_rate', 'fx_to_usd_median', 'fx_to_usd_min', 'fx_to_usd_max'])
        w.writerow(['20261105', 'EUR', '10', '1.10', '1.09', '1.11'])
        w.writerow(['20261105', 'USD', '10', '1.0', '1.0', '1.0'])
    with (out / 'reviewed_links.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['source', 'identifier_type', 'identifier_value', 'client_id', 'mastergroup_id', 'valid_from', 'valid_to', 'link_basis'])
        w.writerow(['pvd', 'JOI_RELATIONSHIP_ID', 'PVDREL4', 'PVD:PVDREL4', 'MGD0004', '', '', 'reviewed_demo_link'])
    return out


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', required=True)
    print('Wrote synthetic portfolio extract to', build(p.parse_args().out))
