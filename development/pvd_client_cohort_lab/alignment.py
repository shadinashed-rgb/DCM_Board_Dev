#!/usr/bin/env python3
"""development-2 alignment step: attach the internal credit approval date to SIG02.

DCM meeting decision: the event date for new RCF / term loan / bridge facilities is
the internal credit approval date (earlier than signing). Facilities carries a
credit_proposal_serial_no; Application Ratings carries the same serial with an
approval_dt. Where the serial links to exactly one approval date (preferring rows
with the same CIN), that date becomes the SIG02 event date. The link is a
development association to validate with the credit team, not an approved join.

The combined evidence is written to a fresh file; inputs are never modified.
"""
import argparse
from collections import defaultdict
import csv
from datetime import date
import json
from pathlib import Path

from sig07_crr import day, read


def approval_index(ratings_dir):
    """serial -> list of (cin, approval date, file:record) from Application Ratings."""
    index=defaultdict(list);ratings_dir=Path(ratings_dir)
    files=sorted(ratings_dir.glob('*_full.csv')) or sorted(ratings_dir.glob('*.csv'))
    for path in files:
        _,rows=read(path)
        for record,r in enumerate(rows,2):
            serial=str(r.get('credit_proposal_serial_no','')).strip()
            approved=day(r.get('approval_dt'))
            if serial and approved:index[serial].append((str(r.get('cin','')).strip(),approved,f'{path.name}:record {record}'))
    return index


def link(row,index):
    serial=str(row.get('credit_proposal_serial_no','')).strip()
    if not serial:return None,'no_credit_proposal_serial',[]
    candidates=index.get(serial,[])
    if not candidates:return None,'serial_not_found_in_application_ratings',[]
    cins={c.strip() for c in str(row.get('cins','')).split('|') if c.strip()}
    same_cin=[c for c in candidates if c[0] in cins]
    chosen=same_cin or candidates
    dates=sorted({c[1] for c in chosen})
    if len(dates)>1:return None,'conflicting_approval_dates',[c[2] for c in chosen]
    return dates[0],'serial_and_cin_match' if same_cin else 'serial_match_only',[c[2] for c in chosen]


def apply(combined_csv,ratings_dir,target,as_of):
    fields,rows=read(combined_csv);target=Path(target)
    if target.exists():raise ValueError('Output already exists; choose a new file')
    index=approval_index(ratings_dir);counts=defaultdict(int)
    for r in rows:
        if r['signal_id']!='SIG02':continue
        approved,basis,refs=link(r,index);counts[basis]+=1
        r['credit_approval_source']=f'application_ratings.approval_dt ({basis})' if approved else basis
        creation=r.get('source_creation_dates','').strip()
        creation_iso=day(creation) if creation and '|' not in creation else None
        if not approved:continue
        r['credit_approval_date']=approved
        r['approval_matches_creation_date']=str(creation_iso==approved) if creation_iso else ''
        if r['assessment_status']=='unavailable':continue
        age=(date.fromisoformat(as_of)-date.fromisoformat(approved)).days
        lookback=int(r.get('event_lookback_days') or 90)
        r.update(event_date=approved,event_age_days=str(age),event_basis='credit_approval_date',
                 recent_creation_for_testing=str(0<=age<=lookback))
        reasons=[x for x in r['validation_reason'].split(';') if x and x!='event_date_is_candidate_approval_date']
        reasons.append('approval_link_by_serial_unverified')
        r['validation_reason']=';'.join(reasons)
        r['review_type']='recent_approval_for_testing' if 0<=age<=lookback else 'other_evidence_for_review'
        details=json.loads(r.get('details_json') or '{}')
        details.update(credit_approval_date=approved,credit_approval_link=basis,credit_approval_references=refs)
        r['details_json']=json.dumps(details,default=str)
        counts['approval_date_applied']+=1
        if r['approval_matches_creation_date']=='True':counts['approval_equals_creation']+=1
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    return dict(rows=len(rows),sig02_approval_linking=dict(counts))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--combined',required=True);p.add_argument('--ratings',required=True);p.add_argument('--out',required=True);p.add_argument('--as-of',required=True)
    a=p.parse_args();print(json.dumps(apply(a.combined,a.ratings,a.out,a.as_of),indent=2))
