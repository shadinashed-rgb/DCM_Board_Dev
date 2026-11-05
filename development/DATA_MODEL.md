# Source contracts, joins and aggregation

## Source reference

| Dataset | SQL source | Observed role / grain | Principal caveat |
| --- | --- | --- | --- |
| CLO | hive.clo_prod.clo_cda_contract_lvl | Contract/sub-limit/facility observations over dates; group/CIN/GID and product | REV facility comparison, whole-facility/share and missing drawn semantics |
| Counterparty | delta.prod_party_gda.counterparty_core | Dated entity-to-group mappings through CIN and GID | Point-in-time lifecycle, conflicting candidate groups; never overwrite a valid original group |
| DRR | delta.prod_credit_and_lending_mda.drr_facility_limits | Exposure/UID observations with borrower associations | Shared exposures, limit hierarchy, product eligibility and currency |
| Facilities | delta.prod_credit_and_lending_gda.facilities_limits | Effective versions with facility/product/borrower contexts | Same ID can have several products/associations; publishing dates differ by country/source |
| PVD OMNIA DRR | hive.pvd_prod_wave.pvd_omnia_drr | Native relationship/supergroup/composite-key observations | Not an explicit CIN table; amounts/currency/grain unverified |
| KYC | delta.prod_party_gda.kyc | Case/entity observations | Latest target export empty; arrays and namespace/date semantics |
| Covenants | delta.prod_credit_and_lending_gda.covenants | Expected covenant terms/test observations | Actual financial tests not supplied; latest misleading export quarantined |
| Application Ratings | delta.prod_credit_and_lending_gda.application_ratings | CIN/application/version/snapshot observations | No verified native MGID; periods/flags competing; CRR scale interpretation |

These are SQL catalog locations used in the current work, not proof of live access or unchanged schemas. The returned column inventories/DDL and source profiles are preserved under sql/, data/application_ratings_schema/ and pvd_client_cohort_lab/profiles/. Capture live schema errors rather than substituting guessed columns.

## Preserve grains before making a presentation table

The intended design is a small local database with separate raw/reference/fact tables and one long-format signal evidence view. Do not flatten all raw sources through facility ID into one giant join: many-to-many products, borrowers, versions and snapshots multiply amounts.

1. **Raw landing:** immutable source files, original headers, original identifier strings and a manifest describing submitted SQL, scope, time, source date, row limit and outcome. Separate schema/profile/error results from source data.
2. **Identity links:** canonical mastergroup targets plus source-scoped CIN/GID/relationship proposals and review decisions, namespace, date range, evidence and conflict state. Keep source-native group fields independently.
3. **Current/version selection:** select appropriate snapshots at the source's verified publishing grain, then effective record periods. CLO retains comparison snapshots. Never resurrect a previously eligible key after a newer ineligible observation. Retain the reductions and rejected/unknown states.
4. **Source facts:** Facilities parents/products/borrower associations and versions; DRR exposures and borrower associations; CLO contracts/drawings; covenant terms/tests; KYC/enquiry events; application-rating versions. Source-specific keys remain independent until equivalence is proved.
5. **Signal evidence:** one record per signal/client/source/component/key/date, with measure, currency/scale, data availability, imputation, trigger verification, conflicts and lineage. Multiple records per client/signal are expected.
6. **Dashboard views:** selected evidence, coverage and validation state for bankers. Do not turn partial, stale, missing or ambiguous data into an apparently definitive group aggregate.

The active code already uses local SQLite cohort and signal databases plus CSV exports. The richer parent/product/event model remains a next development step, not a claim that all proposed tables are implemented. Fresh runs write `baseline/cohort/cohort.sqlite` and `baseline/signals/results/bond_radar.sqlite`; the separate CRR adapter appends context to the long CSV.

## Identity and Counterparty enrichment

