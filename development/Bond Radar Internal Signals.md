# Bond Radar Internal Signal Requirements

**5 November 2026 meeting decisions (development-2).** These supersede the earlier statements on SIG01, SIG02, SIG03, SIG06 and SIG07 below. Full comparison: `../docs/MEETING_ALIGNMENT_REVIEW.md`.

| Signal | Decision |
| --- | --- |
| SIG01 | Any drawing over EUR 50m on any **Cat A** bank facility (RCF, term loan, bilateral). HSBC share and the inferred total (÷ participation) are both considered. Facilities `limit_cat` is the Cat A filter, no longer a SIG07 candidate. |
| SIG02 | Event date = internal **credit approval date**, not signing. |
| SIG03 | Split into **SIG03A** (roll of a swap tied to maturing debt) and **SIG03B** (enquiry for a new pre-hedge swap). FX swaps first. |
| SIG06 | Covenant pressure = leverage **within half a turn** of the covenant maximum. Utilisation > 70% is context only (`CTX_UTIL`). |
| SIG07 | Rating advisory is sourced from **call reports** (CME, not integrated). Application Ratings CRR and Facilities/PVD category fields are credit context (`CTX_CREDIT`). |
| Investor sales | The number of investor sales is dropped. |


**Current SIG07 decision, 4 November 2026:** add **CRR only** from Application
Ratings in this stage. Display final_crr with its scale, date and application/entity
scope; retain previous/proposed/approved/manual/overridden states separately.
Missing CRR remains unknown and no external agency rating is added by this step.
Advisory interpretation and trigger conditions remain unconfirmed. See the
[CRR-only workflow](pvd_client_cohort_lab/sql_templates/sig07_crr_20261104/README.md).

**4 November 2026 SIG07 addition:** investigate
`delta.prod_credit_and_lending_gda.application_ratings` alongside Facilities Limits
and PVD. The user reports S&P, CRR and other rating types. Capture all relevant
types, providers, statuses and source/effective dates for the three target groups;
verify the schema and identifier roles before adding runtime joins. Credit rating
data does not by itself establish advisory engagement. See the
[sample SQL guide](pvd_client_cohort_lab/sql_templates/sig07_application_ratings_20261104/README.md).

**3 November 2026 development update:** SIG01 treats missing/blank drawn amounts
as zero with imputation flags; invalid numbers and absent comparison observations
remain unavailable. SIG06 retains its missing-data rules. Counterparty access is
corrected to `delta.prod_party_gda.counterparty_core`; live schema/mapping settings
still need validation. Facilities `limit_cat` is a SIG07 advisory candidate pending
code definitions. Use current snapshots/effective versions and a second CLO
snapshot for comparison. See the [current workflow](pvd_client_cohort_lab/CURRENT_WORKFLOW.md).

Version 1.1 | 29 October 2026 | For stakeholder review

## 1 Purpose and current scope

Bond Radar will give Debt Capital Markets (DCM) bankers a consolidated view of internal activity that may indicate a future bond issuance opportunity. The current stage is to collect available candidate data from the discussed sources, preserve the evidence and refine source choices and signal definitions through testing.

Begin with CLO, while progressing the other identified sources as access and extraction capability permit. Extract within agreed date, country and client bounds, retaining relevant candidate attributes and available history. A shared client cohort is used later to test interpretations and joins; it need not restrict the whole raw extraction population.

The current scope covers SIG01, SIG02, SIG03, SIG04, SIG06 and SIG07. SIG05 remains excluded. External feeds and predictive modelling are outside this phase. Candidate source mappings and thresholds below require validation; no individual signal establishes that a bond issuance will occur.

The [planning notes](Bond%20Radar%20Signal%20Planning%20Notes.md) record the current planning decisions. Historical meeting statements and sample findings remain evidence, with their original scope and limitations.

## 2 Internal signal catalogue

| ID | Signal | Intended assessment | Current source position |
| --- | --- | --- | --- |
| SIG01 | Material drawing on a Cat A bank facility | Compare deduplicated facility observations over time; a drawing above EUR 50m on any Cat A facility (RCF, term, bilateral) is material (5 Nov decision). | CLO is the primary extraction candidate. Counterparty Core will support mastergroup enrichment once its table and mappings are verified. LoanIQ was mentioned in the meetings; its relationship to CLO remains unconfirmed. |
| SIG02 | New RCF, term loan or bridge facility | Identify new financing facilities that may later be refinanced through bonds, dated by the internal credit approval date (5 Nov decision). | Facilities Limits GDA, with the Application Ratings `approval_dt` linked by `credit_proposal_serial_no`. Facilities `loan_approva_dt` is a `0` placeholder; `facility_creation_date` is a candidate only. |
| SIG03A / SIG03B | Derivatives and pre-hedging activity | Two independent signals (5 Nov decision): SIG03A, roll of an existing swap tied to maturing debt; SIG03B, enquiry for a new pre-hedge swap. | No source identified. SIG03A needs derivatives trade data (FX swaps first); SIG03B has no markets-system source (Bloomberg chat raised; open). |
| SIG04 | Entity onboarding and KYC activity | Identify relevant client cases, distinguishing routine reviews and dataset refreshes from business events. | Party KYC GDA. Review-purpose and case/date fields are available; signatory-change and new-entity coverage remain unconfirmed. |
| SIG06 | Financial covenant breach or pressure | Pressure = leverage within half a turn of the covenant maximum (5 Nov decision). Utilisation above 70% is context only (`CTX_UTIL`). | CLO and PVD OMNIA DRR are utilisation candidates; DRR Facility Limits is an alternative. Covenants GDA is a candidate for explicit financial covenant evidence, which the current non-financial sample does not demonstrate. |
| SIG07 | Ratings advisory request | Rating advisory requests recorded by senior bankers in call reports (5 Nov decision). | CME call reports, not integrated (MNPI/entitlements, as SIG05). Facilities, PVD and Application Ratings fields are credit context (`CTX_CREDIT`). |

