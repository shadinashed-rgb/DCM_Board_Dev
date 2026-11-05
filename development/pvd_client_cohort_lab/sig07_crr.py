#!/usr/bin/env python3
"""Add Application Ratings CRR context to the existing signal CSV.

Only CRR fields are contributed by this source. Records are candidate application
states, not one authoritative group rating or a confirmed advisory engagement.

development-2: rating advisory (SIG07) is sourced from CME call reports per the DCM
meeting decision, so CRR rows are emitted as CTX_CREDIT context, not SIG07 evidence.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CLIENTS={'vodafone':('MG001356','VODAFONE'),'siemens_energy':('MG102229','Siemens Energy'),'softbank':('MG101624','SOFTBANK')}
SENTINELS={'','NULL','NONE','N/A','XNA','NO CRR','\\N'}
TABLE='delta.prod_credit_and_lending_gda.application_ratings'


def read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);rows=list(reader)
        if any(None in r or None in r.values() for r in rows):raise ValueError('Malformed CSV: '+str(path))
        return reader.fieldnames or [],rows


def day(value):
    value=str(value or '').strip()
    if value=='99991231':return None
    try:
        return date.fromisoformat(value[:10] if '-' in value else value[:4]+'-'+value[4:6]+'-'+value[6:8]).isoformat()
    except ValueError:return None


def norm(value):return str(value or '').strip().upper()
def fingerprint(row):return hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()


def select_context(rows,as_of):
    """Latest supplied snapshot per publishing scope, then candidate validity periods."""
    usable=[];latest={};counts=Counter(input_rows=len(rows))
    for r in rows:
        observed=day(r.get('run_date'))
        if not observed or observed>as_of:
            counts['invalid_or_future_snapshot']+=1;continue
        scope=tuple(norm(r.get(c)) for c in ['source_system_name','country_code','carm_instance'])
        latest[scope]=max(latest.get(scope,''),observed);usable.append((r,scope,observed))
    result=[];seen=set()
    for r,scope,observed in usable:
        if observed!=latest[scope]:counts['older_snapshot_rows']+=1;continue
        start,end=day(r.get('record_start_dt')),day(r.get('record_end_dt'))
        if (start and start>observed) or (end and end<observed):counts['out_of_effective_period']+=1;continue
        period_known=bool(start and (end or str(r.get('record_end_dt'))=='99991231'))
        r=dict(r,_selection_known=period_known)
        key=fingerprint({k:v for k,v in r.items() if not k.startswith('_sig07_') and not k.startswith('_input_')})
        if key in seen:counts['exact_duplicates']+=1;continue
        seen.add(key);result.append(r)
    counts['candidate_rows']=len(result)
    return result,dict(counts)


def export(input_dir,base_csv,output,as_of,identifier_inventory=None):
    as_of=date.fromisoformat(as_of).isoformat();input_dir=Path(input_dir);output=Path(output)
    if output.exists():raise ValueError('Output exists; choose a new directory')
    inventory=Path(identifier_inventory) if identifier_inventory else ROOT/'sql_templates/sig07_application_ratings_20261104/client_identifier_candidates.csv'
    _,ids=read(inventory)
    allowed=defaultdict(set)
    for r in ids:
        if r['identifier_kind']=='CIN':allowed[norm(r['identifier_value'])].add(r['mastergroup_id'])
    base_fields,base=read(base_csv)
    if not base or not {'signal_id','source','evidence_id'}<=set(base_fields):raise ValueError('Base CSV must be the consolidated signal evidence export')
    hashes={str(Path(base_csv).resolve()):hashlib.sha256(Path(base_csv).read_bytes()).hexdigest(),str(inventory.resolve()):hashlib.sha256(inventory.read_bytes()).hexdigest()}
    additions=[];selection=[]
    required={'run_date','cin','final_crr','crr_scale','record_start_dt','record_end_dt','credit_proposal_serial_no'}
    for label,(group,client) in CLIENTS.items():
        files=[p for p in sorted(input_dir.glob(f'application_ratings_{label}*.csv')) if 'profile' not in p.stem]
        full=[p for p in files if p.stem.endswith('_full')]
        if full:files=full
        raw=[]
        for path in files:
            fields,records=read(path)
            if not required<=set(fields):raise ValueError('Missing Application Ratings CRR columns: '+str(path))
            hashes[str(path.resolve())]=hashlib.sha256(path.read_bytes()).hexdigest()
            for record,r in enumerate(records,2):
                r.update(_input_file=path.name,_input_record=str(record));raw.append(r)
        selected,counts=select_context(raw,as_of)
        selection.append(dict(mastergroup_id=group,client=client,**counts))
        for r in selected:
            cin=norm(r['cin']);groups=allowed.get(cin,set())
            unique_group=groups=={group}
            observed=day(r['run_date']);code=str(r['final_crr']).strip()
            has_crr=norm(code) not in SENTINELS
            reason=['crr_context_only_rating_advisory_source_is_call_reports','application_version_rule_requires_validation']
            if not unique_group:reason.append('cin_cohort_link_unresolved')
            if not r['_selection_known']:reason.append('effective_period_unknown')
            if not has_crr:reason.append('missing_final_crr')
            key=[r.get(c,'') for c in ['source_system_name','country_code','carm_instance','branch_code','cin','customer_id','relationship_id','credit_proposal_serial_no','record_start_dt','source_system_unique_id']]
            record_key=json.dumps(key,separators=(',',':'))
            eid=hashlib.sha256(('CTX_CREDIT|crr_context|development-2|'+record_key+'|'+observed).encode()).hexdigest()
            details=dict(final_crr_raw=code,crr_scale=r['crr_scale'],proposed_crr=r.get('proposed_crr',''),approved_crr=r.get('approved_crr',''),
                previous_crr=r.get('previous_crr',''),latest_record=r.get('latest_record',''),latest_approved_appl_flag=r.get('latest_approved_appl_flag',''),
                source_mastergroup_name=r.get('mastergroup_name',''),selection='latest source/country/CARM snapshot then effective-period candidates',advisory_trigger_verified=False)
            row={c:'' for c in base_fields}
            row.update(client=client,mastergroup_id=group if unique_group else '',signal_id='CTX_CREDIT',signal_name='Credit category and rating context',source='application_ratings',
                component='crr_context',review_type='crr_context',assessment_status='needs_validation' if has_crr and unique_group and r['_selection_known'] else 'unavailable',
                business_trigger='',observation_date=observed,event_date=day(r.get('approval_dt')) or '',assessment_date=as_of,export_date=as_of,
                stale=str((date.fromisoformat(as_of)-date.fromisoformat(observed)).days>30),cins=r['cin'],source_countries=r.get('country_code',''),
                metric='crr_code',metric_value=code if has_crr else '',validation_reason=';'.join(reason),
                mapping_status='candidate_cin_cohort_lookup' if unique_group else 'unresolved_cin_cohort_lookup',cohort_mapping_status='development_candidate_not_historical_membership_proof',
                source_table=TABLE,source_record_references=f'{r["_input_file"]}:record {r["_input_record"]}',record_key=record_key,evidence_id=eid,
                crr=code if has_crr else '',crr_raw=code,crr_scale=r['crr_scale'],previous_crr=r.get('previous_crr',''),proposed_crr=r.get('proposed_crr',''),
                approved_crr=r.get('approved_crr',''),proposed_manual_crr=r.get('proposed_manual_crr',''),overriden_crr=r.get('overriden_crr',''),
                approval_date=day(r.get('approval_dt')) or '',record_start_date=day(r['record_start_dt']) or '',record_end_raw=r['record_end_dt'],
                latest_record=r.get('latest_record',''),latest_approved_appl_flag=r.get('latest_approved_appl_flag',''),
                credit_proposal_serial_no=r['credit_proposal_serial_no'],source_system_unique_id=r.get('source_system_unique_id',''),customer_id=r.get('customer_id',''),relationship_id=r.get('relationship_id',''),
                customer_name=r.get('customer_name',''),original_mastergroup_name=r.get('mastergroup_name',''),details_json=json.dumps(details))
            additions.append(row)
    if not additions:raise ValueError('No current/unknown-period Application Ratings candidates found')
    # Keep competing current CRRs visible; do not choose one rating per CIN/group.
    codes=defaultdict(set)
    for r in additions:
        if r['crr']:codes[(r['mastergroup_id'],r['source_countries'],r['cins'])].add(r['crr'])
    for r in additions:
        r['multiple_crrs_for_cin']=len(codes[(r['mastergroup_id'],r['source_countries'],r['cins'])])>1
    fields=list(dict.fromkeys(base_fields+[k for r in additions for k in r]))
    combined=[r for r in base if r['source']!='application_ratings']+additions
    if len({r['evidence_id'] for r in combined})!=len(combined):raise ValueError('Duplicate evidence identifiers')
    output.mkdir(parents=True)
    def save(name,rows):
        with (output/name).open('x',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    save('SIG07_Application_Ratings_CRR.csv',additions)
    save('DCM_Run_003_All_Signal_Evidence_With_CRR.csv',combined)
    summary=dict(as_of=as_of,base_rows=len(base),application_crr_candidates=len(additions),nonmissing_crr=sum(bool(r['crr']) for r in additions),
        missing_crr=sum(not r['crr'] for r in additions),combined_rows=len(combined),selection=selection,input_sha256=hashes,
        scope='Application Ratings adds CRR context only (CTX_CREDIT); rating advisory (SIG07) requires CME call reports; existing other-source evidence is retained.')
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    (output/'manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True);p.add_argument('--base',required=True);p.add_argument('--out',required=True)
    p.add_argument('--as-of',required=True);p.add_argument('--identifier-inventory')
    a=p.parse_args();print(json.dumps(export(a.input,a.base,a.out,a.as_of,a.identifier_inventory),indent=2))
