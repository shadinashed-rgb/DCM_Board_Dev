# PVD-first cohort extraction review

Assessment date: 2026-10-30

Reviewed discovery cohort; historical membership is not inferred

## Coverage by group and source

| Group | Source | State | Matched rows | Distinct matched rows | Candidates | Conflicts | Latest matched date |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| VODAFONE (MG001356) | clo | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| VODAFONE (MG001356) | counterparty | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| VODAFONE (MG001356) | covenants | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| VODAFONE (MG001356) | drr | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| VODAFONE (MG001356) | facilities | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| VODAFONE (MG001356) | kyc | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| VODAFONE (MG001356) | pvd | candidates_only | 0 | 0 | 4 | 0 | Unavailable |
| SOFTBANK (MG101624) | clo | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| SOFTBANK (MG101624) | counterparty | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| SOFTBANK (MG101624) | covenants | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| SOFTBANK (MG101624) | drr | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| SOFTBANK (MG101624) | facilities | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| SOFTBANK (MG101624) | kyc | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| SOFTBANK (MG101624) | pvd | candidates_only | 0 | 0 | 2 | 0 | Unavailable |
| Siemens Energy (MG102229) | clo | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| Siemens Energy (MG102229) | counterparty | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| Siemens Energy (MG102229) | covenants | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| Siemens Energy (MG102229) | drr | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| Siemens Energy (MG102229) | facilities | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| Siemens Energy (MG102229) | kyc | missing_file | 0 | 0 | 0 | 0 | Unavailable |
| Siemens Energy (MG102229) | pvd | candidates_only | 0 | 0 | 1 | 0 | Unavailable |

## Interpretation

- PVD exact ID/name discovery remains candidate evidence until the identifier role/group association is reviewed.
- `identifier_review.csv` contains distinct candidate IDs, original source columns, observation ranges and pending decisions. No CIN is inferred from the shape of `joi_key` or `joi_relationship_id`.
- A source row matching conflicting approved group links or disagreeing with its explicit mastergroup is quarantined. Group expansion is not transitive.
- `name_variations.csv` is a discovery/review inventory. Names do not become authoritative join keys.
- Missing, empty, unmatched, candidate-only and conflicting results have separate coverage states. Counts cannot establish source-wide completeness.
- Coverage counts preserve raw observations and separately show distinct row hashes. Financial balances are not summed here.

## Next steps

1. Review identifiers and save reviewed decisions in an approval CSV. Approve only with evidence and the correct namespace/source scope.
2. Generate source SQL from approved links and target mastergroup anchors. Export the resulting source data and rerun analysis.
3. Repeat as DRR/Counterparty/CLO reveal additional CIN/GID/relationship mappings. A new identifier is proposed for review; it is not silently approved.
4. Run the bundled signal tests on uniquely linked rows. Business triggers remain unverified by default.

## Qualifications

- PVD relationship/supergroup/key columns retain their own namespaces. No CIN/GID interpretation was inferred.
- As-of checks use exported observation/processing dates, not historical database version recovery.
- Counterparty table location, PVD grain/units and cross-source facility equivalence still require verification.
