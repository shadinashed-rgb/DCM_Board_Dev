# Development update — validation, 5 November 2026

The user deferred the additional German Facilities extraction and requested the validation step using existing evidence. The extraction SQL remains available but is deferred; no new DE source data has been ingested and publishing/current-selection completeness remains unresolved.

Completed local validation is in [runs/validation_20261105_001/REVIEW.md](runs/validation_20261105_001/REVIEW.md), with per-candidate owner-review CSVs for SIG06, SIG02 and Application Ratings CRR. The independent validation recorded 269 passing checks. All 70 tests and the original 686-file handover integrity check passed. The previous reference run's controls were reused with input hashes verified.

The latest evidence remains `runs/crr_full_001/DCM_Run_003_All_Signal_Evidence_With_CRR.csv` (626 rows). Arithmetic, date-rule, CRR selection and lineage checks pass within the supplied scope; business eligibility, source definitions, approved identity links and triggers remain unverified. No engine, source CSV, previous result, shipped manifest or assessment date was changed.

Two FGTE candidates have raw `unconditionally_cancellable=Y` alongside `committed_flag=Y`; Siemens FCTA has raw `facility_as_parent=G`. These require source-owner definitions, not automatic inclusion/exclusion. Creation-event meanings, CRR scales and historical/open-period application semantics remain unresolved. Use the owner-review CSVs to record and resolve these questions before changing business eligibility rules.
