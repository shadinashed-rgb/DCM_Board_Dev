> **Update, 5 November 2026 (development-2).**
> - The rules now follow the DCM meeting decisions: see `../docs/MEETING_ALIGNMENT_REVIEW.md` and `DEVELOPMENT_UPDATE_MEETING_ALIGNMENT_20261105.md`.
> - The current result is `runs/aligned_20261105_004/BOND_RADAR_SIGNAL_EVIDENCE.csv`: 631 records, with its review in `REVIEW.md` beside it.
> - In the git repository, restore raw inputs first with `python3 -B tools/extract_inputs.py`.
> - The verified sample reference is now 609 core / 619 combined; development-1's 604 / 614 is kept in `REFERENCE_EXPECTATIONS_development-1.json`.
> - Sections below describe the 4 November handover and remain valid for workflow; their counts are development-1.

# Bond Radar development handover — 4 November 2026

This folder is the new development workspace. It includes the working Python/SQL, selected original CSV exports, current results, requirements and the evidence behind earlier decisions. It runs locally without the old project directory. Real client data is included.

## 1. Open this folder and start the new chat

Move/copy the **whole folder**, open it as the IDE project, then paste [NEW_CHAT_PROMPT.md](NEW_CHAT_PROMPT.md) into the new chat. Read [PROJECT_STATE.md](PROJECT_STATE.md) for the consolidated knowledge and [AGENTS.md](AGENTS.md) for working conventions. There is no need to rerun Starburst just to resume development.

Authority order: explicit new user instructions; this handover's dated decisions and PROJECT_STATE; the newest dated analysis; current requirements/planning documents; older discovery reports. Historical files may describe assumptions that were later corrected. This is a curated handover, not a verbatim transcript of the chat.

## 2. Inspect the data and current results

| What | Where |
| --- | --- |
| Current combined evidence, 614 rows | [results/ALL_SIGNALS_WITH_CRR.csv](results/ALL_SIGNALS_WITH_CRR.csv) |
| Application Ratings CRR contribution, 10 rows | [results/SIG07_CRR.csv](results/SIG07_CRR.csv) |
| Six safe latest source exports | `data/current_exports/` |
| Application Ratings samples and profiles | `data/application_ratings/` |
| Earlier Siemens DE Facilities export | `data/history/facilities_siemens_de_20261030.csv` |
| Data inventory, row counts, hashes, origin and intended use | [DATA_CATALOG.csv](DATA_CATALOG.csv) |
| Source contracts, join/grain rules and proposed model | [DATA_MODEL.md](DATA_MODEL.md) |
| Known missing, empty and misleading sources | [data/README.md](data/README.md) |
| Historical reasoning, SQL checks and current lineage databases | `analysis/` |

614 evidence items are **not 614 confirmed banker alerts**. SIG03 and SIG04 have no assessable event records in this consolidated CSV. Missing sources remain visible in the coverage reports rather than being fabricated as zero activity.

## 3. Verify and rebuild locally

From a terminal opened **inside this folder**:

```sh
python3 --version
python3 -B verify_workspace.py
python3 -B run_reference.py --out runs/reference_001 --test-observed-links --verify-reference
```

Python 3.10+ and its standard library are sufficient. No pip install, database server, credentials or network connection is required. On Windows, use `py -3` if that is the installed launcher. If `reference_001` already exists, use `runs/reference_002`; existing results are never overwritten by this runner.

`--test-observed-links` explicitly reproduces the **development-only** identity associations used in this baseline. They are not production approvals. Without that option, matching is more restrictive and the reference counts will differ. Do not pass `--verify-reference` after changing data or assessment dates.

Expected verified result: 604 core rows, 614 with CRR, 10 CRR candidates (9 populated, 1 unavailable), 5 utilisation candidates above 70%, 8 recent-creation candidates, 3 SIG01 comparisons with current drawn zero-imputation. Full expectations and source hashes are in `REFERENCE_EXPECTATIONS.json`.

Open the new run's:

- `RUN_SUMMARY.json`: reference checks and counts.
- `baseline/cohort/REPORT.md`: group/source coverage.
- `baseline/current_selection.csv`: snapshot and version reductions.
- `baseline/signals/results/exports/`: detailed candidate measures and lineage.
- `crr/DCM_Run_003_All_Signal_Evidence_With_CRR.csv`: the rebuilt combined output.

The supplied `results/` files preserve the earlier export. Rebuilt record references may contain the new local paths; those path differences are expected. The reference check compares verified inputs and control counts, not byte equality of path-bearing outputs.

## 4. Continue the next extraction when ready

Follow [NEXT_STEPS.md](NEXT_STEPS.md). SQL is executed **manually in Starburst**, downloaded to the user's drive, then moved locally for Python processing. The code does not submit SQL or handle credentials.

For the immediate CRR-only follow-up, run the three SQLs listed in NEXT_STEPS and save the exact prescribed filenames. The full 722-row Application Ratings export is **not included**: only 207 raw sample rows were available locally.

## Workspace map

- `pvd_client_cohort_lab/`: active code, source profiles, SQL templates, tests and synthetic demo. Start with this root guide rather than restarting the old demo/discovery workflow.
- `data/`: curated, byte-preserved source CSVs, schemas, history and quarantine.
- `results/`: latest inspected output aliases; regenerate into a new `runs/` subfolder.
- `sql/` and `sql_sample_extract/`: original returned extracts and source schemas retained as historical evidence. Do not ingest these entire trees as one round.
- `analysis/`: dated reviews, supporting metrics/scripts, targeted follow-up SQL and the current archived lineage databases. Earlier large intermediate databases were omitted when raw inputs and current replacements are available.
- Root requirements/planning MD files: original business context and detailed evolving notes. The DOCX and meeting TXT are background versions.
- `diagrams/`: existing interactive source/process views; they are illustrative and may lag the latest CRR-only decision.
- `reference/legacy/`: older prototype and background implementation. Do not switch development to that prototype.
- `reference/skills/hsbc-house-style/` and `hsbc-house-style.md`: portable style guidance/assets for future HTML. No global skill installation is needed for this handover.
- `validation/`: checks completed for this handover. `MANIFEST.json` verifies the shipped snapshot, while `PROVENANCE_ORIGINS.json` maps copied files back to original project paths.

Archived manifests/SQLite evidence may retain original machine paths as provenance. Only the new root runner and copied active package are the supported portable execution path. Historical review scripts may require intermediate files that were intentionally not duplicated.

For the evidence behind each discovery, use [EVIDENCE_INDEX.md](EVIDENCE_INDEX.md). [validation/CHECKS.json](validation/CHECKS.json) records tests, relocation checks, adaptations and intentionally omitted regenerable files. DATA_CATALOG row counts are CSV records, including metadata/error records where labelled; they are not source-wide business counts.
