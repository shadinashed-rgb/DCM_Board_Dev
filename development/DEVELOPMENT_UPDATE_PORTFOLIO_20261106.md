# Development update — portfolio extraction and signal build, 6 November 2026

Branch: `feature/portfolio-signal-extraction`.

## Purpose

Until now the SQL and runs targeted three development clients (Vodafone, Siemens Energy, SoftBank) through hard-coded mastergroup, CIN and GID lists. The goal of Bond Radar is to extract the signals for **all clients** from all the sources used so far. This update:
- adds a full-portfolio SQL pack;
- adds a pipeline that discovers client groups from the data itself and builds every signal for every group;
- adds guides for both steps.

The development-2 signal rules (the DCM meeting decisions) are unchanged.

## What was added

| Area | Files |
|---|---|
| **SQL pack generator** | `pvd_client_cohort_lab/portfolio_sql.py`. Eight sources with no client filter. Each query projects only the needed columns, picks snapshots per publishing partition, and splits into stable hash parts with a CSV checklist. Also an optional CLO FX reference and a discovery query for missing sources |
| **Generated pack** | `pvd_client_cohort_lab/sql_templates/portfolio_20261106/`: 8 profiles, 21 extract parts, 1 reference query, 1 discovery file; `EXTRACTION_CHECKLIST.csv`, `README.md`, `pack_manifest.json` |
| **Schema reference** | `pvd_client_cohort_lab/profiles/source_columns_observed.json`: column names (no data) seen in the real exports and schemas, used to validate the pack |
| **Pipeline** | `pvd_client_cohort_lab/portfolio.py`. Steps: input check → group discovery → engine → evidence export → CRR context → SIG02 approval dates → summaries (group matrix, candidates, maturity windows, coverage, workbook, review) |
| **Runner** | `run_portfolio.py` (`--fx-from-clo`, `--business-lines`, `--extra-links`) and profile `profiles/portfolio_dev2.json` |
| **Tools** | `tools/project_to_portfolio_layout.py` (re-run older `t.*` rounds in portfolio mode); `pvd_client_cohort_lab/portfolio_demo.py` (synthetic portfolio) |
| **Engine (behaviour-preserving)** | Optional `link_basis` on identity links, so derived links are labelled rather than called "verified". Precomputed Cat A lookup and newest-snapshot map (no per-row scans). DRR `NO MSG` and other invalid mastergroups are no longer treated as groups |
| **Shared CRR rules** | `sig07_crr.crr_row` / `flag_multiple_crrs`, reused by portfolio mode. The targeted run reproduces run 004 exactly (631/631 records, 0 differences) |
| **Guides** | `../docs/PORTFOLIO_EXTRACTION_GUIDE.md`, `../docs/PORTFOLIO_SIGNAL_BUILD_GUIDE.md` |

## Key design decisions

- **CLO is projected to sub-limit-level columns.** The table is exploded by contract and account; on the real extract, projection reduces 276 rows to 69 (one per sub-limit × snapshot × borrower).
- **Snapshots are selected per partition:**
  - Facilities and covenants: per source system × country
  - CLO and DRR: per group
  - Counterparty Core: per instance (latest two)
  - PVD: per relationship
  - Application Ratings: per source/country/CARM
- **Group discovery:**
  1. Counterparty Core (latest, active) maps CIN and GID → mastergroup.
  2. Where Counterparty Core has none, the CIN → mastergroup association recorded by CLO or DRR is used, if unambiguous.
  3. Facilities relationship → CIN serves covenants.
  4. Reviewed links (`--extra-links`) can be added, e.g. for PVD.
  - Every route is labelled on the record. Ambiguous CINs and invalid groups get no group.
- **A SIG01 candidate requires both** materiality (≥ EUR 50m) and a Cat A facility.
- **Maturity windows** (DASH03) are produced as context: < 12 months and 12–24 months, counts only.

## Verification

- **Tests:** 109 pass (74 package + 35 engine; previously 87). New tests:
  - `test_portfolio_sql.py` (7): no client filters; only observed columns; parses as Trino; buckets partition the data; snapshot rules
  - `test_portfolio.py` (12): synthetic four-group portfolio covering every signal path, FX, ambiguity, invalid groups, reviewed links, missing parts and header drift
  - `test_portfolio_regression.py` (3): real data, run only when restored
- **Real-data regression.** Portfolio mode on the three-client extracts, given no client list, finds:
  - Vodafone, Siemens Energy and SoftBank with names, business line and country
  - the same SIG01 and SIG02 records for the three groups
  - the same 9 SIG02 candidates and the same 5 utilisation ratios above 70%
  - SoftBank's USD 179.7m drawing without a prior snapshot

  The only unlinked records are PVD (no ID route), DRR rows marked `NO MSG`, and 3 CRR CINs.
- **Reference.** The development-2 three-client reference still verifies (609/619).
- **Scale.** A synthetic portfolio of 20,000 groups (135,000 input rows → 125,000 records) builds in about 2 minutes on the development container.

## Not changed

Raw inputs, the three-client run `runs/aligned_20261105_004`, the dashboard, the definitions of the development-2 rules, and the archived package.

## Next steps

1. Run the profiles in Starburst, choose the parts, extract, and build. Follow the guides.
2. Review the group links (`RUN_SUMMARY.json` → `links`, `SOURCE_COVERAGE.csv`) and provide reviewed links for PVD.
3. Adapt the dashboard to the portfolio outputs. Many groups need a search/paged matrix (the LAF board pattern) rather than the three-client radar.
4. Pursue the data requests: LoanIQ drawn and participation, FX, derivatives, covenants, CME.
