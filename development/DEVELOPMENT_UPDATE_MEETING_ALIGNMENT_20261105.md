# Development update — meeting-aligned rules (development-2), 5 November 2026

At the user's request, the signal rules, documents, results and reports were updated to the decisions captured in the DCM meetings. The comparison that motivated the change is in `../docs/MEETING_ALIGNMENT_REVIEW.md`.

The scope, inputs and assessment dates are unchanged. No raw export was modified, and the development-1 package `signal_workbooks_20261105_003` is kept unchanged as the baseline.

## Rule changes

| Signal | development-1 | development-2 |
| --- | --- | --- |
| SIG01 | CLO `REV` drawn change; no threshold; blank drawn imputed zero | Any **Cat A** bank facility (`REV`, `TERM`); Cat A from Facilities `limit_cat` via the facility-ID match; **EUR 50m** materiality on the drawing (HSBC share as lower bound, inferred total with a participation share, FX only from configured rates); separate comparison on `ag_acc_bal_drawn_sub_lim_usd`; imputed comparisons never material |
| SIG02 | `facility_creation_date`; 90-day test | **Credit approval date**: Facilities `loan_approva_dt` → `facility_creation_date` (labelled candidate) → Application Ratings `approval_dt` via `credit_proposal_serial_no` + CIN (`alignment.py`); 90-day test on the approval date |
| SIG03 | One enquiry signal | **SIG03A** swap roll on maturing debt, **SIG03B** new pre-hedge enquiry (no source) |
| SIG06 | Utilisation > 70% plus covenant breach rule | **Covenant breach or pressure** (headroom ≤ 0.5 turns below a maximum-type covenant); utilisation emitted as **CTX_UTIL** context |
| SIG07 | Facilities/PVD category + Application Ratings CRR | **Call reports** (CME, not integrated); category and CRR emitted as **CTX_CREDIT** context |
| Investor sales | — | Dropped (config `dropped_signals`) |

All `definitions_verified` flags remain `false`, so `business_trigger` stays blank.

## Code

| Area | Files |
| --- | --- |
| Engine | `pvd_client_cohort_lab/engine/bond_radar.py`, `engine/config.json`, `engine/demo_data.py` |
| Run profile | `profiles/current_signals_20261105_dev2.json`, now used by `refresh.py` |
| Cohort readiness | `cohort.py` (signal map and qualifications) |
| CSV export | `export_signals.py` (new columns) |
| CRR adapter | `sig07_crr.py` (CRR rows become `CTX_CREDIT`) |
| Approval-date step | new `alignment.py`, called from `run_reference.py` |
| Tests | new `engine/tests/test_meeting_rules.py` (13 tests) and `tests/test_alignment.py` (4 tests); existing tests updated for the new signal IDs |
| Reference | `REFERENCE_EXPECTATIONS.json` now holds development-2 counts (609 core / 619 combined); development-1 counts are in `REFERENCE_EXPECTATIONS_development-1.json` |
| Tools | `tools/review_run.py` (review pack), `tools/signal_catalogue.py` and `tools/build_package.py` (reports and workbooks), `tools/extract_inputs.py` (restore raw inputs from the zip; the git copy does not hold raw data) |

**Checks:** 87 tests pass (52 package + 35 engine; previously 70), and the development-2 sample reference is verified.

## Results — `runs/aligned_20261105_004/`

631 records (626 in development-1). All 626 earlier records map forward and 5 SIG01 comparisons are new (`RECONCILIATION_DEV1.csv`).

| Dataset | Records | Key result |
| --- | ---: | --- |
| SIG01 | 8 | 0 material (default drawn field blank; FX/participation not configured). SoftBank TERM sub-limit has USD 179.7m drawn but no prior snapshot |
| SIG02 | 63 | 9 approved within 90 days; approval = creation date for only 9 of 50 linked contexts |
| SIG03A, SIG03B, SIG04, SIG06, SIG07 | 0 | Source missing, empty or not integrated |
| CTX_UTIL | 442 | 5 above 70% (context) |
| CTX_CREDIT | 118 | 96 category contexts + 22 CRR (18 populated) |

Owner-review files: `OWNER_REVIEW_SIG01.csv`, `OWNER_REVIEW_SIG02.csv`, `OWNER_REVIEW_CTX_UTIL.csv`, `OWNER_REVIEW_CTX_CREDIT.csv`; plus `COVERAGE.csv` and `SIGNAL_SUMMARY.csv`.

## Reports and documents

- **Package:** `../signal_workbooks_20261105_004/` holds `SIGNAL_OVERVIEW.xlsx`, eight signal/context workbooks, `SIGNAL_DEFINITIONS.md`, `FINDINGS_AND_LIMITATIONS.md` and `README.md`. Summary counts are `COUNTIFS` formulas, recalculated with zero errors.
- **Updated documents:** `PROJECT_STATE.md`, `NEXT_STEPS.md`, `AGENTS.md`, `START_HERE.md`, `NEW_CHAT_PROMPT.md` and `DATA_MODEL.md`.
- **Requirements v1.1:** `Bond Radar Requirements.md` and a regenerated `.docx` using the original styles.
- **Decision banners and catalogue updates:** `Bond Radar Internal Signals.md`, `... Data Sources.md` and `... Signal Planning Notes.md`.
- **Package documentation:** `pvd_client_cohort_lab/README.md`, `CURRENT_WORKFLOW.md` and `VALIDATION.md`.
- **Dashboard:** `../dashboard/dcm_signals_dashboard.html` is rebuilt from the development-2 package.

## Not changed

- Raw inputs and the archived 003 package.
- The historical diagrams in `diagrams/`, which illustrate development-1 and may lag the new rules.
- `MANIFEST.json`, which describes the original shipped snapshot. Edits to tracked files are intentional, so `verify_workspace.py` reports them as changed.