- Target mastergroups are explicit anchors. Names and aliases are review inventories only. No fuzzy-name approvals or transitive expansion through a shared supergroup.
- CIN, GID, PVD relationship/key/supergroup, customer/relationship IDs, facility IDs and application serials are distinct namespaces. Keep strings, source, country/booking scope and evidence.
- The development `--test-observed-links` route permits only bounded uniquely observed associations and records assumptions. Genuine production approval requires reviewed mappings; do not infer historical legal membership from today's links.
- For each CLO observation, prepare Counterparty state per mapping key using the latest available mapping date no later than the CLO date, then evaluate lifecycle rules. Do not prefilter away the newest invalid state and accidentally restore an older valid one.
- Build CIN and GID candidate routes separately and union their candidates. Keep non-target and conflicting mappings through the reference stage. Preserve a valid original CLO mastergroup. With a missing/invalid original, fill only a unique combined candidate under the explicit test/review policy. Conflicting, ambiguous and unmatched cases stay flagged.
- Group-ID fields do not supply names. Keep original group, candidate group, selected group, route, source dates and conflicts separately. The legacy Counterparty zip is evidence for this feature only.

## Deduplication and aggregation

Exact-row hashes support an observation inventory, not a universal financial deduplication rule. Reordered CSVs can contain the same observations; do not ingest both as new business events. The large historical CLO exports include such overlap and are not additional current facilities.

Facilities IDs repeat across products, borrower associations, countries and versions. Preserve child contexts; conflicting creation dates must not be resolved with arbitrary first/MAX. DRR shared borrower rows can represent one exposure only if all non-association attributes agree. With conflicts, withhold ratios. An internal DRR UID does not establish an equal Facilities/CLO key.

Do not sum daily snapshots, source overlaps, mixed currencies, whole-facility/share amounts or parent/child limits. Ratios require valid comparable numerator/denominator, currency, unit, date and scope. Missing/zero denominators remain unavailable. Apply the drawn-zero exception only to SIG01 with flags; imputed comparisons are never assessed for materiality.

**development-2 cross-source lookups (development links, not approved joins):**

- SIG01 Cat A eligibility uses Facilities `limit_cat` where the CLO `sub_lim_id` equals a Facilities `facility_id`.
- SIG02 credit approval date uses Application Ratings `approval_dt` where `credit_proposal_serial_no` (preferring the same CIN) links one approval date.

Both record their basis on every row (`limit_category_basis`, `credit_approval_source`). Neither is used to merge amounts across sources. The EUR 50m SIG01 test converts currency only with configured FX rates, and infers whole-facility drawings only from an explicit participation share; HSBC's share is used as a lower bound.

CRR is categorical and scale-dependent. Multiple applications/CIN values remain separate; neither averages nor MAX produce a valid group rating. Current application periods and latest flags are development interpretations requiring source-owner confirmation.

## Current output contract

`runs/aligned_20261105_004/BOND_RADAR_SIGNAL_EVIDENCE.csv` (development-2) is the presentation-evidence starting point, not a final dashboard API; `results/ALL_SIGNALS_WITH_CRR.csv` is the archived development-1 sample result. Fields include client/group, signal/source/component, assessment status and business_trigger, observation/event/assessment dates, identifiers, monetary/ratio/CRR context, conflicts, mapping state, validation reason and original record references. `details_json` retains source-specific information.

`signal_id` takes the signal values SIG01, SIG02, SIG03A, SIG03B, SIG04, SIG06 and SIG07, or the context values `CTX_UTIL` (utilisation) and `CTX_CREDIT` (Facilities/PVD category and Application Ratings CRR). Context records are not signals. Use `source=application_ratings` and `component=crr_context` for the CRR contribution (now `CTX_CREDIT`).

New development-2 columns:

| Signal | Columns |
|---|---|
| SIG01 | `material_drawing_for_testing`, `drawn_field`, `limit_category`, `limit_category_basis`, `cat_a_eligible`, `materiality_status`, `materiality_threshold`, `drawing_in_threshold_currency`, `hsbc_participation_share_percent`, `inferred_total_drawing` |
| SIG02 | `event_basis`, `credit_proposal_serial_no`, `credit_approval_date`, `credit_approval_source`, `approval_matches_creation_date`. `recent_creation_for_testing` now means within 90 days of the credit approval date |
| SIG06 | `covenant_pressure_for_testing`, `covenant_headroom_turns` | Blank business_trigger means unverified, not false. Use coverage CSVs to distinguish missing file, empty export, no matches, candidates only and conflict. Freshness uses exported source dates, not a historical database time-travel guarantee.

Archived path-bearing manifests and databases keep the original location as provenance. New runs create local references. Do not depend on old absolute paths or rewrite raw evidence merely to make a historical path look local.
