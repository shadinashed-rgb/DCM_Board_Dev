# Manual Starburst → drive exports → local Python

**For the next round, follow [CURRENT_WORKFLOW.md](CURRENT_WORKFLOW.md).**
It uses current snapshots and one local processing command. The instructions
below describe earlier recovery rounds.

The two environments are separate. You copy SQL text into Starburst, run it manually and save results to the drive accessible from that environment. You then transfer those files into a local folder. Python reads the transferred files; it never connects to Starburst or triggers an export.

## Recovery SQL for the returned files, 2 November 2026

The current recovery pack is `sql_templates/recovery_20261102/`:

| File | Run in Starburst | Expected use |
| --- | --- | --- |
| `pvd/00_pvd_partitions.sql` | One SELECT | Optional Hive partition metadata; inspect available ETL months/portfolios. Support depends on connector/access. |
| `pvd/04_pvd_mastergroup_ids.sql` | One SELECT | ID-first extraction for MG001356, MG102229 and MG101624 in `joi_relationship_id`; no name search. |
| `pvd/06_pvd_id_date_coverage.sql` | One SELECT | Counts by exact ID and business date. |
| `pvd/05_pvd_name_candidates.sql` | One SELECT | Additional name/supergroup candidates kept separate from exact target IDs. |
| `sources/kyc/04_name_candidates.sql` | One SELECT | Corrected array-aware KYC name lookup. `cdd_topco_legal_name` uses ARRAY_JOIN, not CAST(array AS VARCHAR). |
| `sources/clo/02_extract.sql` | One SELECT | Exact supplied mastergroup anchors. |
| `sources/drr/02_extract.sql` | One SELECT | Exact supplied mastergroup anchors. |

Run the schema/DDL statements separately before using a source. The recovery profile uses PVD business dates from 1 July through 30 October 2026, because the wider returned file contained July/August/September rows but the October-only exports were empty. Other source windows remain 1–30 October. This is an evidence-based development window, not a claim of current completeness. Review partitions/dates before changing it.

The old combined PVD discovery query already searched IDs and names. The `04_name_candidates.sql` files were deliberately name-only supplements; they were not the ID extracts. The new filenames make the two purposes explicit. Broader names can return different mastergroups, including supergroup members; they are not silently assigned to one of the three targets.

## Transfer and import the results

1. Save results with headers, all rows and correct CSV quoting on the drive accessible from Starburst. Keep error messages/schema/date-profile exports distinguishable. Record the submitted SQL and execution/export outcome.
2. Transfer the folder to your local machine. The filenames may remain Starburst's query-result names; no manual source renaming is required for recognised schemas.
3. Open a terminal in `pvd_client_cohort_lab` and run:

```sh
python3 cohort.py import-exports \
  --input ../sql_sample_extract \
  --out imported/round-001

python3 cohort.py analyse \
  --input imported/round-001 \
  --as-of 2026-11-02 \
  --out runs/round-001
```

Use the path to your transferred folder instead of `../sql_sample_extract` when needed. New output names are required for each run.

The importer identifies datasets by header signatures. It preserves source values, writes canonical per-source chunks and a manifest with the original filenames/checksums. Schemas, profiles and error exports are recorded but are not loaded as source rows. A file containing the KYC error is not treated as KYC data. Identical whole exports are loaded once even if their row order differs; partial overlaps between different exports remain raw evidence for later deduplication.

Open `imported/round-001/IMPORT_REPORT.md`, `runs/round-001/REPORT.md` and `coverage_summary.csv`. `extraction_failed` means a query-error payload was supplied; `missing_file`, `empty_export` and `no_matches_in_supplied_export` remain different states.

## Generate the next ID-based lookup queries locally

The returned CLO rows with explicit target mastergroups expose candidate CINs/GIDs. To write source lookups using such observed IDs without automatically approving cross-source mappings:

```sh
python3 cohort.py candidate-sql \
  --cohort runs/round-001 \
  --start 2026-10-01 --end 2026-10-30 \
  --config profiles/returned_extracts_20261102.json \
  --out generated_sql/round-002
```

This command writes files only. Copy the generated `kyc/02_extract.sql`, `facilities/02_extract.sql`, `drr/02_extract.sql` and `clo/02_extract.sql` into Starburst individually when the plan says `query_generated`. Export and transfer their results, then import/analyse another round. These are source-observed candidate identifier lookups; cross-source identity/date/country meaning still needs review before final joins. No approval CSV is created or changed by `candidate-sql`.

For verified links, continue to use `source-sql --approved ...` as described in README.md. Counterparty remains blocked until its catalog/schema is confirmed; Covenants needs a verified relationship/facility bridge. KYC's `mg_parent_grid`, `groupguci` and `groupguci_sub` have not been established as the supplied mastergroup namespace, so they are not guessed into an MG-ID join.

## What to review after extraction

- Exact group IDs and source-observed CIN/GID values first; names provide additional candidate context.
- Source dates and ETL/partition dates separately. Empty recent windows do not prove absent clients.
- Duplicate exports before combining records or evaluating amounts.
- Coverage for each group/source, including failures and unresolved identifiers.
- Signal measure definitions, currency and participation before calculating triggers. The supplied CLO's default drawn field was missing in the reviewed rows; an alternative USD field must not be mixed with a local-currency limit automatically.

Local SQL expression tests use SQLite equivalents and synthetic arrays; the corrected KYC query still needs execution in Starburst. Function reference: [Trino array_join](https://trino.io/docs/current/functions/array.html#array_join). No source data is uploaded or sent by these commands.
