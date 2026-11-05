# Bond Radar Signal Planning Notes

**5 November 2026 meeting decisions (development-2).** These supersede the earlier statements on SIG01, SIG02, SIG03, SIG06 and SIG07 below. Full comparison: `../docs/MEETING_ALIGNMENT_REVIEW.md`.

| Signal | Decision |
| --- | --- |
| SIG01 | Any drawing over EUR 50m on any **Cat A** bank facility (RCF, term loan, bilateral). HSBC share and the inferred total (÷ participation) are both considered. Facilities `limit_cat` is the Cat A filter, no longer a SIG07 candidate. |
| SIG02 | Event date = internal **credit approval date**, not signing. |
| SIG03 | Split into **SIG03A** (roll of a swap tied to maturing debt) and **SIG03B** (enquiry for a new pre-hedge swap). FX swaps first. |
| SIG06 | Covenant pressure = leverage **within half a turn** of the covenant maximum. Utilisation > 70% is context only (`CTX_UTIL`). |
| SIG07 | Rating advisory is sourced from **call reports** (CME, not integrated). Application Ratings CRR and Facilities/PVD category fields are credit context (`CTX_CREDIT`). |
| Investor sales | The number of investor sales is dropped. |


Date: 29 October 2026

## Current SIG07 Application Ratings scope: CRR only, 4 November 2026

The user requested adding CRR to the rating-advisory signal. Application Ratings
now contributes only CRR context: final_crr, scale, separate prior/proposed/approved
states, relevant application identity and dates. Agency rating fields are not
added in this step. Existing source investigation remains available as background.
No CRR level/change is an approved advisory trigger, and missing CRR is not zero.

The available samples yield ten candidate effective-period application records,
with nine populated final_crr values and one unavailable placeholder. Preserve
multiple entities/applications and competing values. Source/date-scoped CIN links
and validity rules remain development assumptions. The prior consolidated 604-row
file is preserved; the new addition produces 614 evidence rows. Use the
[CRR-only workflow](pvd_client_cohort_lab/sql_templates/sig07_crr_20261104/README.md)
and `analysis/sig07_crr_addition_20261104/` outputs.

## SIG07 Application Ratings candidate, 4 November 2026

Add **delta.prod_credit_and_lending_gda.application_ratings** alongside Facilities
Limits and PVD OMNIA DRR for comparative testing. The user reports S&P, CRR and
other rating types. Source columns, client/application keys, observation/effective
dates, approval states, scale and record grain remain to be verified.

Use the [three-client sample pack](pvd_client_cohort_lab/sql_templates/sig07_application_ratings_20261104/README.md)
for Vodafone MG001356, Siemens Energy MG102229 and SoftBank MG101624. The pack
reads source metadata and produces per-client sample/profile SQL from actual
scalar columns. Retain separate types/providers/history and all candidate rating
columns. No rating level or category is automatically an advisory event.

Compare the three sources on client coverage, verified key scope, freshness,
rating-type coverage, actual/proposed/final states, history and a known advisory
example before selecting the best source. Preserve native IDs and ambiguous
matches. Application/proposal serial and relationship lookups are discovery
bridges, not approved equivalences. Existing processed signal evidence is not
relabelled; runtime ingestion will follow returned schema/sample validation.

## Development decisions, 3 November 2026

These decisions supersede earlier extraction and missing-drawn handling below.
Use the [current extraction workflow](pvd_client_cohort_lab/CURRENT_WORKFLOW.md)
for Vodafone MG001356, Siemens Energy MG102229 and SoftBank MG101624.

- For **SIG01 only**, treat missing/blank drawn amounts as zero for development
  calculations. Preserve raw values and flag current/prior imputations. Invalid
  numbers and absent comparison observations remain unavailable. SIG06's
  missing-data handling and unverified business thresholds are unchanged.
- Reduce daily repetition: CLO keeps two latest available group snapshots;
  other signal sources keep one. Preserve raw exports separately, display source
  dates and flag stale snapshots. Latest available is not necessarily current.
- Facilities selection uses effective record periods as a test rule. Retain
  overlapping/unknown versions for review. Do not filter solely on
  `latest_record=CURRENT`. Shared DRR borrower associations do not add limits;
  consolidate only agreeing exposure attributes and retain lineage.
- Counterparty access is **`delta.prod_party_gda.counterparty_core`**, correcting
  the earlier Hive route as instructed. Run live schema/access checks; column,
  date and lifecycle semantics and equivalence to the old Delta path remain
  unverified. Preserve mapping snapshots preceding CLO dates plus the latest.
