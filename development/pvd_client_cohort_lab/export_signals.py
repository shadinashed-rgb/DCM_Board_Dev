"""Export the completed DCM_Run_003 signal evidence as one readable, auditable CSV.

No signal is recalculated or promoted to a confirmed alert. Original identifiers,
source value sets, conflicts and record references remain available. Assessment
date is the original run's date; export date is recorded separately.
"""
from collections import Counter, defaultdict
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

from cohort import engine

NAMES={'MG001356':'VODAFONE','MG102229':'Siemens Energy','MG101624':'SOFTBANK'}
SIGNALS={'SIG01':'Material drawing on a Cat A bank facility','SIG02':'New RCF, term loan or bridge (credit approval)','SIG06':'Financial covenant breach or pressure','CTX_UTIL':'Facility utilisation context','CTX_CREDIT':'Credit category and rating context'}
FILES={'clo':'clo_current_and_previous.csv','drr':'drr_current.csv','facilities':'facilities_current.csv','pvd':'pvd_current.csv'}


def digest(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def export(cohort_dir, signal_dir, original_exports, target, export_date='2026-11-04'):
    cohort_dir=Path(cohort_dir);signal_dir=Path(signal_dir);original_exports=Path(original_exports);target=Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():raise ValueError('Export already exists; choose a new output file')
    original_rows={}
    fingerprints={}
    for source,name in FILES.items():
        p=original_exports/name
        fingerprints[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        lookup=defaultdict(list)
        with p.open(encoding='utf-8-sig',newline='') as f:
            for record,row in enumerate(csv.DictReader(f),2):
                lookup[digest({k.strip().lower():v for k,v in row.items()})].append(f'{name}:record {record}')
        original_rows[source]=lookup
    db=sqlite3.connect((signal_dir/'results/bond_radar.sqlite').resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    cohort=sqlite3.connect((cohort_dir/'cohort.sqlite').resolve().as_uri()+'?mode=ro',uri=True);cohort.row_factory=sqlite3.Row
    lineage={(r['source'],r['raw_id']):r['cohort_raw_id'] for r in db.execute('SELECT * FROM cohort_row_groups')}
    payloads={(r['source'],r['raw_id']):json.loads(r['payload']) for r in cohort.execute('SELECT * FROM raw_rows')}

    def references(source, ids):
        result=[]
        for raw_id in ids:
            row=payloads[(source,lineage[(source,raw_id)])]
            matches=original_rows[source].get(digest(row),[])
            if not matches:raise ValueError(f'Missing original source reference: {source}/{raw_id}')
            result.extend(matches)
        return ' | '.join(dict.fromkeys(result))

    def values(rows,*columns):
        return ' | '.join(sorted({str(r.get(c)).strip() for r in rows for c in columns if engine.norm(r.get(c)) is not None}))

    rows=[]
    for evidence in db.execute('SELECT * FROM cohort_signal_evidence ORDER BY cohort_mastergroup_id,signal_id,source,record_key'):
        e=dict(evidence);details=json.loads(e['details_json']);ids=json.loads(e['source_rows'])
        source=e['source'];raw=[payloads[(source,lineage[(source,i)])] for i in ids]
        observation=db.execute('SELECT payload FROM observations WHERE source=? AND record_key=? AND observation_date=?',(source,e['record_key'],e['observation_date'])).fetchone()
        conflicts=json.loads(observation[0]).get('__conflicts',[]) if observation else []
        high=details.get('threshold_exceeded_for_testing') if e['component']=='utilisation' else None
        recent=(details.get('event_age_days') is not None and 0<=details['event_age_days']<=details['event_lookback_days'] and e['assessment_status']!='unavailable') if e['signal_id']=='SIG02' else None
        material=details.get('material_for_testing') if e['signal_id']=='SIG01' else None
        pressure=details.get('pressure_for_testing') if e['component']=='financial_covenant' else None
        if e['assessment_status']=='unavailable':review_type='unavailable'
        elif material:review_type='material_drawing_for_testing'
        elif pressure:review_type='covenant_pressure_for_testing'
        elif recent:review_type='recent_approval_for_testing'
        elif high:review_type='utilisation_above_70_context'
        elif e['signal_id']=='CTX_CREDIT':review_type='credit_category_context'
        elif e['signal_id']=='SIG01':review_type='drawing_comparison'
        else:review_type='other_evidence_for_review'
        group=e['cohort_mastergroup_id'] or ''
        rows.append(dict(
            client=NAMES.get(group,''),mastergroup_id=group,signal_id=e['signal_id'],signal_name=SIGNALS[e['signal_id']],
            source=source,component=e['component'],review_type=review_type,assessment_status=e['assessment_status'],
            business_trigger=e['triggered'],above_70_for_testing=high,recent_creation_for_testing=recent,
            material_drawing_for_testing=material,covenant_pressure_for_testing=pressure,
            observation_date=e['observation_date'],event_date=e['event_date'],assessment_date=e['assessment_date'],export_date=export_date,
            stale=bool(e['stale']),facility_ids=values(raw,'facility_id'),clo_sub_limit_ids=values(raw,'sub_lim_id'),
            clo_facility_references=values(raw,'rct_facility_ref'),drr_uids=values(raw,'drr_uid'),pvd_keys=values(raw,'joi_key'),
            cins=values(raw,'cin','obligor_cin'),gids=values(raw,'gid','rct_gid'),
            source_countries=values(raw,'country_code','rpt_facility_country_code'),
            product_codes=values(raw,'product_code','facility_type_code','local_product_type_lbs'),
            limit_categories=values(raw,'limit_cat','drr_fac_category','joi_facility_category'),
            rating_values=values(raw,'drr_crr'),facility_grade_codes=values(raw,'facility_grade_code'),advised_ind_values=values(raw,'advised_ind'),
            source_creation_dates=values(raw,'facility_creation_date'),
            metric=e['metric_name'],metric_value=e['value'],previous_metric_value=e['previous_value'],
            current_drawn=details.get('current_drawn'),previous_drawn=e['previous_value'] if e['signal_id']=='SIG01' else '',
            utilisation_amount=details.get('numerator') if e['component']=='utilisation' else '',approved_limit=e['denominator'],
            currency=e['currency'] or details.get('currency',''),proposed_limit=details.get('limit'),
            source_currencies=values(raw,'facility_ccy','facility_currency','approved_limit_ccy','utilisation_ccy'),
            threshold_percent=details.get('threshold_percent'),event_age_days=details.get('event_age_days'),
            event_lookback_days=details.get('event_lookback_days'),previous_observation_date=details.get('previous_observation_date'),
            comparison_gap_days=details.get('comparison_gap_days'),current_drawn_imputed_zero=details.get('current_missing_imputed_zero'),
            drawn_field=details.get('drawn_field') if e['signal_id']=='SIG01' else '',limit_category=details.get('limit_category') if e['signal_id']=='SIG01' else '',
            limit_category_basis=details.get('limit_category_basis') if e['signal_id']=='SIG01' else '',cat_a_eligible=details.get('cat_a_eligible') if e['signal_id']=='SIG01' else '',
            materiality_status=details.get('materiality_status') if e['signal_id']=='SIG01' else '',materiality_threshold=(f"{details.get('threshold_currency')} {details.get('threshold_amount')}" if e['signal_id']=='SIG01' else ''),
            drawing_in_threshold_currency=details.get('drawing_in_threshold_currency') if e['signal_id']=='SIG01' else '',
            hsbc_participation_share_percent=details.get('hsbc_participation_share_percent') if e['signal_id']=='SIG01' else '',inferred_total_drawing=details.get('inferred_total_drawing') if e['signal_id']=='SIG01' else '',
            event_basis=details.get('event_basis') if e['signal_id']=='SIG02' else '',credit_proposal_serial_no=details.get('credit_proposal_serial_no') if e['signal_id']=='SIG02' else '',
            credit_approval_date='',credit_approval_source='',approval_matches_creation_date='',
            covenant_headroom_turns=details.get('headroom_turns') if e['signal_id']=='SIG06' else '',
            previous_drawn_imputed_zero=details.get('previous_missing_imputed_zero'),conflicting_fields=' | '.join(conflicts),
            validation_reason=e['reason'],mapping_status=e['mapping_status'],cohort_mapping_status=e['cohort_group_status'],
            source_table=engine.SOURCES[source]['table'],source_record_references=references(source,ids),
            previous_source_record_references=references(source,details['previous_source_rows']) if details.get('previous_source_rows') else '',
            record_key=e['record_key'],evidence_id=e['evidence_id'],details_json=e['details_json']))
    if not rows:raise ValueError('No signal evidence available for export')
    assert len({r['evidence_id'] for r in rows})==len(rows)
    assert all(hashlib.sha256(Path(name).read_bytes()).hexdigest()==value for name,value in fingerprints.items())
    with target.open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with target.open(encoding='utf-8-sig',newline='') as f:
        check=list(csv.DictReader(f))
    assert len(check)==len(rows) and all(r['source_record_references'] for r in check)
    db.close();cohort.close()
    return target
