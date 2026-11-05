# Cohort data dictionary

## Application Ratings CRR addition, 4 November 2026

SIG07 now has an optional CRR-only Application Ratings addition via sig07_crr.py.
crr is the non-placeholder final_crr code; crr_raw retains blanks/placeholders.
crr_scale, previous_crr, proposed_crr and approved_crr remain separate source
states. These are categorical codes, not amounts or numbers to average.
The source snapshot, record period, application identity and candidate CIN mapping
are retained. Multiple CRRs per CIN are flagged rather than choosing a group rating.
Missing ratings and unknown periods/links remain unavailable; no zero imputation,
fallback rating state, change threshold or advisory business_trigger is applied.
No agency-rating fields are contributed by this adapter.

This package starts with user-supplied mastergroup anchors and PVD discovery. Table/field names in its local outputs are development contracts, not new upstream database columns.

## Identifier types

| Type | Source interpretation | Cross-source use |
| --- | --- | --- |
| MASTERGROUP_ID | User target IDs; explicit CLO/DRR/Counterparty group fields | Only configured matching fields; not automatically a PVD field. |
| PVD_RELATIONSHIP_ID | `joi_relationship_id` | PVD only until a separately reviewed namespace conversion/crosswalk exists. |
| PVD_SUPERGROUP_ID | `drr_supergroup_id` | PVD only; may cover several client groups. No automatic transitive expansion. |
| PVD_KEY | `joi_key` | PVD only. Can be composite; no CIN or GID inference. |
| CIN | Explicit CIN field or a reviewed namespace conversion | A source or `*`, only when source/country scope is verified. Leading zeros retained. |
| GID | Explicit GID field or a reviewed namespace conversion | A source or `*` under the same qualification. |
| RELATIONSHIP_ID | Source `relationship_id` | Specific target source; no generic cross-source equivalence. |
| CUSTOMER_ID | Facilities `customer_id` | Facilities-specific. |
| DRR_RELATIONSHIP_ID | DRR `app_relationship_id` | DRR-specific. |
| FACILITY_ID | Source `facility_id` | Specific target source and explicit source-system/country scope. |
| CLO_SUB_LIMIT_ID | CLO `sub_lim_id` | CLO source/mapping/booking scope. |
| CLO_RCT_FACILITY_REF | CLO `rct_facility_ref` | CLO source/mapping/booking scope. |

Source-column routes are declared in `cohort.py:IDENTIFIERS`; source name fields in `NAME_COLUMNS`. They follow the supplied schemas. The source tables/date formats are in the bundled engine's `SOURCES`. Adapt generated SQL only after live schema verification when a field/location differs. Do not add a guessed name or ID column just to force matching.

## Review CSV

| Column | Meaning |
| --- | --- |
| review_id | Stable proposal identity. New manual mappings need a unique new ID. |
| mastergroup_id | One configured target group. |
| origin_source / origin_column | Where this value was seen or the separately verified bridge originated. |
| identifier_value | Normalised text; raw original values remain in the cohort database. |
| proposed_type | Type assigned from the original source column. |
| approved_type | Type the reviewer verified for matching. A conversion requires evidence. |
| target_source | One of pvd, clo, drr, counterparty, facilities, kyc, covenants; `*` is allowed for reviewed MG/CIN/GID namespaces. |
| decision | pending / approve / reject. Only approve enters identifier matching and extraction queries. |
| evidence | Nonempty verification reference for an approved link. |
| valid_from / valid_to | Inclusive source-observation date bounds; blank means open. Not automatically legal effective dates. |
| scope_json | Source-column/value predicates, for example `{"source_system_name":"DEMO","country_code":"GB"}`. Required namespace context for facility routes. |
| first_observed / last_observed | Dates of the candidate evidence retained in the inventory. |
| observed_rows | Raw supporting rows in this run; zero for an earlier/manual inventory item retained without a current proposal. |

Pending/rejected/manual decisions survive the next review export. Rejection removes that link from approved matching but does not delete source data. If an unchanged source row is still a name candidate, its candidate association can remain visible for inspection. The code does not delete evidence to hide a rejected suggestion.

## Local SQLite tables

- `raw_rows`: all supplied source fields as JSON with source, run-local row ID, original file/CSV record number, observation date and content hash. Header case/spacing are normalised; values remain text.
- `source_status`: input files/counts/headers, missing identifier fields, invalid dates, processing dates after the assessment and missing metadata sidecars.
- `source_status.extraction_errors`: query-error payloads detected by `import-exports`. A failed export with no source rows produces coverage state `extraction_failed`, separately from missing or empty data.
- `approved_links`: seed anchors plus the explicit approved identifier links used for this run.
- `matches`: per-source-row/group association and its routes. `matched` requires a unique trusted route; `candidate` is name or unreviewed PVD ID evidence; `conflict` prevents trusted assignment.
- `coverage`: every group/source combination, including missing/empty cases.
- `signal_readiness`: all six retained signals for every group. Presence means source records exist, not that fields or business logic are sufficient.

