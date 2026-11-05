"""Synthetic PVD-first discovery and iterative identifier-review demonstration."""
import csv
import json
from pathlib import Path
from cohort import ROOT, REVIEW_COLUMNS, analyse, dump, norm, run_signals, seed_sql, source_sql, write_csv
import bond_radar as engine

def make_inputs(folder):
    folder=Path(folder);folder.mkdir(parents=True)
    rows={s:[] for s in engine.SOURCES}
    targets=[('MG001356','VODAFONE','00000001','G_DEMO_1'),('MG102229','Siemens Energy','00000002','G_DEMO_2'),('MG101624','SOFTBANK','00000003','G_DEMO_3')]
    for mg,name,cin,gid in targets:
        pvd=dict(joi_date='2026-10-29',joi_relationship_id=mg,joi_relationship_name=name+' DEMO',drr_supergroup_id='SG_SHARED_DEMO',drr_supergroup_name='SHARED DEMO SUPERGROUP',omn_mastergroup_name=name,joi_key='00000999',drr_utils='80',drr_act_limit='100',drr_carm_limit='100',drr_crr='DEMO_RATING',drr_fac_category='DEMO_CAT',joi_facility_category='DEMO_CAT',etlmonth='2026-10-29')
        rows['pvd'].append(pvd)
        rows['drr'].append(dict(reporting_date='20261029',run_date='20261029',facility_id='DRR_'+cin,source_system_name='DEMO',rpt_facility_country_code='GB',drr_mastergroup_id=mg,cin=cin,gid=gid,app_relationship_id='DRR_REL_'+cin,approved_limit='100',utilisation='80',approved_limit_ccy='GBP',utilisation_ccy='GBP'))
        rows['clo'].append(dict(run_date='20261029',source_system='DEMO',mapping_system='DEMO_UK',hsbc_booking_legal_entity='DEMO_BANK',rct_mastergroup_id=mg if mg!='MG101624' else '',rct_mastergroup_name=name,obligor_cin=cin,rct_gid=gid,obligor_customer_name=name+' ENTITY DEMO',sub_lim_id='CLO_'+cin,rct_facility_ref='',facility_id='',local_product_type_lbs='REV',facility_currency='GBP',facility_drawn_amount='80',facility_limit_amount='100'))
        rows['counterparty'].append(dict(run_date='20261028',customer_relationship_cin_identifier=cin,customer_relationship_gid_identifier=gid,mastergroup_esr_identifier=mg,customer_relationship_lifecycle_status_code='A'))
        rows['facilities'].append(dict(run_date='20261029',source_system_name='DEMO',country_code='GB',facility_id='FAC_'+cin,cin=cin,relationship_id='REL_'+cin,customer_id='CUST_'+cin,facility_creation_date='2026-10-20',product_code='DEMO_RCF',limit_cat='DEMO_CAT',limit_category_type='DEMO',advised_ind='1'))
        rows['kyc'].append(dict(run_date='20261029',cin=cin,related_case_id='CASE_'+cin,legal_name=name+' DEMO',review_purpose_code='NTB',review_purpose_desc='DEMO NEW TO BANK',review_request_created_time_stamp='2026-10-21'))
        rows['covenants'].append(dict(run_date='20261029',source_system_name='DEMO',country_code='GB',facility_id='COV_FAC_'+cin,covenant_id='COV_'+cin,active_testing_id='TEST_'+cin,relationship_id='REL_'+cin,covenant_type='Financial',active_testing_final_value='4',active_testing_testing_threshold_value='3',active_testing_testing_threshold_operator='<=',active_testing_approval_status='DEMO_APPROVED',reporting_dt='2026-10-25'))
    rows['pvd'] += [dict(rows['pvd'][0]),dict(rows['pvd'][0],joi_relationship_id='PVD_SUB_DEMO',joi_relationship_name='Vodafone Holdings Demo',omn_mastergroup_name='VODAFONE'),dict(rows['pvd'][0],joi_relationship_id='PVD_AMBIGUOUS',joi_relationship_name='VODAFONE SOFTBANK DEMO',omn_mastergroup_name='',drr_supergroup_id='NO SPG')]
    rows['clo'].append(dict(rows['clo'][0],run_date='20261001',facility_drawn_amount='40'))
    rows['clo'].append(dict(rows['clo'][0]))
    for source,data in rows.items():
        columns=list(dict.fromkeys(engine.SOURCES[source]['required']+engine.SOURCES[source]['desired']+[c for row in data for c in row]))
        write_csv(folder/(source+'.csv'),columns,([row.get(c,'') for c in columns] for row in data))
        dump(folder/(source+'.metadata.json'),json.dumps({'synthetic':True,'source':source,'qualification':'Deliberately constructed fixture data, not bank records.'},indent=2))
    return targets