- Include Facilities **`limit_cat`** as a **SIG07 advisory candidate**. CAT codes
  and `advised_ind` need definitions before assigning an advisory-engagement
  trigger. Preserve source codes and null unverified trigger values.

The [3 November review](analysis/source_refresh_review_20261103/Findings.md)
records row reductions, client coverage and remaining limitations.

## Current extraction and refinement approach

At this stage, collect the available candidate data from the discussed sources, then use testing to refine the fields, source choices and signal definitions. Begin with CLO as the first workstream, while progressing the other sources as access and extraction capability permit. Final source selection remains open.

Broad collection means retaining relevant candidate attributes and available history within an agreed date, country and client scope. Partition or batch large extracts as needed. The shared client cohort is used later for testing and cross-source comparisons; it does not have to define the entire raw extraction population.

### Extraction workstreams

- **CLO:** facility, borrower, product, drawn amount, limit, currency and historical observation data for SIG01 and SIG06.
- **Counterparty Core supporting enrichment:** borrower CIN/GID, mastergroup identifier, lifecycle status and observation dates to improve CLO mastergroup completeness. The proposed catalog table is `delta.prod_party_gda.counterparty_core`, subject to confirmation. Preserve the raw CLO and Counterparty extracts separately before deriving enriched records.
- **Facilities Limits:** facility creation, product, client identifiers, record history, categories and rating-related attributes for SIG02 and SIG07 investigation.
- **Party KYC GDA:** client and case identifiers, review purposes, statuses, event details and case/source dates for SIG04.
- **Covenants GDA:** covenant and testing-instance records, including types, statuses, actual values, thresholds, operators and dates for SIG06 investigation.
- **DRR Facility Limits:** client/facility identifiers, approved limits, utilisation, currencies and reporting dates as an alternative SIG06 source.
- **PVD OMNIA DRR:** relationship identifiers, limit/utilisation measures, category/rating attributes and business/ETL dates for SIG06 and SIG07 investigation.

Continue source discovery for SIG03 derivatives and pre-hedging enquiries. For SIG07, confirm whether the existing category/rating attributes identify the intended advisory activity; seek engagement records separately if they do not. Verify the proposed Counterparty Core table and its mappings using the enrichment approach below. Identify the SF Approval location where required for the investigation, without assuming its qualified name.

### Process from extraction to signal evidence

| Stage | Work | Expected output |
| --- | --- | --- |
| 1 Agree scope and inventory | Identify candidate sources, fields, history, client/country coverage and extraction bounds. Record source locations and unresolved access or definition gaps. | A source-specific extraction specification. |
| 2 Extract each source separately | Capture available candidate records and history using source-appropriate queries and partition/date filters. The separate workstreams can progress independently; actual concurrency depends on the environment. | Source-specific raw extracts and schemas. |
| 3 Preserve the raw evidence | Retain original values and identifiers. Store data with its schema, table definition, exact query and parameters, extraction timestamp, observed dates and extraction outcome. Keep a versioned copy before transformations. | Raw datasets with reproducible extraction metadata. |
| 4 Profile and refine | Check coverage, missing values, sentinel values, date semantics, record grain and duplicates. Confirm amount definitions, units and currency. Test identifier mappings and joins on a shared client cohort before enrichment. | Refined source datasets, data-quality findings and validated mappings where available. |
| 5 Assemble candidate signal datasets | Derive the evidence for SIG01, SIG02, SIG03, SIG04, SIG06 and SIG07 where source data supports it. Retain client/entity IDs, source record references, business-event dates, observation dates and qualifications. | Separate candidate signal datasets and an explicit gap list. |
| 6 Review with bankers and agree dashboard inputs | Review relevant and routine client examples. Agree definitions, thresholds, comparison periods and repeat-event handling. Return to extraction or refinement where evidence is insufficient. | Reviewed signal rules and supported dashboard input records. |

### Rules for broad raw capture

- Preserve candidate records before applying the EUR 50 million materiality baseline or the proposed utilisation threshold above 70%. These are later signal tests, not raw capture filters.
- Retain the history and product/status context needed to identify changes, routine activity and later ineligible states. Do not assume a global latest source date is a complete snapshot.
- Keep source datasets separate at landing. Normalisation, deduplication, currency treatment and joins belong in derived datasets after their rules have been validated.
- Preserve original identifiers, including leading zeros and prefixes, and retain multiple borrower or covenant relationships.
- Record empty or failed extraction results explicitly. Investigate them without silently replacing a usable prior extract.
- Treat missing data and unresolved mappings as unavailable evidence rather than an absence of client activity. SIG03 and SIG07 remain subject to their source and definition gaps.