All exact identifier matching normalises case/whitespace while preserving zeros and prefixes. Name discovery additionally normalises punctuation to spaces and uses configured alias containment; it is deliberately candidate-only. Sentinel identifier values are configurable. No name-based fuzzy score or confidence percentage is invented.

The KYC name generator uses `ARRAY_JOIN` for the verified array-valued `cdd_topco_legal_name` field. Scalar name fields retain scalar handling. An array is not cast directly to VARCHAR.

`import-exports` identifies manual downloads by contents, retaining schemas/profiles/errors in its manifest and recognising duplicate whole exports by their row-content multiset, independent of ordering. Raw exports are unchanged. A source-observed `candidate-sql` pack can use CIN/GID values from linked records to collect further data, but creates no approved identity mapping and makes no completeness claim.

## Coverage columns

| Column(s) | Unit/interpretation |
| --- | --- |
| raw_export_rows | Entire source CSV population, repeated per group for context. |
| matched_rows | Raw rows uniquely assigned to this group through its source mastergroup or approved identifier routes. |
| matched_distinct_rows | Distinct source row hashes among those matches; repeated snapshots/amounts are not automatically independent business events. |
| candidate_rows / conflict_rows | Raw observations requiring review; not approved financial evidence. |
| distinct_cins / distinct_gids / distinct_relationship_ids | Identifiers actually present in matched source records. They may still be pending for cross-source reuse. |
| first_observed / last_observed | Matched-row source date range. |
| candidate_first_observed / candidate_last_observed | Candidate-only date range, available before identifier approval. |
| stale_rows | Matched observations older than the configured development freshness threshold. |
| invalid_dates / future_rows / metadata_missing | Source-wide diagnostics, repeated per group; not group-specific absence measures. |
| status / qualification | Missing, empty, candidate, conflict, matched/stale interpretation and limits. |

`coverage_summary.csv` has one row per group, cumulative discovered/reviewed CIN/GID counts, source match counts and numbers of missing/candidate/matched sources. It does not claim a complete corporate entity population.

## Signal handoff

Only `matches.status=matched` rows are exported as separate source CSVs under the signal run. The bundled engine retains its original raw/observation/evidence tables and controls. Business definitions are unverified by default, keeping unsupported trigger decisions NULL.

`cohort_row_groups` maps signal-input row IDs to cohort raw IDs and groups. `cohort_signal_evidence` derives a separate cohort group only when all contributing raw rows have exactly one group. If a facility spans target groups, it remains `shared_or_unresolved_group`; full balances are not duplicated into both groups. Original source and Counterparty mastergroup results remain separate.

`cohort_signal_summary.csv` always has one row per group/signal, with evidence counts, pending-definition counts and fresh development candidates. Zero evidence items means no linked evidence reached the signal test; consult upstream coverage to distinguish missing files, rejected links, shared allocations or genuinely empty supplied results. It is not a negative financing signal.

`COHORT_GROUP:<MG>` is a testing key at group level when feeding approved links into the engine. It does not merge multiple legal entities into one party identity. No monetary exposure is summed across CLO, DRR and PVD. Group utilisation, FX/participation inference and borrower allocation need separately agreed definitions.

## Run metadata and limitations

`run_manifest.json` stores assessment time, membership policy, configuration/approval/code hashes and input checksums/metadata. Raw source files are never changed. Runs are saved to new directories; failures retain staging diagnostics. As-of filtering uses dates in exports and cannot reconstruct historical database versions or relationship effective periods that were not supplied.

Counterparty catalog equivalence is unconfirmed until checked in the SQL environment. The earlier package's PVD/DRR/Facilities source samples were independently limited and cannot establish join completeness. SIG03 needs a source, SIG07 needs an advisory definition, SIG05 and PVD sector aggregate are excluded.


## SIG07 Application Ratings discovery, 4 November 2026

The new candidate table is delta.prod_credit_and_lending_gda.application_ratings.
Its fields and native identifiers are not yet a runtime ingestion contract.
application_ratings_samples.py retains source CIN/GID/mastergroup roles and
Facilities relationship/proposal serial values as discovery candidates.
APPLICATION_SERIAL_NUMBER and CREDIT_PROPOSAL_SERIAL_NO are lookup inventory
labels for this sample pack only; they are not approved global identifier types.
The metadata result lists matched column names, snapshot/type/provider candidates
and blocked routes. Schema existence alone does not validate semantic equivalence.
Compare S&P/CRR scales and advisory meaning after source definitions and samples.
