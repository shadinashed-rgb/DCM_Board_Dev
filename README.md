# DCM_Board_Dev

Development workspace for the **DCM Bond Radar** signal dashboard.

## Contents

| Path | What it is |
|---|---|
| `signal_workbooks_20261105_003.zip` | Signal workbook package: `SIGNAL_OVERVIEW.xlsx`, one workbook per retained signal (SIG01, SIG02, SIG03, SIG04, SIG06, SIG07), consolidated definitions/findings, the development snapshot and the LAF `sample board` the dashboard style is taken from. |
| `dashboard/dcm_signals_dashboard.html` | **The dashboard.** A single self-contained HTML file (no CDN, fonts or network calls). Open it in a browser by double-clicking it. |
| `dashboard/template.html` | Page layout, styles and rendering code, following the LAF board's style guide. |
| `dashboard/build_dashboard.py` | Extracts every signal workbook into the embedded JSON payload and writes the dashboard. |

## Dashboard sections

1. **Hero and KPIs**: 626 evidence records, 13 development test candidates, 224 needing validation, 402 unavailable, 0 confirmed business triggers.
2. **Signal shape radar**: one shape per target mastergroup (Vodafone, Siemens Energy, SoftBank). It has two modes: *Development tests* (how far each test is met) and *Evidence coverage* (the share of each client's evidence that can be assessed).
3. **Client matrix**: one row per client and one coloured cell per signal. Click a row to open the client drill-down for that client's SIG06, SIG02, SIG01 and SIG07 evidence and its coverage gaps.
4. **Development tests**: strip charts of the SIG06 utilisation ratios against the >70% test and the SIG02 facility ages against the 90-day window.
5. **Signal catalogue**: SIG01–SIG07 (SIG05 is shown as excluded), with purpose, evidence counts and the split of each signal's evidence.
6. **Evidence explorer**: all 626 records with search, signal/client/status filters and pagination. Click a row to see every original evidence field and its source lineage.
7. **Owner review queue**: the 35 SIG02/SIG06/SIG07 candidates and the question each one needs answered.
8. **Definitions and findings**, **sources and freshness**, and **package verification**.

All values appear exactly as saved in the workbooks. Amounts stay in their native currency, with no FX conversion or cross-source totals. Missing or empty sources are shown in grey and are never treated as "no activity".

## Rebuilding

Requires Python 3.10+ and `openpyxl`.

```sh
python3 dashboard/build_dashboard.py --src signal_workbooks_20261105_003.zip
# or point --src at an extracted package folder, and --out elsewhere if needed
```

The build checks that each signal's extracted evidence count matches `SIGNAL_OVERVIEW.xlsx` and fails if any record has no Evidence detail.