def read_review(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as handle:return list(csv.DictReader(handle))

def demo(output):
    output=Path(output).resolve()
    if output.exists():raise ValueError('Demo output exists; choose another directory')
    output.mkdir(parents=True)
    cfg=ROOT/'config.json';targets=make_inputs(output/'inputs_all')
    seed_sql(output/'sql_seed',cfg,'2026-10-01','2026-10-30')
    pvd_only=output/'inputs_pvd';pvd_only.mkdir()
    for ext in ('.csv','.metadata.json'):(pvd_only/('pvd'+ext)).write_bytes((output/'inputs_all'/('pvd'+ext)).read_bytes())
    first=analyse(pvd_only,output/'01_discovery','2026-10-30',cfg)
    review=read_review(first/'identifier_review.csv')
    for row in review:
        if row['proposed_type']=='PVD_RELATIONSHIP_ID' and (row['identifier_value']==row['mastergroup_id'] or row['identifier_value']=='PVD_SUB_DEMO' and row['mastergroup_id']=='MG001356'):
            row.update(decision='approve',evidence='SYNTHETIC fixture oracle verifies this PVD relationship/group association')
    write_csv(output/'approved_round1.csv',REVIEW_COLUMNS,([r[c] for c in REVIEW_COLUMNS] for r in review))
    source_sql(output/'sql_after_pvd',cfg,'2026-10-01','2026-10-30',output/'approved_round1.csv')
    second=analyse(output/'inputs_all',output/'02_bridge_discovery','2026-10-30',cfg,output/'approved_round1.csv')
    review=read_review(second/'identifier_review.csv')
    known={(mg,cin,gid) for mg,_,cin,gid in targets}
    for row in review:
        if row['proposed_type'] in ('CIN','GID') and any(row['mastergroup_id']==mg and row['identifier_value'] in (cin,gid) for mg,cin,gid in known):
            row.update(decision='approve',evidence='SYNTHETIC fixture oracle verifies shared identifier namespace/group membership')
    write_csv(output/'approved_entities.csv',REVIEW_COLUMNS,([r[c] for c in REVIEW_COLUMNS] for r in review))
    third=analyse(output/'inputs_all',output/'03_entity_coverage','2026-10-30',cfg,output/'approved_entities.csv')
    review=read_review(third/'identifier_review.csv');extra=[]
    for row in review:
        if row['origin_source']=='facilities' and row['proposed_type']=='RELATIONSHIP_ID':
            copy=dict(row);copy.update(review_id=row['review_id']+'-cov',target_source='covenants',decision='approve',evidence='SYNTHETIC fixture oracle verifies Facilities-to-Covenants relationship crosswalk');extra.append(copy)
    review += extra
    write_csv(output/'approved_final.csv',REVIEW_COLUMNS,([r[c] for c in REVIEW_COLUMNS] for r in review))
    final=analyse(output/'inputs_all',output/'04_reviewed_coverage','2026-10-30',cfg,output/'approved_final.csv')
    source_sql(output/'sql_reviewed_sources',cfg,'2026-10-01','2026-10-30',output/'approved_final.csv')
    run_signals(final,output/'05_signal_tests')
    dump(output/'README.md','# Synthetic PVD-first demonstration\n\nAll source rows and verification decisions in this directory are made-up fixtures. Actual target group labels/IDs are used only as the user-supplied seed configuration.\n\n01_discovery shows candidate-only PVD discovery and missing other sources. 02_bridge_discovery shows additional IDs exposed by source group anchors. 03_entity_coverage shows the reviewed entity IDs unlocking Facilities/KYC. 04_reviewed_coverage adds explicit verified covenant relationship bridges. 05_signal_tests contains default unverified-business-rule signal outputs. Do not reuse the synthetic approval CSVs for real data. Counterparty catalog confirmation remains unresolved because the demonstration cannot verify a live table.\n')
    return output
