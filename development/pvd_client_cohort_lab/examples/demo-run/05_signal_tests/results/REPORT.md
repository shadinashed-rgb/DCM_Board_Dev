# Local Bond Radar test results

Assessment date: 2026-10-30

Development/test outputs. Business definitions and mappings remain subject to the recorded qualifications.

## Run outputs

- clo_enriched: 5
- observations: 20
- signal_evidence: 29
- signal_assessments: 18

## Quality checks

| Source | Check | Level | Count | Interpretation |
| --- | --- | --- | --- | --- |
| clo | exact_duplicate_rows | WARN | 1 | Raw records retained; derived observations deduplicate repeated values. |
| clo | input_loaded | INFO | 5 | 1 file(s); 17 columns; raw values preserved as text |
| counterparty | input_loaded | INFO | 3 | 1 file(s); 5 columns; raw values preserved as text |
| facilities | input_loaded | INFO | 3 | 1 file(s); 12 columns; raw values preserved as text |
| kyc | input_loaded | INFO | 3 | 1 file(s); 9 columns; raw values preserved as text |
| covenants | input_loaded | INFO | 3 | 1 file(s); 14 columns; raw values preserved as text |
| drr | input_loaded | INFO | 3 | 1 file(s); 13 columns; raw values preserved as text |
| pvd | exact_duplicate_rows | WARN | 1 | Raw records retained; derived observations deduplicate repeated values. |
| pvd | input_loaded | INFO | 5 | 1 file(s); 15 columns; raw values preserved as text |
| counterparty | prior_settings_unverified | WARN | 1 | Lifecycle, lookback and sentinel settings are previous configuration to validate, not approved Bond Radar defaults. |
| counterparty | catalog_unconfirmed | WARN | 1 | hive.prod_party_gda.counterparty_core is a proposed location; local CSV processing does not verify it. |
| identity | cin_namespace_unverified | WARN | 1 | CIN joins are provisional. Verify country/source scope or supply explicit source-scoped identity links. |
| counterparty | enrichment_matched_unique | INFO | 1 | Counts are raw borrower-association observations, not distinct clients or recovered facilities. |
| counterparty | enrichment_original_preserved | INFO | 4 | Counts are raw borrower-association observations, not distinct clients or recovered facilities. |

## How to interpret the results

- `signal_evidence`: metrics and context, with source-row references and qualifications. `triggered` stays blank until applicable definitions/settings are verified.
- `client_signal_summary`: all six signals per observed client identity. No-evidence means unavailable. An assessed no-trigger result only describes supplied records.
- `clo_enriched`: one record per accepted raw CLO association, including both identifier routes and mapping dates.
- `group_signal_summary`: counts of evidence only; no monetary totals across sources. Unverified and ambiguous mappings need review.
- `stale`: observation lag exceeds the configurable development freshness setting; inspect event dates separately.
- `raw_*`: original CSV values as text. `__id` connects derived lineage to source file and CSV line.

## Limits

No live SQL was executed by the local process. Daily coverage, approved production definitions, financial units, facility equivalence and full client mappings are not established by a successful run.
