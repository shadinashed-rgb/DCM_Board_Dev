# DCM_Board_Dev

Development workspace for the **DCM Bond Radar** internal-signal dashboard (AI DCM / Use Case 6 – Market Signals).

The signals follow the **DCM meeting decisions** (rule version `development-2`). The comparison of meeting requirements against the development, and what changed, is in [`docs/MEETING_ALIGNMENT_REVIEW.md`](docs/MEETING_ALIGNMENT_REVIEW.md).

## Branch `feature/portfolio-signal-extraction` — signals for all clients

The development so far tested the extraction on three clients (Vodafone, Siemens Energy, SoftBank). This branch extracts the same sources for **every client** and builds the signals across the portfolio, discovering client groups from the data:

| Step | Start here |
|---|---|
| 1. Extract all clients from all sources (profile → parts → checklist) | [`docs/PORTFOLIO_EXTRACTION_GUIDE.md`](docs/PORTFOLIO_EXTRACTION_GUIDE.md) and the SQL pack `development/pvd_client_cohort_lab/sql_templates/portfolio_20261106/` |
| 2. Build every signal for every client (`run_portfolio.py`) and review the outputs | [`docs/PORTFOLIO_SIGNAL_BUILD_GUIDE.md`](docs/PORTFOLIO_SIGNAL_BUILD_GUIDE.md) |
| What changed and how it was verified | `development/DEVELOPMENT_UPDATE_PORTFOLIO_20261106.md` |

Try it without real data: `cd development && python3 -B pvd_client_cohort_lab/portfolio_demo.py --out data/portfolio_demo && python3 -B run_portfolio.py --input data/portfolio_demo --as-of 2026-11-06 --out runs/portfolio_demo_001`

## Contents

| Path | What it is |
|---|---|
| `manager_meeting_20261106/` | Manager meeting pack: plan, one-pager, requirements, definitions, results, practicality assessment, next steps, Q&A, Word/PDF briefing and attachments |
| `docs/MEETING_ALIGNMENT_REVIEW.md` | Meeting requirements vs. development: decisions, gaps, data findings and the status after the update |
| `dashboard/dcm_signals_dashboard.html` | **The dashboard.** A single self-contained HTML file (no CDN, fonts or network calls), in the LAF board's style. Open it in a browser |
| `dashboard/template.html`, `dashboard/build_dashboard.py` | Dashboard layout and the script that embeds the workbook data |
| `signal_workbooks_20261105_004/` | Current reports: `SIGNAL_OVERVIEW.xlsx`, one workbook per signal/context, `SIGNAL_DEFINITIONS.md`, `FINDINGS_AND_LIMITATIONS.md` |
| `development/` | Active workspace: engine and tools (`pvd_client_cohort_lab/`, `tools/`), project documents (`PROJECT_STATE.md`, `NEXT_STEPS.md`, requirements v1.1), and the latest run `runs/aligned_20261105_004/` |
| `signal_workbooks_20261105_003.zip` | Archived development-1 package (626 records, raw source sheets, raw inputs, LAF sample board). Kept unchanged as the baseline |

## Signals (development-2)

| ID | Signal | Status |
|---|---|---|
| SIG01 | Drawing over EUR 50m on any Cat A bank facility | 8 comparisons, none material yet (drawn field / FX / participation) |
| SIG02 | New RCF / term loan / bridge, dated by credit approval | 9 approved within 90 days |
| SIG03A / SIG03B | Swap roll on maturing debt / new pre-hedge enquiry | No source |
| SIG04 | KYC onboarding / signatory refresh | Empty export |
| SIG05 | CME call-report keywords | Excluded (MNPI / entitlements) |
| SIG06 | Covenant breach or pressure (within 0.5x of maximum) | Rule ready; no covenant data |
| SIG07 | Rating advisory request (call reports) | CME not integrated |
| CTX_UTIL / CTX_CREDIT | Utilisation, credit category and CRR | Context, not signals |

The "number of investor sales" signal has been dropped. All records are development evidence; no business trigger is confirmed.

## Rebuild

Requires Python 3.10+ and `openpyxl`. Raw client exports are not committed; they are restored from the archived zip.

```sh
cd development
python3 -B tools/extract_inputs.py
python3 -B -m unittest discover -s pvd_client_cohort_lab/tests -q
python3 -B -m unittest discover -s pvd_client_cohort_lab/engine/tests -q
python3 -B run_reference.py --out runs/<new> --test-observed-links --ratings-input data/application_ratings_full
python3 -B tools/review_run.py runs/<new> --previous <development-1 combined CSV>
python3 -B tools/build_package.py runs/<new> ../<package> --previous-package ../signal_workbooks_20261105_003.zip
cd .. && python3 dashboard/build_dashboard.py --src <package>
```

After `build_package.py`, recalculate the workbook formulas (open and save in Excel, or LibreOffice headless) before building the dashboard.
