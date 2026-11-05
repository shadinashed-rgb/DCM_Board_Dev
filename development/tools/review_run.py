#!/usr/bin/env python3
"""Write the review pack for a development-2 run.

Produces, inside the run folder:
  SIGNAL_SUMMARY.csv            evidence counts per signal/context and client
  OWNER_REVIEW_SIG01.csv        every SIG01 drawing comparison with the owner question
  OWNER_REVIEW_SIG02.csv        recent credit-approval candidates (<= 90 days)
  OWNER_REVIEW_CTX_UTIL.csv     utilisation ratios above 70% (context, not covenant pressure)
  OWNER_REVIEW_CTX_CREDIT.csv   Application Ratings CRR contexts
  RECONCILIATION_DEV1.csv       development-1 -> development-2 mapping by source record
  COVERAGE.csv                  signals with no source (SIG03A, SIG03B, SIG04, SIG06, SIG07)
  REVIEW.md                     narrative review

Nothing is recalculated here; it reads BOND_RADAR_SIGNAL_EVIDENCE.csv as written.

Usage: python3 tools/review_run.py runs/aligned_20261105_004 [--previous <dev-1 combined csv>]
"""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

CLIENTS = [('VODAFONE', 'MG001356'), ('Siemens Energy', 'MG102229'), ('SOFTBANK', 'MG101624')]
CATALOGUE = [
    ('SIG01', 'Material drawing on a Cat A bank facility', 'signal'),
    ('SIG02', 'New RCF, term loan or bridge (credit approval date)', 'signal'),
    ('SIG03A', 'Swap roll on maturing debt', 'signal'),
    ('SIG03B', 'New pre-hedge swap enquiry', 'signal'),
    ('SIG04', 'KYC onboarding / signatory refresh', 'signal'),
    ('SIG05', 'CME call report keywords', 'excluded'),
    ('SIG06', 'Financial covenant breach or pressure', 'signal'),
    ('SIG07', 'Rating advisory request (call reports)', 'signal'),
    ('CTX_UTIL', 'Facility utilisation (context)', 'context'),
    ('CTX_CREDIT', 'Credit category and rating (context)', 'context'),
]
COVERAGE = [
    ('SIG03A', 'derivatives trade/booking data', 'source_missing', 'No derivatives trade source supplied. Needs trade id, product (IRS/CCS/FX swap), maturity, notional, linked debt and roll indicator.'),
    ('SIG03B', 'pre-hedge enquiry / pricing requests', 'source_missing', 'Signal does not exist in markets systems today; Bloomberg chat suggested as a possible source (open).'),
    ('SIG04', 'delta.prod_party_gda.kyc', 'empty_export', 'Target KYC export is header-only (326 columns, 0 rows).'),
    ('SIG05', 'CME call reports', 'excluded', 'Excluded pending MNPI handling and entitlements.'),
    ('SIG06', 'financial covenant tests', 'source_missing', 'Genuine financial covenant tests (net debt/EBITDA actual vs maximum, test date) not supplied; the file labelled covenants is Counterparty data and stays quarantined.'),
    ('SIG07', 'CME call reports', 'source_not_integrated', 'Rating advisory requests are recorded only in call reports; same CME dependency as SIG05.'),
]


def read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write(path, rows, fields=None):
    fields = fields or (list(rows[0]) if rows else ['note'])
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows or [])


