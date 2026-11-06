# Local development validation

## Portfolio mode: 6 November 2026

**109 tests pass:** 74 package and 35 engine.

New tests:
- `tests/test_portfolio_sql.py` (7): no client filters; only observed columns; parses as Trino; buckets partition the data; partitioned snapshots
- `tests/test_portfolio.py` (12): synthetic four-group portfolio covering SIG01 Cat A material, FX, not-Cat-A, SIG02 approval date, SIG06 pressure via the relationship route, KYC, CRR, maturity windows, ambiguous CIN, `NO MSG`, reviewed PVD link, missing part, header drift
- `tests/test_portfolio_regression.py` (3): real three-client data in portfolio mode reproduces the targeted SIG01/SIG02 results and the 9 SIG02 candidates. Runs when the inputs are restored

The engine changes (link basis, precomputed lookups, invalid DRR groups) keep the development-2 reference (609/619) and run 004 identical (631/631).


## Meeting-aligned rules: 5 November 2026 (development-2)

**87 tests passed:** 52 package tests and 35 engine tests, up from 70.

New tests:

- `engine/tests/test_meeting_rules.py` covers:
  - Cat A eligibility (linked, not Cat A, unlinked)
  - TERM products
  - the EUR threshold with configured FX only
  - HSBC-share lower bound, inferred total and sole lender
  - imputed zero never assessed as material
  - the separate USD drawn field
  - the SIG02 approval-date preference
  - covenant pressure at 2.6x vs 2.4x against a 3.0x maximum
  - utilisation and category emitted as context
  - real defaults producing no triggers
- `tests/test_alignment.py` covers Application Ratings approval-date linking (serial + CIN, conflicts, recency on the approval date).

Existing tests were updated for the new signal IDs and readiness counts (9 entries per group).

The reference rebuild verifies the development-2 sample counts (609 core / 619 combined). The full run `runs/aligned_20261105_004` reconciles all 626 development-1 records forward, plus 5 new SIG01 comparisons (631).


## Follow-up validation: 2 November 2026

**44 tests passed:** 26 cohort/import/query-generation tests and the 18 bundled signal-engine tests. The added tests cover manual export classification, query-error versus data detection, header-only outputs, row-order-independent duplicate export detection, an array-valued KYC name, explicit PVD ID-first extraction and source-observed candidate lookup generation without changing approval files.

The live returned KYC DDL confirms `cdd_topco_legal_name array(varchar)`. The old name query incorrectly cast it to VARCHAR; local scalar CSV fixtures had not exercised that Trino datatype constraint. The corrected query uses ARRAY_JOIN, and the new test evaluates the equivalent expression on a synthetic array. This fixes the identified generator defect but still requires execution in the user's Starburst environment.

The nine newly supplied files were reviewed by content. Two CLO exports have the same 3,622-row multiset in different orders. The widened PVD export has 1,312 rows, including 850 exact target relationship-ID observations on July/August/September month-ends. The October PVD exports are header-only. The KYC payload is an error message, not source records. The importer prepared one CLO export and the nonempty PVD export, recorded the failed KYC query, and preserved every original input checksum.

The 3,350 CLO rows with explicit target mastergroups expose 10 distinct CINs and six GIDs for candidate extraction. Their local signal diagnostic produced 88 scoped facility/date observations after excluding 92 rows with no facility key. Current default drawing/utilisation assessments remain unavailable because the configured drawn numerator is missing; no currency/measure fallback or source-group reassignment was invented.

Updated recovery SQL, manual drive-transfer guidance and the new importer are included in this package. Actual input data and review databases are outside the transfer archive. Prior validation below is retained as the historical baseline.

Validated on **30 October 2026** using Python 3.12.7 and its bundled SQLite. The package targets Python 3.10+ and needs no additional Python packages.

## Automated tests

- **18 cohort tests passed**: PVD namespace preservation, name/ID candidates, identifier review and validity, missing-versus-empty coverage, leading zeros, scoped facility links, conflicts, manual bridge retention, Counterparty lookback, group-safe signal handoff and output preservation.
- **18 bundled signal-engine tests passed**: raw/derived grain, Counterparty matching, historical cutoff, duplicate amounts, conflicting measures, zero/negative/currency conditions, threshold boundaries, old events and unavailable/unverified signals.
- Total: **36 automated tests passed**.

The PVD-to-GID bridge test explicitly verifies that a reviewed PVD relationship can supply a GID to find a DRR row with no mastergroup value, then reveal its CIN. The native PVD association and cross-source role are kept as separate reviewed links; no prefix-based interpretation is used.

Generated source-filter queries were exercised against synthetic CSV tables in local SQLite after replacing only catalog-qualified table names and supplying equivalent REGEXP_REPLACE/STRPOS functions. Expected row counts were obtained for all seven sources. This checks the filters/EXISTS/date logic locally; it is not a remote Trino execution or proof of connector behaviour.

