# Bond Radar signal workbooks — development-2 (meeting-aligned)

Open **SIGNAL_OVERVIEW.xlsx** first. It summarises the catalogue: SIG01, SIG02, SIG03A, SIG03B, SIG04, SIG06 and SIG07, plus SIG05 (excluded) and the two context datasets `CTX_UTIL` and `CTX_CREDIT`. It also contains per-client counts, definitions, findings and the source inventory.

This package supersedes `signal_workbooks_20261105_003` for definitions and results. The 003 package is kept unchanged as the development-1 baseline: 626 records, with raw source sheets.

## What changed (DCM meeting decisions)

| Item | development-1 | development-2 |
|---|---|---|
| SIG01 | CLO REV drawn change, no threshold | Any **Cat A** bank facility (REV, TERM) drawing over **EUR 50m**; HSBC share and inferred total; separate USD-field comparison |
| SIG02 | `facility_creation_date`, 90-day test | **Credit approval date** (Application Ratings `approval_dt` via serial); 90-day test on approval |
| SIG03 | Single enquiry signal | **SIG03A** swap roll on maturing debt · **SIG03B** new pre-hedge enquiry |
| SIG06 | Utilisation > 70% | **Covenant breach or pressure** (leverage within 0.5x of maximum); utilisation → `CTX_UTIL` |
| SIG07 | Facilities/PVD category + CRR | **Call reports** (CME, not integrated); category + CRR → `CTX_CREDIT` |
| Investor sales | — | Dropped |

## Records

| Dataset | Records |
|---|---:|
| SIG01 — Material drawing on a Cat A bank facility | 8 |
| SIG02 — New RCF, term loan or bridge (credit approval) | 63 |
| SIG03A — Swap roll on maturing debt | 0 |
| SIG03B — New pre-hedge swap enquiry | 0 |
| SIG04 — KYC onboarding or signatory refresh | 0 |
| SIG05 — CME call report keywords | 0 |
| SIG06 — Financial covenant breach or pressure | 0 |
| SIG07 — Rating advisory request (call reports) | 0 |
| CTX_UTIL — Facility utilisation (context) | 442 |
| CTX_CREDIT — Credit category and rating (context) | 118 |
| **Total** | **631** |

## Workbooks

Each workbook (SIG01, SIG02, SIG03, SIG04, SIG06, SIG07, CTX_UTIL and CTX_CREDIT) has these sheets:

1. **Summary** — counts by client; these are `COUNTIFS` formulas over Signal data.
2. **Signal data** — the compact view.
3. **Definitions**
4. **Findings**
5. **Sources**
6. **Owner review** or **Coverage**, where applicable.
7. **Lineage** — one row per source-record link.
8. **Evidence detail** — every original field as text.

Native identifiers, CRR codes and placeholders remain text. Amounts are in native currency; nothing is FX-converted or summed across sources.

## Rebuild

From `development/`:

```sh
python3 -B tools/extract_inputs.py
python3 -B run_reference.py --out runs/<new> --test-observed-links --ratings-input data/application_ratings_full
python3 -B tools/review_run.py runs/<new> --previous <development-1 combined CSV>
python3 -B tools/build_package.py runs/<new> ../<package folder> --previous-package ../signal_workbooks_20261105_003.zip
```

Then recalculate the workbook formulas, by opening and saving in Excel or by running LibreOffice headless.
