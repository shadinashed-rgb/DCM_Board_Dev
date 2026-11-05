# Bond Radar Internal Signal Data Source Reference

**5 November 2026 meeting decisions (development-2).** These supersede the earlier statements on SIG01, SIG02, SIG03, SIG06 and SIG07 below. Full comparison: `../docs/MEETING_ALIGNMENT_REVIEW.md`.

| Signal | Decision |
| --- | --- |
| SIG01 | Any drawing over EUR 50m on any **Cat A** bank facility (RCF, term loan, bilateral). HSBC share and the inferred total (÷ participation) are both considered. Facilities `limit_cat` is the Cat A filter, no longer a SIG07 candidate. |
| SIG02 | Event date = internal **credit approval date**, not signing. |
| SIG03 | Split into **SIG03A** (roll of a swap tied to maturing debt) and **SIG03B** (enquiry for a new pre-hedge swap). FX swaps first. |
| SIG06 | Covenant pressure = leverage **within half a turn** of the covenant maximum. Utilisation > 70% is context only (`CTX_UTIL`). |
| SIG07 | Rating advisory is sourced from **call reports** (CME, not integrated). Application Ratings CRR and Facilities/PVD category fields are credit context (`CTX_CREDIT`). |
| Investor sales | The number of investor sales is dropped. |


**Current SIG07 contribution, 4 November 2026:** Application Ratings supplies
CRR-only context in this stage. Primary display field is final_crr, with crr_scale
and separate previous/proposed/approved states, source/application identity and
dates. Missing values remain unavailable. No agency rating or advisory trigger
is inferred by this addition. See the
[CRR-only workflow](pvd_client_cohort_lab/sql_templates/sig07_crr_20261104/README.md).

**4 November 2026 SIG07 addition:** the user supplied
`delta.prod_credit_and_lending_gda.application_ratings` as another candidate,
reporting S&P, CRR and other rating types. Schema, client/application keys,
dates, rating scales and advisory meaning await samples. Use the
[three-client sample pack](pvd_client_cohort_lab/sql_templates/sig07_application_ratings_20261104/README.md).

**3 November 2026 update:** the user corrected Counterparty to the Delta catalog:
`delta.prod_party_gda.counterparty_core`. Validate live access/schema and source
semantics; the earlier Hive route is superseded. Current extraction now selects
latest snapshots and effective Facilities versions. SIG01-only missing drawn
amounts become zero with audit flags. Retain `limit_cat` as a SIG07 advisory
candidate pending definitions. See the [current workflow](pvd_client_cohort_lab/CURRENT_WORKFLOW.md).

Version 1.1 | 29 October 2026 | For stakeholder review

## 1 Current scope and evidence

This reference follows the [planning notes](Bond%20Radar%20Signal%20Planning%20Notes.md): collect candidate data and schemas across the discussed sources, preserve raw evidence, then refine fields, source choices and signal rules through testing. Begin with CLO while other source workstreams progress. SIG05 and PVD sector aggregate are excluded from the active plan.

Evidence comes from [InternalSignalsDataSources.xlsx](InternalSignalsDataSources.xlsx), Sheet1 A1:D5; the returned [SQL samples](sql/sql_samples); [extract_clo_rev_universe.sql](extract_clo_rev_universe.sql); and code inspection of `clo_counterparty_pipeline.py` and `systems_config.yaml` inside the [previous handover archive](clo_counterparty_production_handover.zip). Workbook references below describe the original investigation. Later sample observations and planning decisions are identified separately.

Known table identifiers are candidate access routes, not proof of complete coverage, daily freshness or correct business interpretation. Counterparty's proposed catalog location has not been verified.

## 2 Active source inventory