Testing is iterative: findings about missing history, fields, source coverage or join keys feed back into the next extraction. Collecting data does not itself validate a signal or establish a bond issuance opportunity.

## Proposed source approach for SIG01 SIG06 and SIG07

Use the CLO asset as the primary candidate source for **SIG01 RCF drawing increases** and the **facility-utilisation component of SIG06**. Include **PVD OMNIA DRR as another candidate source for SIG06 utilisation** during planning and testing. Use the Covenants asset alongside these sources to investigate explicit covenant pressure and breaches.

This is the proposed direction for planning and testing. The final source selection for SIG06 remains open. Amount definitions, historical coverage and trigger logic still need confirmation before implementation.

For **SIG07 ratings advisory**, investigate Facilities Limits and PVD OMNIA DRR as candidate sources because they contain category and rating-related attributes. Their suitability depends on confirming the business meaning of those attributes and the intended definition of SIG07.

| Signal or component | Proposed source | Assessment |
| --- | --- | --- |
| SIG01 RCF drawing increases | CLO | Compare deduplicated facility observations over time to identify material increases in drawings. |
| SIG06 facility utilisation | CLO | Identify utilisation above 70% using compatible drawn and approved-limit amounts. |
| SIG06 utilisation investigation | PVD OMNIA DRR | Test candidate utilisation and limit measures at client or relationship level, subject to validation of grain, units, identifiers and coverage. |
| SIG06 explicit covenant monitoring | Covenants | Assess financial covenant testing results, thresholds, actual values and relevant statuses. |
| SIG07 category and rating investigation | Facilities Limits | Investigate category, advised-indicator and grade fields. No field is yet confirmed to identify ratings-advisory activity. |
| SIG07 category and rating investigation | PVD OMNIA DRR | Investigate `drr_crr` and facility categories. Confirm whether these support the intended signal or provide credit-rating context only. |

## CLO source

```sql
"hive"."clo_prod"."clo_cda_contract_lvl"
```

### SIG01 RCF drawing increases

Identify revolving facilities using the validated product classification, initially `local_product_type_lbs = 'REV'`. Compare drawn amounts across observations for the same scoped facility key, preserving each observation's `run_date`.

The existing sample includes `ag_acc_bal_drawn_sub_lim_usd` as a candidate pre-aggregated drawn measure. Its business definition and whether it represents HSBC's share or the whole facility need confirmation.

Jerome's proposed EUR 50 million baseline relates to the total drawing for investment-grade corporates. It is separate from the still-open definition of a material increase over time.

### SIG06 facility utilisation

The proposed calculation is:

**Utilisation percentage = drawn amount / approved facility limit × 100**

Flag utilisation **greater than 70%** as a candidate indication of high facility usage. This threshold is a business proposal to validate.

The CLO schema contains `facility_drawn_amount` and `facility_limit_amount` as candidate fields. Confirm their population and definitions before selecting the calculation inputs. In particular, confirm that the limit is the appropriate approved-limit denominator.

### Shared requirements for using CLO

- Compare amounts for the same facility, currency, observation date and participation basis.
- Deduplicate the exploded source rows before assessing facility amounts. Do not sum repeated facility-level values.
- Do not divide a USD drawn amount directly by a limit expressed in local currency.
- Treat missing or zero denominators as an unavailable utilisation result.
- Validate facility-key scope and retain multiple borrower relationships where present.
- Resolve the header-only history extraction before relying on changes over time.

## Counterparty Core enrichment of CLO mastergroup data

### Purpose and review basis

Use Counterparty Core to supplement missing or invalid CLO mastergroup identifiers so that facility evidence can be linked to banker client groups for SIG01 and the CLO utilisation component of SIG06. Counterparty Core is a supporting identity source, not an independent bond issuance signal.

The enrichment reference is `clo_counterparty_pipeline.py` inside [clo_counterparty_production_handover.zip](clo_counterparty_production_handover.zip), together with that package's `systems_config.yaml`. The archive spells the file `clo_counterparty_pipeline.py`. Relevant functions are `norm`, `resolve_counterparty_dates`, `build_counterparty_mapping`, `build_counterparty_lookups`, `enrich_with_counterparty` and `validate_row_preservation`.

Reuse the matching principles after validation in Bond Radar. The prior solution's complete extraction, Spark configuration, eligibility rules, FX treatment and publication workflow are not being adopted. This review is based on code inspection; it does not establish current production access or matching coverage.

### Source location to confirm

The proposed Starburst catalog location supplied for this project is:

