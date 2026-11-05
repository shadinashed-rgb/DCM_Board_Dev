# Development update — full CRR exports, 4 November 2026

This update supplements the immutable shipped handover. Its statements that full Application Ratings exports were absent describe the earlier reference snapshot; the three full files are now present in `data/application_ratings_full/`. `MANIFEST.json` and the historical sample reference expectations remain unchanged.

The new run is `runs/crr_full_001/`. See [the reviewed run](runs/crr_full_001/REVIEW.md) and [machine-readable reconciliation](runs/crr_full_001/DATA_REVIEW.json).

Use `runs/crr_full_001/DCM_Run_003_All_Signal_Evidence_With_CRR.csv` as the latest combined development output for the supplied full CRR scope: **626 evidence rows**, comprising the unchanged 604-row core plus 22 CRR contexts (18 populated, four unavailable). The original `results/ALL_SIGNALS_WITH_CRR.csv` remains the 614-row sample baseline.

Raw export counts match the previous profiles: Vodafone 477, Siemens Energy 238, SoftBank 7. Snapshot is 3 November 2026; CRR assessment is 4 November 2026. All ten sample CRR contexts remain present, with 12 additional contexts. Nine candidates are labelled HISTORICAL despite open periods; competing Siemens CRRs remain separate. No business triggers, identity approvals or group ratings are established.

All 70 tests and a fresh reference rebuild (`runs/reference_002/`) passed. Raw exports, shipped code, archived results and original manifest remain unchanged. Reproduction, checks, extraction metadata gaps and outstanding targeted validations are documented in the run review.