New facilities and ratings advisory remain in the collection plan alongside the original RCF, pre-hedge, covenant and KYC investigation. Final definitions and implementation priorities remain open.

## 3 RCF drawing and utilisation rules

### SIG01 drawing materiality

Keep HSBC's drawn amount separate from the total drawing across the facility. Where a proportional drawing assumption is valid:

**Inferred total RCF drawing = HSBC drawn amount / HSBC participation share**

An HSBC drawing of EUR 10 million at a 10% participation share implies EUR 100 million across the full facility. Validate the share and proportionality assumption before using that inference.

Jerome proposed EUR 50 million in total drawing as the minimum relevant baseline for investment-grade corporates. This is separate from the definition of a material increase over time, which remains to be agreed. Parent and subsidiary activity can both be relevant. Applicability to other client segments also requires agreement.

Confirm whether the baseline applies to outstanding drawn balance, a new drawing or a period increase; the change amount/percentage and comparison period; facility/entity/group aggregation; non-EUR conversion and FX date; and handling of missing participation information. Show observed and inferred amounts separately.

### SIG06 utilisation

The proposed assessment is:

**Utilisation percentage = drawn or utilised amount / validated approved limit × 100**

Investigate values **greater than 70%** as a candidate high-utilisation indicator. Validate the threshold and denominator with the business. The numerator and denominator must cover the same currency, date, entity/facility grain and participation basis. Do not divide a USD measure by a local-currency limit. Missing or zero denominators produce unavailable results, not zero utilisation.

CLO candidate fields include `facility_drawn_amount` and `facility_limit_amount`; `ag_acc_bal_drawn_sub_lim_usd` is another drawn-measure candidate whose definition and denominator must be confirmed. PVD candidates are `drr_utils`, `drr_act_limit` and `drr_carm_limit`, with their grain and units unverified. DRR offers `approved_limit` and `utilisation`, subject to compatible currencies, dates and definitions.

High utilisation alone does not establish a covenant breach. Financial covenant assessment needs the applicable actual/final value, threshold, comparison operator, test date and meaningful approval/result state. The returned covenant sample is non-financial reporting activity; Overdue is not proof of financial breach.

The original meetings identified covenant pressure as a possible financing need, including a potential hybrid transaction. That relevance remains a business hypothesis to test against actual financial covenant evidence.

## 4 Data collection and refinement requirements

1. Inventory candidate sources and confirm source locations, schema, available history, coverage and extraction bounds.
2. Extract each source separately and retain its relevant candidate attributes and historical states. Apply agreed extraction bounds; defer EUR 50 million, 70% and other business trigger filters to refinement.
3. Preserve versioned raw data with schema, table definition, exact query/parameters, extraction timestamp, observed dates, source coverage and outcome. Record failed or empty extracts without silently replacing usable data.
4. Profile dates, grain, missingness, sentinel values, duplicates, currencies and identifier scope. Do not assume a global latest date contains the whole population.
5. Derive refined and enriched datasets separately. Test joins on matched clients/dates and measure multiplicity before enrichment. Preserve original identifiers and multiple borrower/testing-instance relationships.
6. Assemble candidate signal evidence, review examples with bankers and source owners, then agree dashboard rules. Missing history, fields or mappings feed back into another extraction.

PVD sector aggregate is not part of the active collection plan. GRADE remains a possible historical credit-data route from the meetings if an identified history gap requires it; no GRADE dataset or access has been confirmed for this phase.

For every source, confirm owner, access, country/client coverage, refresh frequency, historical depth, record grain, date meaning and permitted use. Daily updates remain the business preference; actual capability must be established source by source.

Common evidence fields to investigate are client/entity identifiers and names, parent group, signal/event type and explanation, business-event and observation dates, source record/reference and refresh time. Retain relevant facility identifiers, maturity, amounts and currency; previous values and comparison dates for change-based signals; and observed/inferred status, assumptions and missing-data indicators. These are output requirements to map to actual source fields.

## 5 Counterparty Core enrichment of CLO

Counterparty Core is a supporting identity source for the CLO-backed SIG01 and SIG06 assessments. The proposed table `delta.prod_party_gda.counterparty_core` is unconfirmed. The reviewed historical package uses a direct Delta path; equivalence with the proposed catalog table must be verified.