```sql
"delta"."prod_party_gda"."counterparty_core"
```

This identifier is **unconfirmed**. The reviewed package instead loads Counterparty Core directly as Delta from:

```text
hdfs://HDP46/apps/hive/warehouse/data-refinery/party/party/counterparty-core.delta
```

Confirm the catalog/schema/table, live column types, partition properties, available dates and physical location. Do not assume the proposed Hive table and the previous Delta path expose the same version or history. The package path is reference evidence, not a verified source location for the current extraction.

### Required fields and matching routes

| Purpose | CLO fields | Counterparty Core fields used by the previous pipeline | Requirement for Bond Radar |
| --- | --- | --- | --- |
| CIN identifier route | `obligor_cin` | `customer_relationship_cin_identifier` | Confirm the identifiers have the same meaning and scope. Preserve their original text and leading zeros. |
| GID identifier route | `rct_gid` | `customer_relationship_gid_identifier` | Use as another candidate route and a cross-check; do not allow a unique match on one route to conceal contradictory evidence on the other. |
| Mastergroup identifier | `rct_mastergroup_id` | `mastergroup_esr_identifier` | Preserve a valid original CLO ID. Fill a missing or configured-invalid ID only from an unambiguous candidate set. |
| Mastergroup names | `rct_mastergroup_name`, with `rct_group_name` as separate existing context | No mastergroup-name field is selected by the reviewed enrichment code. | Confirm a suitable name source separately if needed. Do not present an original CLO name as verified for a newly assigned ID. |
| Observation dates | `run_date` | `run_date` | Retain both source dates and agree the mapping's as-of policy. Verify actual date types and formats. |
| Relationship eligibility | CLO borrower/entity and source scope | `customer_relationship_lifecycle_status_code` | Confirm lifecycle codes and whether blank status may be accepted before applying the old configuration. |
| Row and join controls | Stable facility key, source/mapping system, booking entity, observation date and borrower association | Normalised CIN/GID keys, candidate IDs and per-route dates | Preserve the chosen input grain and prevent enrichment from multiplying or dropping records. |

The initial 19-column CLO raw sample did not include `rct_gid`. Add it to the fields planned for the next CLO extraction, together with the original mastergroup ID and name, so that both matching routes can be assessed. The existing wider CLO extraction example already references `rct_gid`.

### Mapping preparation in the reviewed pipeline

1. Normalise identifiers as text: trim surrounding whitespace, collapse whitespace runs, uppercase the result and convert blank strings to null. Leading zeros are retained. Verify that these normalisation rules suit the actual identifier formats; do not strip country prefixes or convert identifiers to numbers without a confirmed rule.
2. Obtain the distinct CIN and GID keys needed by the CLO dataset. Restrict the Counterparty lookup to those keys, keeping the two identifier routes separate.
3. Apply a bounded Counterparty date window and select the latest observed date **per normalised key** within that window.
4. Only after selecting that latest date, apply the configured lifecycle-status and valid-mastergroup checks. The old code does not search back to an older active record when the latest record is inactive or has no usable mastergroup.
5. Collect distinct mastergroup IDs for each key at its selected date, recording the candidate list, candidate count and source date. Repeated records for the same key/mastergroup do not create additional candidates.
6. Produce one lookup record per CIN and one per GID, then left-join both lookups to CLO. Combine their candidate IDs into one distinct set for each CLO record.

The prior configuration used a 120-day Counterparty lookback, accepted lifecycle statuses `A`, `ACTIVE` and `Y`, included blank lifecycle status and treated `NO MSG` as an invalid mastergroup value. These are **previous configuration values to validate**, not agreed defaults for Bond Radar. Confirm other source-specific sentinel values through the data dictionary.

### Mastergroup selection and conflict handling

The previous code combines both routes before making a decision; it does not simply take CIN first and ignore GID evidence.

| Condition | Mastergroup result | Recorded status in the previous implementation |
| --- | --- | --- |
| Original CLO mastergroup is valid and Counterparty has no conflicting candidate. | Preserve the original CLO ID. | `original_preserved` |
| Original CLO mastergroup is valid but a Counterparty candidate differs. | Preserve the original CLO ID and flag the disagreement. | `source_conflict` |
| Original CLO mastergroup is missing or invalid and the combined CIN/GID candidate set contains exactly one distinct ID. | Fill that unique ID. This includes both routes agreeing or one route providing the only available candidate. | `matched_unique` |
| Original CLO mastergroup is missing or invalid and the combined set contains more than one ID. | Leave the final ID unresolved and retain all candidates for review. | `ambiguous` |
| Original CLO mastergroup is missing or invalid and neither route supplies a usable candidate. | Leave the final ID unresolved. | `unmatched` |

