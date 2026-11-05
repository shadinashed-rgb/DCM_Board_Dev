"""Small, synthetic fixtures only. Never imports or packages project client data."""
import json
from pathlib import Path
from bond_radar import ROOT, SOURCES, write_csv, dump

def build_demo(output):
    output=Path(output)
    if output.exists():raise ValueError('Demo output already exists; choose a new directory')
    folder=output/'input';folder.mkdir(parents=True)
    rows={source:[] for source in SOURCES}
    def clo(facility,cin,gid,observed,drawn,limit='100',mg='',**extra):
        row=dict(source_system='DEMO',mapping_system='DEMO_UK',hsbc_booking_legal_entity='DEMO_BANK',sub_lim_id=facility,rct_facility_ref='',facility_id='',obligor_cin=cin,rct_gid=gid,rct_mastergroup_id=mg,rct_mastergroup_name='',run_date=observed,local_product_type_lbs='REV',facility_drawn_amount=drawn,facility_limit_amount=limit,facility_currency='GBP')
        row.update(extra);rows['clo'].append(row)
        return row
    first=clo('F001','000001','G001','20261001','40')
    clo('F001','000001','G001','20261028','80')
    rows['clo'].append(dict(rows['clo'][-1]))  # repeated amount, not an additional facility
    clo('F002','000002','G002','20261028','70')  # exactly 70 does not exceed threshold
    clo('F003','000003','G003','20261028','75',limit='0')
    clo('F004','000004','G004','20261028','80',mg='MG_ORIGINAL')
    clo('F005','000005','G005','20261028','80')  # CIN/GID disagree
    clo('F006','000006','G006','20261001','80')  # later mapping must not leak backward
    clo('F007','000007','G007','20261028','80')
    clo('F007','000008','G008','20261028','80')  # one shared facility, two borrowers/groups
    clo('F008','000009','G009','20261028','80')
    clo('F008','000009','G009','20261028','90')  # conflicting observation, withhold ratio
    def cp(cin,gid,mg,observed='20260930',status='A'):
        rows['counterparty'].append(dict(customer_relationship_cin_identifier=cin,customer_relationship_gid_identifier=gid,mastergroup_esr_identifier=mg,customer_relationship_lifecycle_status_code=status,run_date=observed))
    cp('000001','G001','MG001');cp('000002','G002','MG002');cp('000003','G003','MG003')
    cp('000004','G004','MG_OTHER');cp('000005','','MG005');cp('','G005','MG_DIFFERENT')
    cp('000006','G006','MG_FUTURE','20261020');cp('000007','G007','MG007');cp('000008','G008','MG008')
    cp('000009','G009','MG009')
    rows['facilities']=[dict(run_date='20261028',facility_id='DEMO_NEW_FAC',source_system_name='DEMO',country_code='GB',cin='000001',relationship_id='REL1',customer_id='C1',facility_creation_date='2026-10-20',product_code='DEMO_RCF',limit_cat='DEMO_CATEGORY',limit_category_type='DEMO',advised_ind='1'),
                        # Same ID as CLO sub-limit F001: supplies the Cat A category for SIG01.
                        dict(run_date='20261028',facility_id='F001',source_system_name='DEMO',country_code='GB',cin='000001',relationship_id='REL1',customer_id='C1',facility_creation_date='2015-01-01',product_code='DEMO_RCF',limit_cat='CAT-A',limit_category_type='DEMO',advised_ind='1')]
    rows['kyc']=[dict(run_date='20261028',cin='000001',related_case_id='CASE1',review_purpose_code='NTB',review_request_created_time_stamp='2026-10-21',related_case_status='COMPLT'),dict(run_date='20261028',cin='000001',related_case_id='CASE_OLD',review_purpose_code='NTB',review_request_created_time_stamp='2018-01-01',related_case_status='COMPLT')]
    rows['covenants']=[dict(run_date='20261028',source_system_name='DEMO',country_code='GB',facility_id='DEMO_COV_FAC',covenant_id='COV1',active_testing_id='TEST1',relationship_id='REL1',covenant_type='Financial',active_testing_final_value='4',active_testing_testing_threshold_value='3',active_testing_testing_threshold_operator='<=',active_testing_approval_status='DEMO_APPROVED',reporting_dt='2026-10-25'),
                       # 2.6x against a 3.0x maximum: no breach, but within half a turn (pressure).
                       dict(run_date='20261028',source_system_name='DEMO',country_code='GB',facility_id='DEMO_COV_FAC',covenant_id='COV3',active_testing_id='TEST3',relationship_id='REL1',covenant_type='Financial',active_testing_final_value='2.6',active_testing_testing_threshold_value='3',active_testing_testing_threshold_operator='<=',active_testing_approval_status='DEMO_APPROVED',reporting_dt='2026-10-25'),
                       # 2.4x against 3.0x: outside the half-turn band.
                       dict(run_date='20261028',source_system_name='DEMO',country_code='GB',facility_id='DEMO_COV_FAC',covenant_id='COV4',active_testing_id='TEST4',relationship_id='REL1',covenant_type='Financial',active_testing_final_value='2.4',active_testing_testing_threshold_value='3',active_testing_testing_threshold_operator='<=',active_testing_approval_status='DEMO_APPROVED',reporting_dt='2026-10-25'),dict(run_date='20261028',source_system_name='DEMO',country_code='GB',facility_id='DEMO_COV_FAC',covenant_id='COV2',active_testing_id='TEST2',relationship_id='REL1',covenant_type='NonFinancial',covenant_status='Overdue')]
    rows['drr']=[dict(reporting_date='20261027',run_date='20261028',facility_id='DRR1',source_system_name='DEMO',rpt_facility_country_code='GB',cin='000001',drr_mastergroup_id='MG001',approved_limit='100',utilisation='80',approved_limit_ccy='GBP',utilisation_ccy='GBP')]
    rows['pvd']=[dict(joi_date='2026-10-27',joi_relationship_id='REL_PVD1',joi_key='PVD1',drr_utils='80',drr_act_limit='100',drr_carm_limit='100',drr_crr='DEMO_3',drr_fac_category='DEMO_CAT',joi_facility_category='DEMO_CAT')]
    for source,data in rows.items():
        columns=list(dict.fromkeys(SOURCES[source]['required']+SOURCES[source]['desired']+[key for row in data for key in row]))
        write_csv(folder/(source+'.csv'),columns,([row.get(c,'') for c in columns] for row in data))
        dump(folder/(source+'.metadata.json'),json.dumps({'source':source,'synthetic':True,'coverage':'Deliberately constructed test cases; not bank data.'},indent=2))
    columns=['source','identifier_type','identifier_value','client_id','mastergroup_id','valid_from','valid_to']
    links=[['pvd','JOI_RELATIONSHIP_ID','REL_PVD1','CIN:000001','MG001','2026-01-01',''],['covenants','RELATIONSHIP_ID','REL1','CIN:000001','MG001','2026-01-01','']]
    write_csv(folder/'identity_links.csv',columns,links)
    cfg=json.loads((ROOT/'config.json').read_text())
    cfg['rule_version']='synthetic-demo-only'
    cfg['counterparty']['settings_verified']=True
    cfg['counterparty']['catalog_confirmed']=True
    cfg['identity']['cin_namespace_verified']=True
    cfg['sig01'].update(definitions_verified=True,maximum_comparison_gap_days=45)
    cfg['sig01']['materiality'].update(threshold_amount=10,threshold_currency='GBP')
    for source in ('clo','drr','pvd'):cfg['utilisation'][source]['definitions_verified']=True
    cfg['utilisation']['pvd'].update(verified_currency='GBP',grain_verified=True)
    cfg['sig02'].update(definitions_verified=True,qualifying_product_codes=['DEMO_RCF'])
    cfg['sig04']['definitions_verified']=True
    cfg['covenants'].update(definitions_verified=True,approved_statuses=['DEMO_APPROVED'])
    dump(output/'demo_config.json',json.dumps(cfg,indent=2))
    dump(output/'README.md','# Synthetic demonstration\n\nThese made-up records exercise the workflow. The demo configuration deliberately confirms synthetic definitions to test both positive and negative branches. Never use it for real data; start real runs with the package config.json.\n')
