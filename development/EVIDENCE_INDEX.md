# Evidence and discovery history

Use PROJECT_STATE.md for the consolidated latest position. These preserved reviews explain why decisions were made; earlier observations can be superseded by later returns.

| Review | What it establishes | Limit |
| --- | --- | --- |
| analysis/internal_signal_samples/Findings.md | Initial source schemas, sample availability and candidate signal attributes | Early samples, not final field/grain approval |
| analysis/pvd_cohort_extracts_20261102/Findings.md | PVD-first discovery, native ID evidence, missing/empty/error states | Candidate identity associations, not production/historical approvals |
| analysis/pvd_facilities_review_20261103/README.md | Facilities/PVD identifiers, CAT/rating context, earlier Siemens DE observations | Current partition coverage and business meanings still require checks |
| analysis/source_refresh_review_20261103/Findings.md | Snapshot reduction, zero-imputation decision, source/code refresh | Precedes the latest DCM_Run_003 and Application Ratings returns |
| analysis/dcm_run_003_review_20261103/Findings.md | Latest core raw quality, source grain, 5 high ratios, 8 creation candidates, bad covenant export | Development definitions and partial source coverage |
| analysis/dcm_run_003_review_20261103/local_test/ | Core selected inputs, identity decisions, coverage, SQLite observations and source-row lineage | Preserved manifests/DBs can contain original paths |
| analysis/sig07_application_ratings_review_20261104/Findings.md | Actual 227-column schema and client sample/profile extraction plan | Metadata-stage findings; later raw returns take precedence |
| analysis/sig07_application_ratings_data_review_20261104/Findings.md | 207 raw rows, CRR states, missingness and alternate historical Siemens agency values | Full 722-row export is not locally present |
| analysis/sig07_crr_addition_20261104/README.md | Latest CRR-only addition and 614-row result | 10 candidate applications; no validated advisory trigger |

All top-level files of these review folders and their targeted next_sql/next_checks/next_queries are retained. The current core local_test is retained in full. Earlier bulky intermediate databases/runs are omitted where raw evidence/current replacements are retained; historical standalone review scripts are reference material and may need their omitted intermediate inputs.

Additional original evidence is in the meeting TXT, original XLSX, root requirements/planning MD files, source schema/DDL results under sql/, and sql_sample_extract/. The DOCX is an older background version. The legacy Counterparty handover zip demonstrates enrichment only. reference/legacy/local_signal_lab is an older prototype. Existing diagrams are illustrative; neither diagrams nor legacy code override the current CRR-only and source-quality decisions.