The match-rule labels are `clo_original`, `counterparty_cin`, `counterparty_gid` and `counterparty_cin_gid`; unresolved matches have no successful match rule. Do not pick an arbitrary mastergroup with MAX, MIN or a first-row rule to eliminate ambiguity. A `source_conflict` flag is a disagreement to investigate, not proof that either source is wrong.

### Dates and historical group membership

The previous pipeline caps the Counterparty window at the latest available Counterparty date not later than the overall effective CLO extraction upper bound, then selects the newest record for each matching key. CLO facilities can have different observation dates within that extraction window. Consequently, this approach does not by itself guarantee a point-in-time mapping for every historical CLO row.

For Bond Radar, decide whether the view should use group membership as known at each observation or restate history under a current group mapping. For point-in-time history, use mapping evidence no later than the relevant CLO observation and validate any available relationship-effective dates. For a current-group view, label that policy explicitly. Retain the per-route mapping dates and the date used for the decision; a single maximum mapping date is insufficient to explain all historical matches.

### Grain and evidence to preserve

Enrich at a validated borrower/entity association grain before using the result for group-level aggregation. Our CLO sample contains multiple obligor CINs for some facility keys. Retain those associations rather than selecting one borrower with MAX. If borrowers on one facility resolve to different groups, keep the relationship and conflict evidence for an agreed allocation rule; do not count the full facility amount independently in every group.

Preserve at least:

- Original CLO mastergroup ID and name, final mastergroup ID and any separately verified final name.
- Original and normalised CIN/GID keys, stable CLO row/facility identity and observation date.
- Per-route candidate lists, counts, selected mapping dates and the combined candidate set.
- `mastergroup_match_status`, `mastergroup_match_rule` and conflict/unmatched reasons.
- Counterparty source location, extraction bounds, lifecycle/invalid-value rules and the mapping as-of policy.

The prior internal working dataset contains detailed evidence, but its published CSV deliberately drops much of that evidence. Bond Radar should retain the audit fields in its derived enrichment dataset rather than inherit that restricted publication contract. Enriching the ID alone does not establish a valid mastergroup name.

### Validation before using the enrichment

Check lookup uniqueness and one-to-many relationships before joining. Compare record counts, key multiplicities and amounts before and after enrichment. The old control expects one row per facility; Bond Radar must adapt the control to its actual input grain, including observation dates, source scope and borrower associations where applicable.

Report original missing mastergroups, uniquely recovered IDs, remaining unmatched records, ambiguous records and source conflicts, broken down by relevant mapping system, country and source date. Review representative matches, conflicts and unmatched cases against source evidence. No recovery rate is established by this code review.

Preserve raw inputs and unresolved records. Confirm the mapping policy and mastergroup-name handling before publishing group-level signal evidence. This enrichment does not change the definitions or validation requirements for drawing increases, utilisation or the proposed thresholds.

## PVD OMNIA DRR as another SIG06 source

```sql
"hive"."pvd_prod_wave"."pvd_omnia_drr"
```

Include this asset in SIG06 planning and testing as an additional candidate for utilisation monitoring. It is not yet a confirmed implementation source or a replacement for CLO or explicit covenant evidence.

The sample contains candidate measures `drr_utils`, `drr_act_limit` and `drr_carm_limit`, together with `joi_relationship_id` and `joi_date`. The three measures are populated together in 70 of the 100 sampled rows.

Before testing the proposed utilisation threshold:

- Confirm the meaning of `drr_utils` and which limit field, if either, is the appropriate approved-limit denominator.
- Confirm that numerator and denominator use compatible units, currency, scope and observation dates. The presence of `exposure_usd` does not establish the currency of the other measures.
- Establish the record grain and authoritative mapping from `joi_relationship_id` to banker clients. The exposed schema has no explicit `facility_id`.
- Check current coverage and refresh frequency. The sampled business dates extend only to July 2025, which does not establish the latest date available in the full source.
- Agree how missing amounts, zero limits and negative utilisation values should be handled.

Compare PVD and CLO results only after their client population, dates, grain and measure definitions have been aligned. High utilisation from either source is a separate indicator from a covenant breach.

## Covenants source alongside utilisation sources

```sql
"delta"."prod_credit_and_lending_gda"."covenants"
```

High utilisation alone does not establish covenant pressure or a covenant breach. Retain the Covenants source for direct covenant evidence, including actual values, comparison operators, thresholds, testing dates and approved results where available.