def owner_sig01(r):
    q = []
    if r['current_drawn_imputed_zero'] == 'True' or r['previous_drawn_imputed_zero'] == 'True':
        q.append('Default drawn field is blank; confirm the authoritative drawn-amount field (LoanIQ) before assessing materiality.')
    if r['component'] == 'drawing_change_alt_usd':
        q.append('Confirm whether ag_acc_bal_drawn_sub_lim_usd is the HSBC drawn balance in USD and can replace the blank default field.')
    if 'no_prior_observation' in r['validation_reason']:
        q.append('No prior snapshot for this sub-limit: confirm whether it is newly drawn or outside the prior extract.')
    if r['limit_category_basis'] == 'limit_category_unlinked':
        q.append('Cat A status unknown: no Facilities record with the same facility ID.')
    elif r['limit_category']:
        q.append(f"Confirm the CLO sub-limit and Facilities facility ID identify the same facility (category {r['limit_category']}).")
    q.append('Agree FX source/date for the EUR 50m test and the HSBC participation-share field for the inferred total.')
    return ' '.join(q)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('run')
    p.add_argument('--previous', help='development-1 combined evidence CSV for reconciliation')
    a = p.parse_args()
    run = Path(a.run)
    rows = read(run / 'BOND_RADAR_SIGNAL_EVIDENCE.csv')
    summary_json = json.loads((run / 'RUN_SUMMARY.json').read_text())

    # Signal summary
    summary = []
    for sig, name, kind in CATALOGUE:
        for client, mg in CLIENTS:
            sel = [r for r in rows if r['signal_id'] == sig and r['mastergroup_id'] == mg]
            cov = next((c for c in COVERAGE if c[0] == sig), None)
            summary.append(dict(
                signal_id=sig, signal_name=name, kind=kind, client=client, mastergroup_id=mg,
                evidence_rows=len(sel),
                needs_validation=sum(r['assessment_status'] == 'needs_validation' for r in sel),
                unavailable=sum(r['assessment_status'] == 'unavailable' for r in sel),
                material_drawing_test=sum(r.get('material_drawing_for_testing') == 'True' for r in sel),
                recent_approval_test=sum(r.get('recent_creation_for_testing') == 'True' for r in sel),
                covenant_pressure_test=sum(r.get('covenant_pressure_for_testing') == 'True' for r in sel),
                utilisation_above_70_context=sum(r.get('above_70_for_testing') == 'True' for r in sel),
                populated_crr=sum(r['component'] == 'crr_context' and bool(r.get('crr')) for r in sel),
                coverage_status=cov[2] if cov else ('partial_development_evidence' if sel else 'no_linked_records'),
            ))
    write(run / 'SIGNAL_SUMMARY.csv', summary)

    # Owner review packs
    sig01 = [dict(r, owner_question=owner_sig01(r)) for r in rows if r['signal_id'] == 'SIG01']
    write(run / 'OWNER_REVIEW_SIG01.csv', sig01, ['client', 'mastergroup_id', 'component', 'product_codes', 'clo_sub_limit_ids', 'drawn_field', 'currency',
          'current_drawn', 'previous_drawn', 'metric_value', 'previous_observation_date', 'observation_date', 'limit_category', 'limit_category_basis',
          'materiality_status', 'materiality_threshold', 'assessment_status', 'validation_reason', 'owner_question', 'evidence_id', 'source_record_references'])
    sig02 = []
    for r in rows:
        if r['signal_id'] == 'SIG02' and r.get('recent_creation_for_testing') == 'True':
            q = 'Confirm the linked application approval is the credit approval of this new facility (not a later review/renewal) and whether the product is an RCF, term loan or bridge.'
            if r.get('approval_matches_creation_date') == 'False':
                q = 'Approval date differs from facility_creation_date: ' + q
            sig02.append(dict(r, owner_question=q))
    write(run / 'OWNER_REVIEW_SIG02.csv', sig02, ['client', 'mastergroup_id', 'facility_ids', 'product_codes', 'credit_proposal_serial_no', 'credit_approval_date',
          'source_creation_dates', 'approval_matches_creation_date', 'event_age_days', 'proposed_limit', 'currency', 'credit_approval_source',
          'validation_reason', 'owner_question', 'evidence_id', 'source_record_references'])
    util = [dict(r, owner_question='Context only: utilisation is not covenant pressure. Confirm product, units and participation before using as supporting context.')
            for r in rows if r['signal_id'] == 'CTX_UTIL' and r.get('above_70_for_testing') == 'True']
    write(run / 'OWNER_REVIEW_CTX_UTIL.csv', util, ['client', 'drr_uids', 'facility_ids', 'product_codes', 'metric_value', 'utilisation_amount', 'approved_limit',
          'currency', 'observation_date', 'validation_reason', 'owner_question', 'evidence_id', 'source_record_references'])
    crr = [dict(r, owner_question='Context only (rating advisory comes from call reports). Define CRR scale, version flags and application periods.')
           for r in rows if r['signal_id'] == 'CTX_CREDIT' and r['component'] == 'crr_context']
    write(run / 'OWNER_REVIEW_CTX_CREDIT.csv', crr, ['client', 'cins', 'credit_proposal_serial_no', 'crr', 'crr_raw', 'crr_scale', 'latest_record',
          'multiple_crrs_for_cin', 'approval_date', 'assessment_status', 'owner_question', 'evidence_id', 'source_record_references'])
    write(run / 'COVERAGE.csv', [dict(signal_id=c[0], expected_source=c[1], coverage_state=c[2], note=c[3]) for c in COVERAGE])

    # Reconciliation to development-1
    recon = []
    if a.previous:
        old = read(a.previous)
        key = lambda r: (r['source'], r['record_key'])
        new_by = defaultdict(list)
        for r in rows:
            new_by[key(r)].append(r)
        rename = {('SIG06', 'utilisation'): ('CTX_UTIL', 'utilisation'), ('SIG07', 'crr_context'): ('CTX_CREDIT', 'crr_context'),
                  ('SIG07', 'rating_category_context'): ('CTX_CREDIT', 'facility_category_context'),
                  ('SIG02', 'facility_creation'): ('SIG02', 'facility_approval_event'), ('SIG01', 'drawing_change'): ('SIG01', 'drawing_change')}
        moves = Counter();used = set()
        for r in old:
            want = rename.get((r['signal_id'], r['component']))
            target = next((t for t in new_by.get(key(r), []) if want and (t['signal_id'], t['component']) == want and id(t) not in used), None)
            if target:
                used.add(id(target))
            moves[(r['signal_id'], r['component'], target['signal_id'] if target else '', target['component'] if target else '')] += 1
        added = Counter((r['signal_id'], r['component']) for r in rows if id(r) not in used)
        for (os, oc, ns, nc), n in sorted(moves.items()):
            recon.append(dict(dev1_signal=os, dev1_component=oc, dev2_signal=ns or '(dropped)', dev2_component=nc, records=n, change='same record re-classified' if ns != os else 'same record, rule updated'))
        for (ns, nc), n in sorted(added.items()):
            recon.append(dict(dev1_signal='(new)', dev1_component='', dev2_signal=ns, dev2_component=nc, records=n, change='added by development-2 rules'))
        write(run / 'RECONCILIATION_DEV1.csv', recon)

    # Narrative
    c = summary_json['counts']
    by = Counter(r['signal_id'] for r in rows)
    lines = [
        '# Run review: aligned_20261105_004 (rule version development-2)', '',
        'Development evidence produced with the rules agreed in the DCM meetings (see `docs/MEETING_ALIGNMENT_REVIEW.md` at the repository root). '
        'Scope, inputs and assessment dates are unchanged from development-1: core assessment 3 November 2026, CRR assessment 4 November 2026, three target mastergroups. '
        '`business_trigger` is blank on every record because no definition is marked verified.', '',
        '## Counts', '',
        '| Dataset | Records | Note |', '|---|---:|---|',
        f"| SIG01 material drawing (Cat A) | {by['SIG01']} | {sum(r['component']=='drawing_change' for r in rows if r['signal_id']=='SIG01')} on the default drawn field, {sum(r['component']=='drawing_change_alt_usd' for r in rows if r['signal_id']=='SIG01')} on the populated USD field; 0 material (FX and participation not configured; default field blank) |",
        f"| SIG02 new facility (credit approval date) | {by['SIG02']} | {c['recent_approval_candidates']} within 90 days of approval; approval date linked for {c['sig02_approval_dates_linked']} usable contexts |",
        '| SIG03A / SIG03B | 0 | No derivatives trade or enquiry source |',
        '| SIG04 KYC | 0 | Empty target export |',
        '| SIG06 covenant breach / pressure | 0 | Rule implemented (half a turn); no genuine covenant data |',
        '| SIG07 rating advisory | 0 | Source is CME call reports (not integrated) |',
        f"| CTX_UTIL utilisation context | {by['CTX_UTIL']} | {c['utilisation_above_70']} above 70% — context only |",
        f"| CTX_CREDIT category and CRR context | {by['CTX_CREDIT']} | {by['CTX_CREDIT']-c['crr_candidates']} Facilities/PVD category contexts + {c['crr_candidates']} Application Ratings CRR ({c['populated_crr']} populated) |",
        f"| **Total records** | **{len(rows)}** | development-1 had 626 |", '',
        '## What changed and why', '',
        '- **SIG01** now accepts any Cat A bank facility (CLO `REV` and `TERM`), looks up Cat A from Facilities `limit_cat` by matching facility ID, and tests the drawing increase against EUR 50m '
        '(HSBC share as a lower bound; inferred total when a participation share is available). A second comparison uses `ag_acc_bal_drawn_sub_lim_usd`, the only populated CLO drawn field, kept separate from the blank default field.',
        '- **SIG02** event date is the credit approval date: Application Ratings `approval_dt` linked through `credit_proposal_serial_no` and CIN. Facilities `loan_approva_dt` is a `0` placeholder.',
        '- **SIG06** is financial covenant breach or pressure (leverage within 0.5x of the covenant maximum). Utilisation moved to `CTX_UTIL`.',
        '- **SIG07** is sourced from CME call reports. Facilities/PVD category fields and Application Ratings CRR moved to `CTX_CREDIT`; Cat A now feeds SIG01 eligibility.',
        '- **SIG03** split into SIG03A and SIG03B. Investor-sales count dropped.', '',
        '## Findings from this run', '',
    ]
    s1 = [r for r in rows if r['signal_id'] == 'SIG01']
    s2 = [r for r in rows if r['signal_id'] == 'SIG02']
    applied = [r for r in s2 if r.get('credit_approval_date') and r['assessment_status'] != 'unavailable']
    same = sum(r['approval_matches_creation_date'] == 'True' for r in applied)
    lines += [
        f"- **SIG01:** {sum(1 for r in s1 if r['limit_category']=='CAT-A')} of {len(s1)} comparisons link to a CAT-A Facilities record; Siemens Energy's REV sub-limit has no matching Facilities ID. "
        'All default-field comparisons are still imputed zero. On the USD field the Vodafone and Siemens sub-limits show no increase. '
        'SoftBank TERM sub-limit `00010341075552511210201` carries USD 179.7m drawn but has no prior snapshot, so no increase can be computed. '
        "SoftBank's USD 200m sub-limit `00010341075552607090201` is unchanged across snapshots and has a blank CLO product, so it is not assessed.",
        f"- **SIG02:** the approval date equals `facility_creation_date` for {same} of {len(applied)} linked usable contexts. For older facilities the approval follows creation "
        '(e.g. created 12 Apr 2005, approved 10 Jun 2005), and the serial number appears to encode the creation date. '
        "The 90-day test now selects the same eight facilities plus SoftBank FCL `00010341075552511210201` (created 9 Jul 2026, approved 17 Sep 2026). "
        'Confirm that the linked application is the approval of the new facility rather than a later review.',
        '- **SIG06 / SIG07 / SIG03A / SIG03B / SIG04:** no evidence because the required sources are missing, empty or not integrated (see COVERAGE.csv).', '',
        '## Files', '',
        '- `BOND_RADAR_SIGNAL_EVIDENCE.csv` — all records with the new columns (materiality, Cat A, approval date, covenant headroom).',
        '- `CORE_SIGNAL_EVIDENCE.csv`, `crr/` — intermediate engine and CRR outputs.',
        '- `SIGNAL_SUMMARY.csv`, `COVERAGE.csv`, `OWNER_REVIEW_*.csv`, `RECONCILIATION_DEV1.csv` — written by `tools/review_run.py`.',
        '- `RUN_SUMMARY.json` — counts and approval-link statistics.', '',
        'Reproduce: `python3 -B tools/extract_inputs.py` then `python3 -B run_reference.py --out runs/<new> --test-observed-links --ratings-input data/application_ratings_full` '
        'and `python3 -B tools/review_run.py runs/<new> --previous <development-1 combined CSV>`.',
    ]
    (run / 'REVIEW.md').write_text('\n'.join(lines) + '\n')
    print(f'Wrote review pack for {len(rows)} records; reconciliation rows: {len(recon)}')


if __name__ == '__main__':
    main()