| Source | Catalog identifier | Role and verification position |
| --- | --- | --- |
| CLO | `hive.clo_prod.clo_cda_contract_lvl` | SIG01 and SIG06 utilisation candidate. Schema/raw/profile results returned; history export is header-only. |
| Counterparty Core | **Proposed** `delta.prod_party_gda.counterparty_core` | Supporting CLO mastergroup enrichment. Catalog table and current access are unconfirmed; prior code reads a Delta path. No current Counterparty sample has been supplied. |
| Facilities Limits GDA | `delta.prod_credit_and_lending_gda.facilities_limits` | SIG02 and SIG07 candidates; also a possible identifier bridge. Schema/sample returned, but current event coverage remains unvalidated. |
| Party KYC GDA | `delta.prod_party_gda.kyc` | SIG04 case/purpose/date evidence. Signatory and new-entity interpretations require validation. |
| Covenants GDA | `delta.prod_credit_and_lending_gda.covenants` | SIG06 direct covenant evidence candidate. Returned records are non-financial reporting obligations. |
| DRR Facility Limits | `delta.prod_credit_and_lending_mda.drr_facility_limits` | Alternative SIG06 utilisation source. Amounts/IDs exist in the sample; recent coverage and compatible units need validation. |
| PVD OMNIA DRR | `hive.pvd_prod_wave.pvd_omnia_drr` | SIG06 utilisation and SIG07 category/rating investigation. No explicit facility ID or currency field appears in the supplied schema. |
| Application Ratings GDA | `delta.prod_credit_and_lending_gda.application_ratings` | SIG07 candidate added 4 November. User reports S&P/CRR/other types; schema, namespace/date/grain and advisory interpretation require verification. |

SIG03 has no identified table. SF Approval remains a possible supporting asset mentioned in the workbook; its qualified location and access are unresolved. The source inventory does not establish that every signal is implementable.

## 3 SIG01 RCF drawing increases

**Original workbook reference:** Sheet1 A2:B2 and D2.

The workbook records use of Shadi's latest CLO query after an earlier query did not give the required results. The supplied [previous CLO query](extract_clo_rev_universe.sql) provides field and date/grain conventions; its whole extraction solution is not being adopted automatically. LoanIQ was named in the meetings, but its relationship to the CLO asset is unconfirmed.

Capture product classification, facility keys and scope, borrower CIN/GID, original mastergroup fields, drawn/limit measures, currency, maturity and source dates. Candidate columns include `local_product_type_lbs`, `sub_lim_id`, `rct_facility_ref`, `facility_id`, `obligor_cin`, `rct_gid`, `rct_mastergroup_id`, `rct_mastergroup_name`, `facility_drawn_amount`, `ag_acc_bal_drawn_sub_lim_usd`, `facility_limit_amount`, `facility_currency` and `run_date`.

The 100-row sample repeats 38 scoped keys, has missing mastergroup IDs in 85 rows and lacks `rct_gid` in its selected columns. Include GID in the next extraction and preserve multiple borrowers. Resolve the empty history export before calculating changes. Do not sum repeated facility amounts or assume HSBC-share and whole-facility measures are interchangeable.

Jerome's proposed EUR 50 million investment-grade total-drawing baseline is separate from the still-open material-increase period/rule. Apply business rules after raw capture and measure validation.

**Recorded contact:** Shadi for the latest CLO query; no source owner is established by the workbook.

## 4 Counterparty Core supporting enrichment

The proposed table is `delta.prod_party_gda.counterparty_core`. The previous package instead specifies:

```text
hdfs://HDP46/apps/hive/warehouse/data-refinery/party/party/counterparty-core.delta
```

Verify the catalog object, schema, source/version, date semantics and relationship to that path. Do not assume equivalence between Starburst and a Spark Delta read.

| CLO input | Counterparty field used in the previous package | Use |
| --- | --- | --- |
| `obligor_cin` | `customer_relationship_cin_identifier` | CIN mapping route. |
| `rct_gid` | `customer_relationship_gid_identifier` | GID mapping route and cross-check. |
| `rct_mastergroup_id` | `mastergroup_esr_identifier` | Preserve a valid original ID or fill a unique missing/invalid ID. |
| CLO observation date | `run_date` | Mapping dates and an explicit as-of policy. |
| Borrower/source scope | `customer_relationship_lifecycle_status_code` | Validate eligible relationship states. |

The reviewed code normalises identifiers as text, retains leading zeros, restricts lookups to wanted CLO keys and selects the latest date per matching key inside a bounded window. It then applies lifecycle and mastergroup validity checks. It combines distinct CIN/GID candidates before deciding:

- Valid CLO ID: preserve it; record `source_conflict` if Counterparty disagrees, otherwise `original_preserved`.
- Missing/invalid CLO ID with one combined candidate: `matched_unique`.
- Multiple combined candidates: `ambiguous`; no arbitrary choice.
- No usable candidate: `unmatched`.

The prior settings were a 120-day Counterparty lookback, lifecycle values `A`, `ACTIVE`, `Y`, acceptance of blank status and invalid mastergroup value `NO MSG`. They require validation rather than automatic adoption. Latest-state selection precedes validity filtering, so older active mappings are not automatically resurrected.