The returned covenant sample contains non-financial reporting covenants. Financial covenant examples are needed before validating quantitative covenant pressure. An overdue reporting obligation should not automatically be interpreted as a financial breach.

Present utilisation pressure and explicit covenant findings as separate indicators under SIG06. Validate identifiers, observation dates and testing-instance grain before linking the sources. A facility can have multiple covenants and testing instances, so the join must preserve those relationships without multiplying facility amounts.

## SIG07 category and rating source investigation

Retain the following sources as candidates during planning and testing:

```sql
"delta"."prod_credit_and_lending_gda"."facilities_limits"
"hive"."pvd_prod_wave"."pvd_omnia_drr"
"delta"."prod_credit_and_lending_gda"."application_ratings"
```

### Evidence from the schemas and samples

| Source | Attributes | Recorded evidence |
| --- | --- | --- |
| Facilities Limits | `limit_cat`, `limit_category_type` | Populated classifications include `CAT-Category A` and `CAT-Category B`. Their relationship to SIG07 needs confirmation. |
| Facilities Limits | `advised_ind` | Contains `0` and `1`. Its meaning is unconfirmed; the name alone does not establish ratings-advisory activity. |
| Facilities Limits | `facility_grade_code`, `facility_grade_desc`, `sustainable_risk_rating_impact_proposed`, `sustainable_risk_rating_impact_approved` | Present in the schema but blank in the returned sample. Wider population and business definitions need checking. |
| PVD OMNIA DRR | `drr_crr` | Contains rating-like values such as `5.3` and `4.1`, alongside `NO CRR` and `XNA`. Confirm the rating definition and scale before interpretation. |
| PVD OMNIA DRR | `drr_fac_category`, `joi_facility_category` | Contains classifications including `CAT-A`, `CAT-B` and `CAT-S`. Their business meaning and relevance to ratings advisory remain unverified. |
| Application Ratings GDA | Schema pending; preserve actual rating types/providers, values, dates and application/client identifiers once verified. | User reports S&P, CRR and other types. Metadata-aware sample SQL was prepared on 4 November; no live sample or advisory interpretation is yet verified. |

### Planning conclusion and open definitions

The available attributes and the new user-provided Application Ratings location justify investigating all three candidates for SIG07. They do not yet establish that either source records a client requesting or receiving ratings-advisory services.

If SIG07 is intended to capture credit ratings or rating changes, `drr_crr` is a concrete candidate to investigate, with historical observations and the rating scale still to be validated. If SIG07 is intended to capture ratings-advisory engagements, a field or category must be confirmed to identify that activity explicitly.

Obtain the data dictionary or source-owner definitions for CAT-A/B/S, `limit_category_type`, `advised_ind` and `drr_crr`. Confirm with the DCM stakeholders which interpretation matches the intended signal. Do not assume a category code represents advisory activity or a numerical rating change represents deterioration without those definitions.

Final SIG07 source selection remains open pending this validation.

## Next validation steps

1. Agree extraction bounds and collect the candidate raw data and schemas across the identified workstreams, starting with CLO. Preserve query text, parameters and extraction metadata for each source.
2. Resolve the empty CLO history output, then obtain fixed-client or fixed-facility observations from the captured data to confirm key, date and deduplication rules.
3. Verify the proposed Counterparty Core catalog table and extract the required CIN, GID, mastergroup, lifecycle and date fields. Include `rct_gid` in CLO capture. Test the combined CIN/GID enrichment rules, conflicts, name handling, date policy and row/amount preservation before using enriched group identifiers.
4. Validate CLO drawn and limit definitions, including currency and HSBC participation versus whole-facility coverage.
5. Test recent Facilities Limits and KYC examples, validating facility creation and product classifications, KYC case purposes, business-event dates and client identifiers.
6. Obtain financial covenant examples and validate the relationship between covenant records, clients and facilities.
7. Test PVD OMNIA DRR and, where useful, DRR Facility Limits for SIG06 using a shared client cohort, validating measure definitions, identifier mapping, grain and current coverage before comparison with CLO.
8. Review SIG01 materiality and the proposed SIG06 utilisation threshold with the business stakeholders, then select the suitable SIG06 source or combination of sources.
9. Confirm the intended SIG07 business event and the category, advised-indicator and rating definitions in Facilities Limits and PVD OMNIA DRR before selecting fields or implementing trigger logic. Continue SIG03 source discovery in parallel.

Keep DRR Facility Limits as an alternative source for utilisation if CLO's definitions or coverage are unsuitable.

## Supporting references