| CLO field | Counterparty field from the reviewed package | Purpose |
| --- | --- | --- |
| `obligor_cin` | `customer_relationship_cin_identifier` | CIN mapping route. |
| `rct_gid` | `customer_relationship_gid_identifier` | GID mapping route and cross-check. |
| `rct_mastergroup_id` | `mastergroup_esr_identifier` | Preserve a valid CLO ID or fill an unambiguous missing/invalid ID. |
| `run_date` | `run_date` | Maintain source dates and a validated mapping as-of policy. |
| Source and borrower context | `customer_relationship_lifecycle_status_code` | Validate relationship eligibility and identifier scope. |

The initial CLO raw sample lacks `rct_gid`; it must be included in the planned capture. Retain original IDs and names. The previous enrichment code fills mastergroup IDs only and does not rebuild mastergroup names.

Normalise identifiers as text while retaining original values and leading zeros. Build unique per-key lookups within a validated date window, selecting the latest observed key state before lifecycle/mastergroup validity filtering. Combine distinct candidates from both CIN and GID before making a decision:

- Preserve a valid original CLO ID. Flag Counterparty disagreement as `source_conflict`.
- If the original is missing/invalid, fill only when the combined set has exactly one ID: `matched_unique`.
- Leave multiple candidates `ambiguous` and no candidates `unmatched`; do not select an arbitrary maximum or first row.

Validate previous lifecycle, lookback and sentinel settings rather than adopting them automatically. For historical analysis, distinguish point-in-time membership from a current-group restatement; the previous overall extraction-date bound is not a per-observation guarantee.

Preserve candidate lists/counts, both route dates, original/final IDs, match rule/status and conflict reasons. Validate row counts, keys and financial amounts at the actual observation/borrower grain before and after enrichment. Multiple borrowers on a facility must not cause the full facility amount to be counted in several groups without an agreed allocation rule.

The full matching decisions, previous configuration and audit requirements are in the [Counterparty enrichment section of the planning notes](Bond%20Radar%20Signal%20Planning%20Notes.md#counterparty-core-enrichment-of-clo-mastergroup-data). Only the feature is being adapted; the previous production solution is not being adopted.

## 6 Open source and business definitions

**SIG02:** validate the live `facility_creation_date` field against known signing/approval events and confirm RCF/term-loan/bridge product codes. The old `facility_creation_dt` label is a historical note, not the current verified column name.

**SIG03:** obtain client/entity IDs, enquiry ID, request/update dates, activity type, financing context, status and notional/currency/tenor where available. Validate enquiry coverage as well as executed trades, using bond-linked, routine and non-progressing examples.

**SIG04:** confirm New to Bank, Trigger, Periodic and Remediation purposes and case timestamps. A Trigger case alone is not a financing signal. Establish signatory/onboarding coverage and repeated-case handling.

**SIG07:** define the business event before selecting fields. Investigate `limit_cat`, `limit_category_type`, `advised_ind`, grade/rating-impact fields, `drr_crr`, `drr_fac_category` and `joi_facility_category`. Obtain category and rating-scale definitions. If these do not identify advisory activity, investigate Ratings Advisory enquiry/engagement records separately.

Also inspect Application Ratings GDA for its actual application/client keys,
rating types/providers (including user-reported S&P/CRR), values/scales, effective
and approval dates, current/proposed/final states and row/version grain. Do not
invent column names or collapse different rating types into a single rating.

## 7 Dashboard outcome and immediate actions

The dashboard remains the primary review channel, with daily updates preferred where supported. Bankers should be able to review clients with relevant signals, understand what occurred and why it may matter, inspect supporting facility/event evidence and assess whether a client conversation is warranted. Show relevant dates, source references, amounts/currency where applicable, freshness and qualifications. Client, signal and geography filters and a client detail view remain proposed design features. Scoring and AI Markets integration remain open.

Start with bounded CLO capture and resolve the empty history output. Confirm Counterparty Core and its mappings while progressing Facilities Limits, KYC, Covenants, DRR and PVD extracts independently. Use a shared client cohort for later interpretation and join checks, then review with Simonti, Jerome and the relevant source owners.

Contacts recorded in the earlier discussions remain leads rather than newly assigned commitments: Shadi for data organisation, Roxana for credit-source guidance, Sergey for relevant modelling experience, and Luke Reader for a defined GRADE history request. Owners, milestones and current access still need confirmation.

## 8 References and terminology

- [Current planning notes and appendix](Bond%20Radar%20Signal%20Planning%20Notes.md)
- [Data source reference](Bond%20Radar%20Internal%20Signal%20Data%20Sources.md)
- [Sample review findings](analysis/internal_signal_samples/Findings.md)
- [Source to signal flowchart](diagrams/bond-radar-signal-flowchart.html)
- [Extraction and signal testing process](diagrams/bond-radar-extraction-process.html)
- [Broader dashboard requirements](Bond%20Radar%20Requirements.md) and [original meeting record](Jerome%20signals%20requirments.txt)

RCF means Revolving Credit Facility; KYC means Know Your Customer. Other platform and dataset labels are retained from the supplied material; their ownership and business definitions require source confirmation.
