# Development update — per-signal CSV exports, 5 November 2026

At the user's request, the existing 626-row evidence output has been packaged into one CSV for each retained signal, with summaries, original evidence, source references and losslessly preserved native raw columns. Start with [SIGNAL_SUMMARY.csv](runs/signal_extracts_20261105_002/SIGNAL_SUMMARY.csv) and [the package guide](runs/signal_extracts_20261105_002/README.md).

The completed export folder is `runs/signal_extracts_20261105_002/`. It contains SIG01, SIG02, SIG03, SIG04, SIG06 and SIG07 CSVs, shared Counterparty identity-reference data, a curated source inventory, hashes and checks. The first attempt in `_001` is retained as incomplete development history following a detected timestamp conversion; `_002` preserves every saved cell exactly.

The six signal files distinguish summaries, evidence, raw records actually used, unselected raw context, archived DE context and missing/empty-source coverage. Evidence counts remain 3/63/0/0/442/118, totalling 626. SIG03 and SIG04 contain summaries and coverage, not invented events. The 30 October DE snapshot is labelled historical context only; the additional DE extraction remains deferred.

Every original evidence field and every included raw field was checked for exact preservation, including IDs, CRR placeholders and Counterparty timestamps. Input/output hashes, source linkage and summary totals reconcile. Raw files, previous results, active engine and original shipped manifest remain unchanged. Business eligibility and identity approvals remain unverified.