Python and shell syntax, JSON files, read-only SQL statement structure and SQLite integrity were checked. The runtime was copied into an isolated folder whose path contains spaces and executed from a different working directory. The full demonstration completed without the original project directory or earlier `local_signal_lab` being present in that copy.

## Synthetic end-to-end example

`examples/demo-run/` contains user-supplied group labels/IDs and otherwise made-up source data. Its review decisions are fixture-specific and must not be used for real extracts.

| Stage/output | Verified result |
| --- | --- |
| Initial PVD discovery | PVD IDs/names remain candidates; all three groups and missing source rows remain visible. |
| Bridge discovery | Direct source mastergroup records propose CINs/GIDs; no unreviewed identifier is silently promoted. |
| Entity review | Approved CIN/GID links unlock Facilities and KYC. |
| Relationship review | Explicit fixture-verified Facilities/Covenants relationship bridges unlock covenant records. |
| Final source coverage | 21 rows: all three groups × seven sources, with linked fixture data in every cell. |
| Signal test | 29 evidence/context records; all six signals represented in the 18-row group summary. |
| Business trigger decisions | Zero non-NULL decisions under the unverified default business configuration. |
| Lineage | Evidence references point to existing final-path signal-input CSVs after staging directories are moved. |

Separate tests quarantine a PVD identifier approved to two groups, preserve contradictory original source mastergroups, and leave a shared facility spanning groups unallocated. A shared PVD supergroup never automatically expands the cohort.

## Previously returned source samples

The six existing 100-row project samples were read without alteration, for **600 raw input rows**. Counterparty input was absent. No target group matched under the configured seed IDs/aliases without additional reviewed links: the coverage output correctly contained 18 `no_matches_in_supplied_export` cells and three `missing_file` cells for Counterparty.

Those independently limited samples cannot establish whether the three clients exist in the full sources. Actual target coverage requires running the new PVD/source extraction queries through your SQL access. The local result is an unmatched-sample diagnostic, not an absence-of-client conclusion. Verification outputs using existing client records were kept outside the delivered folder; the package includes synthetic data only.

## Scope and outstanding live checks

All new project files are under `pvd_client_cohort_lab/`. Existing project files, including planning documents, diagrams, raw CSVs, SQL, archives and the earlier local package, were verified by SHA-256 and remained unchanged.

No live SQL query was submitted. Confirm source schemas/types, available partitions/history, exact Counterparty catalog location, PVD identifier semantics, cross-source namespace/country scope, lifecycle/effective dates, amount/currency definitions and qualifying events in your environment. SQL generation, a successful local run and matched fixture records do not establish source-wide completeness or production alert readiness.


## 3 November 2026 current-extraction validation

The refresh adds source snapshot reduction, Facilities effective-period selection,
CLO comparison retention, SIG01-only missing-to-zero auditing, Delta Counterparty
queries, and retention of contradictory mapping references. DRR UID consolidation
keeps borrower lineage and withholds non-association conflicts; rounded facility
IDs are not promoted to cross-source keys. SIG07 limit_cat remains candidate context.

The local data and generated-SQL checks are recorded in
`../analysis/source_refresh_review_20261103/Findings.md`. All original CSV hashes
remained unchanged. SQL was checked through a local SQLite compatibility adapter;
no live Starburst execution, connector permissions or live Counterparty schema
was verified. Follow CURRENT_WORKFLOW.md for the manual extraction round.

Current regression result: **57 tests passed** (35 package and 22 engine).


## SIG07 Application Ratings addition, 4 November 2026

**63 tests passed:** 41 package/query/import/refresh tests plus 22 signal-engine tests.
Six new tests execute the metadata generator and returned client queries locally
using SQLite adapters for Trino ARRAY_AGG/ARRAY_JOIN/CONCAT/CHR/REGEXP_LIKE.
They cover all three clients, S&P/CRR sample quotas, date boundaries, wide ratings,
missing metadata/keys/dates, unsupported array identifiers and escaped literals.
The delivered SQL with all 365 lookup candidates was also executed on synthetic
metadata/data. No live application_ratings schema or source query was executed.
Current seven-source refresh behaviour and original DCM_Run_003 CSVs are preserved.


## CRR-only Application Ratings addition, 4 November 2026

**70 tests passed:** 48 package tests plus 22 signal-engine tests. Seven new
tests cover CRR-only field contributions, raw/base preservation, missing values
without zero/fallback, source snapshot selection before eligibility, competing
application CRRs, full-file preference, unresolved CIN mappings, exact-duplicate
removal and replacement of an earlier Application Ratings contribution on rerun.
The three 30-column CRR projections were also executed read-only against the
provided local samples. The real addition produced ten candidate application
records (nine populated CRRs and one unavailable) and 614 consolidated rows;
all original 604 evidence items were preserved. Source CSVs remain unchanged.
