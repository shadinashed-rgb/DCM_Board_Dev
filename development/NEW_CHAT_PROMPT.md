Continue the existing Bond Radar project in this workspace. First read AGENTS.md, START_HERE.md, PROJECT_STATE.md, DATA_MODEL.md and NEXT_STEPS.md. Do not restart source discovery or create another replacement package.

We are developing a banker-facing dashboard locally for Vodafone MG001356, Siemens Energy MG102229 and SoftBank MG101624. The active code is pvd_client_cohort_lab. I execute SQL manually by copying it into Starburst, download CSVs to my drive and transfer them locally for Python. Give one clear sequence with exact SQL and CSV filenames.

The selected raw data are in data/ (restore with tools/extract_inputs.py if missing). The current result is runs/aligned_20261105_004/BOND_RADAR_SIGNAL_EVIDENCE.csv: 631 development records under rule version development-2, which encodes the DCM meeting decisions in ../docs/MEETING_ALIGNMENT_REVIEW.md. These are development evidence, not confirmed alerts. Check PROJECT_STATE for missing data and assumptions before proposing changes.

Key decisions:

- No SIG05 or PVD sector aggregate.
- SIG01 = any drawing over EUR 50m on any Cat A facility (HSBC share and inferred total).
- SIG02 is dated by the credit approval date.
- SIG03 is split into a swap roll (SIG03A) and a new pre-hedge enquiry (SIG03B).
- SIG06 = covenant breach or leverage within half a turn of the maximum; utilisation is context.
- SIG07 rating advisory comes from call reports; Facilities/PVD category and CRR are context.
- The investor-sales count is dropped.
- Missing drawn amounts become zero only for SIG01, with imputation flags.
- Counterparty is delta.prod_party_gda.counterparty_core.

Names and PVD identifier shapes never establish approved entity joins. Keep raw exports immutable and preserve source/date/grain/lineage. Follow the reference rebuild and tests before relying on changed results.

If I say this is planning or ask you not to change anything, inspect and discuss only. Otherwise make the requested changes in this workspace, preserve prior runs, and explain the outcome simply.

My next request is: [replace this sentence with what you want to do next].