Preserve original/final IDs, candidate sets/counts, per-route dates, match rule/status and conflict reasons. The prior code does not fill mastergroup names, and its published CSV omits much of the internal audit evidence. Retain that evidence in Bond Radar's derived dataset. Confirm any final name source separately.

The previous overall CLO extraction upper bound is not a per-row point-in-time mapping guarantee. Agree historical versus current-group membership. Validate row/key/amount preservation at the actual source/date/borrower grain and do not double-count a shared facility across groups. The complete enrichment requirements are in the [planning notes](Bond%20Radar%20Signal%20Planning%20Notes.md#counterparty-core-enrichment-of-clo-mastergroup-data).

## 5 SIG02 New facilities

**Original workbook reference:** Sheet1 A3:B3 and D3.

Sheet1 lists Facilities Limits GDA and this historical extraction location:

```text
hdfs://HDP46/apps/hive/warehouse/sp_uk_prod/prod_copy/apps/hive/warehouse/data-refinery/credit_and_lending/credit-and-lending/facilities-limits.delta
```

Verify its equivalence to the catalog table before use. The actual returned schema contains **`facility_creation_date`**, not the earlier note's `facility_creation_dt`.

| Field or term | Evidence and implication |
| --- | --- |
| `loan_approval_date` in CARM | Original concept discussed with Barry; not established as the actual source field. |
| `loan_approva_dt` | Suggested by Abhishek Dutta; earlier notes report zeros. The returned 100-row sample instead has blanks. Neither observation validates it as a usable event date. |
| `record_start_dt`, `record_end_dt`, `latest_record` | Available versioning evidence. Not confirmed signing/approval dates. |
| `facility_creation_dt` | Historical wording used in the workbook. Use the verified schema name `facility_creation_date` in future field selection. |
| `facility_creation_date` | Present but blank in the returned historical Thailand sample. Creation meaning and current coverage remain open. |
| `active_facility_ind` | Date-shaped values in all returned sample rows; clarify the field/export mapping before using it as a flag. |

Capture client and facility IDs, product codes, original/version dates, amounts and currencies before qualifying new events. Validate RCF/term-loan/bridge classifications and compare creation dates with known events. The original worksheet row mentions term loans and bridges; RCF event coverage requires confirmation.

**Recorded contacts:** Barry for business interpretation and Abhishek Dutta for asset/field guidance.

## 6 SIG03 Derivatives and pre hedging

No source is identified in the workbook or current samples. Investigate pricing-request or enquiry records with the derivatives sales/hedging team supporting DCM clients. Do not infer enquiries from executed trades alone.

Request client/entity IDs, enquiry ID, request/update dates, product/activity classification, financing purpose/context, status, and notional/currency/tenor where available. Obtain bond-linked, routine hedging and non-progressing examples. These are required information categories, not verified source columns. No named source-owner contact is established.

## 7 SIG04 Onboarding and KYC activity

**Original workbook reference:** Sheet1 A4:B4 and D4.

The KYC GDA investigation identified recurring records. Pankaj provided Hrithika's contact for the dictionary; Hrithika referred the event-definition question to Harry Wu in the Party team. Harry reported daily dataset refreshes and advised contacting the KYC source team. Refresh frequency alone does not establish a client event.

The supplied schema/sample supports investigation of `cin`, `related_case_id`, `related_case_status`, `review_purpose_code`, `review_purpose_desc`, `review_request_created_time_stamp`, `related_case_resolved_time`, `related_case_update_time` and `run_date`. Review purposes include New to Bank, Trigger, Periodic and Remediation. Explicit trigger-detail fields exist but are blank in the sample.

Preserve all relevant comparison categories and business/processing dates during capture. Confirm repeated-case grain, whether case history is complete, signatory-change and new-entity coverage, and which purposes matter to DCM. Old completed cases in a new extract are not new financing events.

## 8 SIG06 Utilisation and covenant evidence

**Original workbook reference:** Sheet1 A5:D5, labelled liquidity or covenant pressure.

### Utilisation candidates

| Source | Candidate measures and keys | Required validation |
| --- | --- | --- |
| CLO | `facility_drawn_amount`, `facility_limit_amount`, `facility_currency`, scoped facility keys and observation date; `ag_acc_bal_drawn_sub_lim_usd` as another drawn candidate. | Amount/approved-limit meaning, units, participation basis, dates, deduplication and borrower/group enrichment. |
| PVD OMNIA DRR | `drr_utils`, `drr_act_limit`, `drr_carm_limit`, `joi_relationship_id`, `joi_key`, `joi_date`, `etlmonth_drr`, `etlmonth`. | Denominator, currency, relationship grain, client mapping, current coverage and missing/negative measures. `exposure_usd` does not establish other fields' units. |
| DRR Facility Limits | `facility_id`, `cin`, `drr_mastergroup_id`, `approved_limit`, `utilisation`, currency and reporting/source-date fields. | Recent coverage, compatible amount definitions, zero denominators, currency alignment and identifier scope. |

The proposed rule is utilisation **greater than 70%**, subject to business validation. It is not proof of financial covenant pressure. Preserve raw records before applying it. Missing/zero denominators must not become zero utilisation.

### Explicit covenant candidate

Covenants GDA exposes `covenant_id`, `active_testing_id`, facility/client keys, types, statuses, actual/final values, threshold values/operators, testing/reporting dates and result/approval states. The returned sample is entirely non-financial reporting activity, with blank financial measures. Financial examples and approved-result semantics are needed before assessing breach or headroom.

The returned DDL points to an `HDP45` Delta location. Verify the physical source before adapting an HDP46 Spark workflow. Keep testing-instance grain separate from facility amounts.

### Historical join investigation and contacts

The workbook records CINs from Counterparty Core being used to find Facilities Limits facility IDs and then covenant records. Those facility IDs were not matched to DRR. Sado Nuuer suggested relationship/customer ID matches; prefix removal and legal-name matching also failed in that investigation. Mastergroup exploration did not establish a covenant bridge. These findings do not prove that no valid mapping exists.

The new Counterparty enrichment review establishes a method to investigate CLO mastergroup IDs only; it does not validate a covenant/DRR join. Use a matched client/date cohort and verify every identifier bridge. Do not strip prefixes merely to force a match.

Other recorded leads are Barry for the 70% utilisation discussion, Simonti for alternative asset suggestions and Sunil for SF Approval access. SF Approval had decryption-key errors in the earlier investigation; its current access and qualified location remain unresolved.

## 9 SIG07 Ratings advisory and category investigation

Sheet1 did not identify a ratings-advisory table. Later schema/sample review identifies **Facilities Limits and PVD OMNIA DRR as unverified candidates**; the user added **Application Ratings GDA** on 4 November:

- Facilities Limits: `limit_cat`, `limit_category_type`, `advised_ind`, `facility_grade_code`, `facility_grade_desc`, `sustainable_risk_rating_impact_proposed`, `sustainable_risk_rating_impact_approved`.
- PVD: `drr_crr`, `drr_fac_category`, `joi_facility_category`, with client/relationship keys and observation dates.
- Application Ratings: exact table `delta.prod_credit_and_lending_gda.application_ratings`.
  S&P/CRR/other content is user-reported, not a verified field list. The sample
  pack reads live metadata before constructing client/date/type sample queries.
  Preserve application/entity/facility scope, agency, scale, effective/approval
  dates and proposed/final status where present. Do not compare rating scales
  directly, infer advisory activity, or join application IDs to proposal serials
  without validating the bridge.

Category values include CAT-A/B/S forms; `advised_ind` contains 0/1 and `drr_crr` contains rating-like values plus sentinels. These observations do not establish advisory activity. Confirm the category definitions, rating scale and SIG07 business event with source owners and DCM stakeholders. Grade/rating-impact fields are blank in the returned Facilities Limits sample.

If ratings changes are intended, establish reliable historical observations and the scale. If advisory engagement is intended, confirm an explicit event field/category or investigate Ratings Advisory engagement records separately. No advisory-specific source or contact is yet confirmed.

## 10 Current collection outputs and open checks

Collect the identified assets separately within agreed bounds. Preserve data, schema, table definition, exact query/parameters, extraction time, actual source dates/coverage and outcome. Keep raw originals and derive refined datasets separately; do not apply EUR 50 million or 70% signal filters during raw capture.

Priorities are CLO history and required fields, Counterparty catalog/schema verification and enrichment tests, current Facilities Limits/KYC coverage, financial covenant examples and comparable utilisation measures. All source owners, dates, grain, access, history and daily-refresh capability still require source-specific confirmation. Daily updates are a business preference, not a conclusion from these samples.

### Related references

- [Internal signal requirements](Bond%20Radar%20Internal%20Signals.md)
- [Current planning notes](Bond%20Radar%20Signal%20Planning%20Notes.md)
- [Sample findings and limitations](analysis/internal_signal_samples/Findings.md)
- [Source to signal flowchart](diagrams/bond-radar-signal-flowchart.html)
- [Extraction and signal testing process](diagrams/bond-radar-extraction-process.html)