- [Internal signal requirements](Bond%20Radar%20Internal%20Signals.md)
- [Internal signal data source reference](Bond%20Radar%20Internal%20Signal%20Data%20Sources.md)
- [Sample review findings](analysis/internal_signal_samples/Findings.md)
- [Interactive source to signal flowchart](diagrams/bond-radar-signal-flowchart.html)
- [Interactive extraction and signal testing process](diagrams/bond-radar-extraction-process.html)
- [Previous CLO and Counterparty handover archive](clo_counterparty_production_handover.zip), used as a reference for mastergroup enrichment only.

## Appendix A Signal source and attribute planning table

This table covers all retained internal signals. SIG05 remains excluded. Sources and attributes are candidates for planning and testing, with their business meaning and suitability still to be validated. SIG06 is split by assessment and source because utilisation and explicit covenant evidence require different inputs.

| Signal | Intended assessment | Possible sources | Candidate attributes or required information | What we still need |
| --- | --- | --- | --- | --- |
| **SIG01 RCF drawing increases** | Identify material increases in drawings for revolving facilities over time. | **CLO**, with **Counterparty Core** supporting mastergroup enrichment. | `local_product_type_lbs`; `sub_lim_id`, `rct_facility_ref`, `facility_id`; `source_system`, `mapping_system`, `hsbc_booking_legal_entity`; `run_date`; `ag_acc_bal_drawn_sub_lim_usd`, `facility_drawn_amount`, `facility_limit_amount`, `facility_currency`; `obligor_cin`, `rct_gid`, `rct_mastergroup_id`, `rct_mastergroup_name`. Counterparty fields and audit outputs are specified in the enrichment section. | Resolve the empty history export and obtain repeated observations for fixed facility keys. Validate amounts, currency and participation basis. Deduplicate repeated amounts and preserve multiple borrowers. Verify the Counterparty table and combined CIN/GID mapping, historical date policy and name handling. Agree the material-increase period and rule separately from the EUR 50 million total-drawing baseline for investment-grade corporates. |
| **SIG02 New RCF term loan or bridge facility** | Identify a new financing facility that may subsequently be refinanced through bonds. | **Facilities Limits** | `facility_id`, `cin`, `relationship_id`, `customer_id`; `product_code`, `product_type`; `facility_creation_date`, `loan_approva_dt`, `record_start_dt`, `record_end_dt`, `run_date`, `latest_record`; `facility_ccy`, `proposed_limit`. | Obtain recent client-matched examples with populated creation and client fields. Confirm product codes for RCFs, term loans and bridge facilities. Establish whether creation represents signing, approval, administration or migration. Validate record-version rules and the unexpected date-shaped values in `active_facility_ind`. The returned sample is historical and does not validate the required event. |
| **SIG03 Derivatives and pre hedging activity** | Identify pre-hedge or swap-pricing enquiries that may relate to future bond financing. | **No source identified.** Investigate enquiry or pricing-request records with the corporate derivatives sales or hedging team supporting DCM clients. | **Required information, not confirmed source columns:** client and legal entity identifiers; enquiry or pricing-request identifier; request date; product or activity classification; financing purpose or supporting context; request status; notional, currency and tenor where available; update timestamp. | Identify the source system and owner. Confirm whether enquiries are captured as well as executed trades. Obtain examples linked to bond issuance, routine hedging examples and enquiries that did not progress. Define how relevant financing preparation will be distinguished from ordinary swap activity. |
| **SIG04 Entity onboarding and KYC activity** | Identify relevant onboarding or KYC events while distinguishing routine refreshes. | **Party KYC GDA** | `cin`, `related_case_id`, `related_case_status`; `review_purpose_code`, `review_purpose_desc`; `review_request_created_time_stamp`, `related_case_resolved_time`, `related_case_update_time`, `run_date`; `event_trigger`, `kyc_case_event_trigger_type_code`, `trigger_event_sub_type_multi`. | Confirm the meaning of New to Bank, Trigger, Periodic and Remediation purposes and the case timestamps. Obtain recent cases and distinguish business-event dates from dataset refresh dates. Validate repeated-case handling and client coverage. Establish whether signatory changes or new entity onboarding can actually be identified; detailed trigger fields are blank in the returned sample. |
| **SIG06 Utilisation using CLO** | Identify facility utilisation greater than 70%. | **CLO**, with **Counterparty Core** supporting mastergroup enrichment. | `facility_drawn_amount`, `facility_limit_amount`, `facility_currency`; facility-key, borrower, mastergroup and source-scope fields used for SIG01; `run_date`. `ag_acc_bal_drawn_sub_lim_usd` is another drawn-measure candidate, subject to compatible denominator and unit definitions. | Confirm the appropriate approved-limit denominator, matching currency, participation basis and dates. Deduplicate facility amounts and validate mastergroup enrichment without multiplying records or amounts. Agree treatment of missing or zero limits and validate the proposed threshold. Do not mix USD drawn amounts with local-currency limits or interpret high utilisation alone as a covenant breach. |
| **SIG06 Utilisation using other candidates** | Investigate utilisation at the source's verified client, relationship or facility grain. | **PVD OMNIA DRR**; **DRR Facility Limits** as an alternative. | **PVD:** `drr_utils`, `drr_act_limit`, `drr_carm_limit`, `joi_relationship_id`, `joi_key`, `joi_date`, `etlmonth_drr`, `etlmonth`. **DRR Facility Limits:** `facility_id`, `cin`, `drr_mastergroup_id`, `approved_limit`, `utilisation`, `approved_limit_ccy`, `utilisation_ccy`, `reporting_date`, `run_date`. | For PVD, confirm measure definitions, the denominator, currency, record grain and the client-identifier bridge; no explicit facility ID appears in its schema. For DRR, obtain recent records and confirm compatible amount and currency definitions. For both, check current coverage, zero or missing denominators, negative values and alignment with the agreed client cohort. Independent limited samples cannot establish join coverage. |
| **SIG06 Explicit covenant pressure or breach** | Assess financial covenant results and, where definitions permit, proximity to a contractual threshold. | **Covenants GDA** | `facility_id`, `relationship_id`, `covenant_id`, `active_testing_id`; `covenant_type`, `covenant_status`; `active_testing_actual_value`, `active_testing_final_value`, `active_testing_testing_threshold_value`, `active_testing_testing_threshold_operator`; `active_testing_final_result`, `active_testing_approval_status`, `active_testing_testing_status`, `reporting_dt`, `run_date`. | Obtain financial covenant examples with populated measures, operators, thresholds and approved results. Confirm units, breach and headroom interpretation, testing-instance grain and identifier mappings. The current sample contains non-financial reporting obligations, so its Overdue statuses do not establish financial breaches. Prevent covenant joins from multiplying facility amounts. |
| **SIG07 Ratings advisory or rating related investigation** | Confirm whether the intended signal is an advisory engagement, a credit-rating change or a relevant category classification. | **Facilities Limits**, **PVD OMNIA DRR** and **Application Ratings GDA** as unverified candidates. If these do not identify advisory activity, investigate Ratings Advisory engagement records separately. | **Facilities Limits:** `limit_cat`, `limit_category_type`, `advised_ind`, `facility_grade_code`, `facility_grade_desc`, `sustainable_risk_rating_impact_proposed`, `sustainable_risk_rating_impact_approved`. **PVD:** `drr_crr`, `drr_fac_category`, `joi_facility_category`, `joi_relationship_id`, `joi_date`. **Application Ratings:** source columns pending; capture S&P/CRR/other types, providers, values, statuses, dates and native keys after schema review. | Confirm SIG07's business definition with DCM stakeholders. Obtain definitions for CAT-A/B/S, the limit categories, `advised_ind` and the rating scale. Determine whether any attribute explicitly identifies ratings-advisory activity. If rating changes are intended, obtain history with reliable client keys and dates. Category names or numerical ratings alone do not prove an advisory engagement. |

### Source identifiers for the appendix

- **CLO:** `hive.clo_prod.clo_cda_contract_lvl`.
- **Counterparty Core supporting enrichment:** proposed `delta.prod_party_gda.counterparty_core`, unconfirmed; the reviewed package uses the Delta path documented in the enrichment section.
- **Facilities Limits:** `delta.prod_credit_and_lending_gda.facilities_limits`.
- **Party KYC GDA:** `delta.prod_party_gda.kyc`.
- **Covenants GDA:** `delta.prod_credit_and_lending_gda.covenants`.
- **PVD OMNIA DRR:** `hive.pvd_prod_wave.pvd_omnia_drr`.
- **DRR Facility Limits:** `delta.prod_credit_and_lending_mda.drr_facility_limits`.

Across all retained signals, use a shared client cohort for testing, retain source-record and observation dates, establish identifier mappings, confirm refresh and historical coverage, and review the resulting examples with the business stakeholders before implementing triggers. Candidate columns listed above are not assumed to be populated or sufficient merely because they exist in a schema.

Application Ratings GDA candidate location (added 4 November 2026): `delta.prod_credit_and_lending_gda.application_ratings`.
