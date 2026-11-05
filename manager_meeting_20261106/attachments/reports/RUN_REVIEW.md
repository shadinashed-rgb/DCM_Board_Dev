# Run review: aligned_20261105_004 (rule version development-2)

Development evidence produced with the rules agreed in the DCM meetings (see `docs/MEETING_ALIGNMENT_REVIEW.md` at the repository root). Scope, inputs and assessment dates are unchanged from development-1: core assessment 3 November 2026, CRR assessment 4 November 2026, three target mastergroups. `business_trigger` is blank on every record because no definition is marked verified.

## Counts

| Dataset | Records | Note |
|---|---:|---|
| SIG01 material drawing (Cat A) | 8 | 4 on the default drawn field, 4 on the populated USD field; 0 material (FX and participation not configured; default field blank) |
| SIG02 new facility (credit approval date) | 63 | 9 within 90 days of approval; approval date linked for 50 usable contexts |
| SIG03A / SIG03B | 0 | No derivatives trade or enquiry source |
| SIG04 KYC | 0 | Empty target export |
| SIG06 covenant breach / pressure | 0 | Rule implemented (half a turn); no genuine covenant data |
| SIG07 rating advisory | 0 | Source is CME call reports (not integrated) |
| CTX_UTIL utilisation context | 442 | 5 above 70% — context only |
| CTX_CREDIT category and CRR context | 118 | 96 Facilities/PVD category contexts + 22 Application Ratings CRR (18 populated) |
| **Total records** | **631** | development-1 had 626 |

## What changed and why

- **SIG01** now accepts any Cat A bank facility (CLO `REV` and `TERM`), looks up Cat A from Facilities `limit_cat` by matching facility ID, and tests the drawing increase against EUR 50m (HSBC share as a lower bound; inferred total when a participation share is available). A second comparison uses `ag_acc_bal_drawn_sub_lim_usd`, the only populated CLO drawn field, kept separate from the blank default field.
- **SIG02** event date is the credit approval date: Application Ratings `approval_dt` linked through `credit_proposal_serial_no` and CIN. Facilities `loan_approva_dt` is a `0` placeholder.
- **SIG06** is financial covenant breach or pressure (leverage within 0.5x of the covenant maximum). Utilisation moved to `CTX_UTIL`.
- **SIG07** is sourced from CME call reports. Facilities/PVD category fields and Application Ratings CRR moved to `CTX_CREDIT`; Cat A now feeds SIG01 eligibility.
- **SIG03** split into SIG03A and SIG03B. Investor-sales count dropped.

## Findings from this run

- **SIG01:** 6 of 8 comparisons link to a CAT-A Facilities record; Siemens Energy's REV sub-limit has no matching Facilities ID. All default-field comparisons are still imputed zero. On the USD field the Vodafone and Siemens sub-limits show no increase. SoftBank TERM sub-limit `00010341075552511210201` carries USD 179.7m drawn but has no prior snapshot, so no increase can be computed. SoftBank's USD 200m sub-limit `00010341075552607090201` is unchanged across snapshots and has a blank CLO product, so it is not assessed.
- **SIG02:** the approval date equals `facility_creation_date` for 9 of 50 linked usable contexts. For older facilities the approval follows creation (e.g. created 12 Apr 2005, approved 10 Jun 2005), and the serial number appears to encode the creation date. The 90-day test now selects the same eight facilities plus SoftBank FCL `00010341075552511210201` (created 9 Jul 2026, approved 17 Sep 2026). Confirm that the linked application is the approval of the new facility rather than a later review.
- **SIG06 / SIG07 / SIG03A / SIG03B / SIG04:** no evidence because the required sources are missing, empty or not integrated (see COVERAGE.csv).

## Files

- `BOND_RADAR_SIGNAL_EVIDENCE.csv` — all records with the new columns (materiality, Cat A, approval date, covenant headroom).
- `CORE_SIGNAL_EVIDENCE.csv`, `crr/` — intermediate engine and CRR outputs.
- `SIGNAL_SUMMARY.csv`, `COVERAGE.csv`, `OWNER_REVIEW_*.csv`, `RECONCILIATION_DEV1.csv` — written by `tools/review_run.py`.
- `RUN_SUMMARY.json` — counts and approval-link statistics.

Reproduce: `python3 -B tools/extract_inputs.py` then `python3 -B run_reference.py --out runs/<new> --test-observed-links --ratings-input data/application_ratings_full` and `python3 -B tools/review_run.py runs/<new> --previous <development-1 combined CSV>`.
