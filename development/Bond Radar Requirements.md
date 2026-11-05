# Bond Radar Dashboard Requirements

Version 1.1 | 5 November 2026 | For stakeholder review

> **Version 1.1** adds the decisions from the follow-up DCM meetings: RCF definition, bridge date, pre-hedging, rating advisory, investor sales and covenant pressure. The changes are marked *(v1.1)*, and section 9 lists the decisions. The alignment of the development with these requirements is reviewed in `../docs/MEETING_ALIGNMENT_REVIEW.md`.

## 1 Project purpose and scope

Bond Radar will provide Debt Capital Markets (DCM) bankers and originators with a dashboard to identify clients that may issue bonds and prioritise proactive client conversations. It will bring together relevant internal signals, external market activity and client context so bankers can assess opportunities without manually assembling information across systems.

The immediate project purpose is to build the bankers’ dashboard. A predictive model is an additional direction to explore: historical data may help identify which clients are more likely to issue bonds. The meetings considered both approaches; they did not establish that a predictive model is feasible or select a final implementation approach.

### Business context

The existing Leveraged Acquisition Finance (LAF) process monitors market news, filings and sponsor activity, with much of the work performed manually by teams in India. Teams match external alerts to HSBC clients and then search for internal credit facility information and debt maturity context. The LAF prototype demonstrated how RCF information and Refinitiv news could be brought together. It provides a reference for Bond Radar, rather than a confirmed technical design.

### Intended users and outcomes

- DCM bankers and originators need a consolidated view of clients with potentially relevant bond issuance signals.
- Bankers need enough context to judge whether a signal warrants a client conversation.
- The longer-term analytical objective is a prioritised list of clients likely to issue bonds, subject to evidence that prediction adds value.

### Scope boundaries

The signal scope includes RCF activity, new credit facilities, derivatives and pre-hedging, KYC activity, CME call reports, covenant pressure and ratings advisory. External news, M&A activity, filings, sponsor activity and debt maturity windows provide supporting context.

Initial sample-data exploration focused on four signals: RCF, pre-hedge, covenant pressure and KYC. This is a starting point for investigation, not a decision to exclude the other signals.

Investor strategy and order book analysis were mentioned as a separate use case. The notes also use “Bond Trader”; this document uses “Bond Radar” for the DCM project.

## 2 Internal signal catalogue

These are candidate indicators of possible financing activity. An individual signal does not establish that a bond issuance will occur. Sources and trigger definitions require validation unless explicitly identified below.

| ID | Signal | Business relevance and qualification |
| --- | --- | --- |
| SIG01 | Material drawing on a bank facility | May indicate a future refinancing need. *(v1.1)* Not limited to facilities labelled RCF: any drawing on any **Cat A** bank facility (RCF, term loan, bilateral or other direct lending) above **EUR 50 million** is material. See section 3. |
| SIG02 | New RCF, term loan or bridge facility | Jerome identified new facilities as potential precursors to refinancing in the bond market. *(v1.1)* The event date is the **internal credit approval date** from the credit team, which precedes signing. |
| SIG03 | Derivatives and pre-hedging | A client asking HSBC for pre-hedge pricing or swap pricing may indicate preparation for financing. *(v1.1)* Two independent signals: **SIG03A**, roll of an existing swap tied to maturing debt; **SIG03B**, enquiry for a new pre-hedge swap ahead of an issuance. FX swaps in particular indicate pre-hedging. The source is open: the signal does not exist in markets systems, and Bloomberg chat was raised as an option. |
| SIG04 | Entity onboarding and KYC | Onboarding a new entity or refreshing KYC for signatories may precede a bond transaction. Determine which events are useful rather than routine administration. |
| SIG05 | CME call report content | Reports posted by GRBs may contain relevant language such as “acquisition”, “drawing”, “opportunistic” or “liquidity”. Interpretation requires context and appropriate access. |
| SIG06 | Covenant breach or covenant pressure | May indicate a financing need, including a possible hybrid transaction. *(v1.1)* Pressure exists when leverage (e.g. net debt / EBITDA) is **within half a turn of the covenant maximum**: 2.5x against 3x, 3.5x against 4x, 1.5x against 2x. The originator should be alerted. Source still to be identified. |
| SIG07 | Ratings advisory activity | Raised in Simonti’s data-source request. *(v1.1)* The source is **call notes / call reports**: requests are rare, are recorded by senior bankers in call reports, and will not be automated in AI Markets. Linked to SIG05 (CME). |

*(v1.1)* "Number of investor sales" has been **dropped**. DCM considers it weak because HSBC initiates the investor interaction, and Jerome agreed.

SIG07 source investigation update, 4 November 2026 (superseded for SIG07 by v1.1; the table is now used as CRR credit context): add `delta.prod_credit_and_lending_gda.application_ratings` alongside Facilities Limits and PVD. User-reported S&P/CRR/other rating content requires schema, client-key, scale/date and advisory-event validation. See the [sample SQL guide](pvd_client_cohort_lab/sql_templates/sig07_application_ratings_20261104/README.md).

### External and client context

The dashboard should connect relevant market news, M&A activity, filings and sponsor activity to HSBC clients, then enrich the result with available RCF, credit facility and debt maturity information. The matching needs to recognise the relevant legal entity and its relationship to the client group.

Refinitiv news was demonstrated in the LAF prototype. Dealogic was proposed for historical bond issuance data, including transactions where HSBC did not win the mandate. Production feed selection and coverage remain to be agreed.

## 3 RCF drawing rules

*(v1.1)* These rules apply to **any Cat A bank facility**, not only RCFs. When a company needs funding it usually draws first on its bank facility, most often the RCF. Some large clients have no RCF and draw on a bilateral facility or term loan instead. A drawing above EUR 50 million on any Cat A facility is the signal.

### Amounts to distinguish

Jerome described two amounts to consider: HSBC’s own share of an RCF drawing and the inferred or assumed drawing across the full facility. The notes provide a numerical baseline for the total drawing only; they do not specify a separate numerical threshold for HSBC’s share.

Where a proportional drawing assumption is valid:

**Inferred total RCF drawing = HSBC drawn amount / HSBC participation share**

For example, an HSBC drawing of EUR 10 million at a 10% participation share implies a total facility drawing of EUR 100 million. The participation share and proportionality assumption must be checked before this inference is used.

### Materiality baseline

For investment-grade corporates, Jerome proposed EUR 50 million in total drawing as the minimum baseline for a relevant DCM signal. Drawings below that amount were considered insignificant for this purpose. A small local subsidiary drawing of EUR 5–10 million was given as an example of noise to filter out.

Parent and subsidiary activity can both be relevant. Entity level alone should not determine exclusion: amount, geography and financing context matter. The EUR 50 million baseline was discussed specifically for investment-grade corporates; applicability to other segments requires agreement.

### Definitions requiring confirmation

- ~~Does the baseline apply to outstanding drawn balance, a new drawing, or the increase over a defined period?~~ *(v1.1)* Answered: it applies to the **drawing**, i.e. the increase in drawn amount, of more than EUR 50 million.
- ~~Which facilities qualify?~~ *(v1.1)* Answered: any Cat A bank facility (RCF, term loan, bilateral).
- Over what comparison period is a drawing measured?
- What facility and client aggregation rules should apply?
- How should non-EUR amounts be converted, and which FX date should be used?
- What should happen when participation data is missing or proportional drawing cannot be assumed?

### Proposed display treatment

Show HSBC’s drawn amount and participation share alongside the observed or inferred total, with an explicit indication when the total is inferred. This makes the materiality assessment understandable to the banker. This display treatment is a proposed implementation detail for review.

## 4 Dashboard requirements and banker workflow

### Requirements captured from the discussions

| ID | Requirement | Basis |
| --- | --- | --- |
| DASH01 | Provide a DCM prospecting dashboard that brings relevant signals and client context together. | Dashboard format preferred; a prospecting board was one of Simonti’s two approaches. |
| DASH02 | Match external activity to HSBC clients and enrich it with available credit facility information. | Manual entity matching and enrichment described in the LAF process. |
| DASH03 | Include relevant RCF information and upcoming debt maturity windows. | Explicit context required in the proposed automated workflow. |
| DASH04 | Aim for daily data updates. | Jerome preferred daily to weekly updates because timeliness matters. Actual source capability needs confirmation. |
| DASH05 | Use the dashboard as the primary channel for reviewing signals. | The group preferred a dashboard over email triggers to avoid information overload. |
| DASH06 | Support prioritisation of clients for proactive banker engagement. | Core business objective; predictive ranking remains subject to feasibility. |
| DASH07 | Resolve CME entitlement and material non-public information constraints before integrating its content. | CME access and MNPI concerns were explicitly raised. |

### Proposed banker workflow

1. Open the prospecting board and review clients with recent relevant signals.
2. Narrow the list by client, geography, signal category or date, if these filters are adopted.
3. Open a client view to inspect supporting signals, RCF context, maturity information and relevant external activity.
4. Assess the evidence and decide whether to initiate a client conversation.

### Proposed minimum information to display

Show the client and legal entity, parent group where known, signal category, event date, source and a short explanation of relevance. Where available, include facility amounts, currency, HSBC participation, total drawing and maturity dates. Show data freshness and distinguish missing data from the absence of a signal.

Filters, client drill-down, evidence links, data freshness labels and the exact screen layout are proposed design details. They require banker review. The notes do not define a final scoring method, prediction horizon, export requirement or automated distribution mechanism. AI Markets integration was discussed, but the delivery interface remains open.

## 5 Data sources and access requirements

For each dataset, identify the source system, country coverage, owner, access route, refresh frequency, historical depth, entity identifiers and permitted use. Roxana indicated that relevant credit data exists; usable coverage and access still need investigation.

| Source or dataset | Intended use | Position recorded in the notes |
| --- | --- | --- |
| LoanIQ | RCF drawings and facility context | Identified as the RCF source. Fields, country coverage, history and extraction route need validation. |
| CIP data platform on HDP46 | Explore CALM, counterparty, KYC and CLO datasets | Named as an existing platform to investigate. Exact tables, useful fields and access remain to be established. |
| GRADE | Historical time series credit data | Described as a separate risk platform. Luke Reader in GRA was named as the access contact after the data need is clarified. |
| CME | GRB call reports and contextual keywords | Integration is more complex because of MNPI and entitlement constraints. |
| DCM mandate and completed deals files | Historical HSBC deal examples and outcomes | Ayush was suggested as a contact for 2025 mandates. Simonti confirmed resending a completed deals file for the last two years. |
| Dealogic | Historical public bond issuances, including deals HSBC did not win | Proposed to broaden the historical dataset. An email about column labels was referenced. |
| Refinitiv | External news context | Demonstrated in the LAF prototype; Bond Radar production use remains to be confirmed. |
| Other signal feeds | Pre-hedge enquiries, new facilities, covenant pressure and ratings advisory | Authoritative feeds and qualifying fields need to be mapped. |

### Data integration dependencies

Confirm how records from each source link to clients, legal entities, parent groups, facilities and deals. Establish which dates represent the underlying event and which represent when information became available. Historical analysis needs data as it was known at the time, rather than only the latest record.

The route for surfacing data to AI Markets remains to be determined. Bloomberg was considered unnecessary for the historical modelling exploration discussed by Simonti; that does not establish a broader decision on future dashboard feeds.

## 6 Predictive model exploration

### Objective and approach

Assess whether historical client and credit information can help predict future bond issuance and improve the prioritised client list. Simonti proposed exploring this alongside the straightforward prospecting-board approach, using the ALM/LAF modelling work associated with Alberto as a reference.

1. Obtain historical DCM mandates and completed deals. The notes mention 2025 as an example and the last two years as another proposed starting scope; agree the actual period.
2. Identify clients and bond issuances, supplementing HSBC outcomes with Dealogic transactions where HSBC did not win the mandate.
3. Reconstruct each client’s credit and signal history before the relevant event, including RCF, pre-hedge, covenant pressure, KYC, liquidity and counterparty information where available.
4. Examine whether consistent patterns appear before issuance, beginning with selected client examples.
5. Test whether a model can use those patterns to prioritise the current client list.

### Historical data requirement

Current snapshots alone are insufficient. Simonti suggested looking back through the months before a deal, potentially up to one year, and mentioned five years as a reference from GRA modelling. The available history and appropriate lookback period must be agreed. GRADE was identified as a route to historical credit time series.

### Proposed validation requirements

The following are analytical recommendations for review, rather than recorded meeting decisions:

- Define the target event and prediction horizon. Bond issuance, mandate award and HSBC mandate win are different outcomes; their dates should not be used interchangeably.
- Include appropriate client periods without an issuance so the study can assess predictive value beyond patterns among completed deals.
- Use only information available before the prediction date, and test on later periods than those used for training.
- Compare model results with a simple signal-based prioritisation baseline and assess whether the highest-priority clients are useful to bankers.

### Decision on the analytical approach

Use data availability, historical coverage, observed signal patterns, validation results and banker usefulness to decide whether predictive modelling merits further development. A probability score should not be presented as an established capability before that evidence exists.

## 7 Actions and decisions to resolve

### Follow-up actions recorded in the notes

| Action | Person or contact identified | Dependency or qualification |
| --- | --- | --- |
| Consolidate requirements, extract samples and organise data by signal. | Shadi | Begin with selected client examples and retain the historical dimension. |
| Review the completed deals file and confirm the historical sample. | Shadi with Simonti; Ayush for DCM mandates | Simonti said the two-year file had been resent; receipt and coverage need checking. |
| Clarify credit data sources, countries and the route to AI Markets. | Roxana with the project team | Source discovery is needed before committing to integration. |
| Discuss comparable loan and term loan prediction work. | Sergey | Simonti recommended this as the first modelling discussion because of his GRA background. |
| Review the assembled data and agree the historical data request. | Shadi and Simonti | Arrange a dedicated working session before approaching Luke. |
| Explore GRADE access for the agreed time series requirements. | Luke Reader in GRA | Follow clarification of the required data. |
| Include Tim and Rachel in a follow-up discussion. | Meeting organiser not specified | The notes refer to August 31st without a confirmed year or current meeting status. |

### Decisions required for delivery planning

- Confirm the initial client population, geographies, investment-grade coverage and banker users.
- Agree which signals can be delivered first, their trigger definitions and the RCF rules in section 3.
- Validate source access, country coverage, daily refresh capability and historical depth.
- Resolve CME access and MNPI handling, and confirm permitted use of the other datasets.
- Review the proposed dashboard fields and workflow, including how client priority should be determined.
- Decide whether predictive modelling will proceed alongside or after dashboard delivery, based on the exploration results.
- Set current owners, milestones and dates. The meeting references to a three-to-four-week exploration and delivery “next year” lack meeting dates that would anchor a current schedule.

### Proposed criteria for reviewing the first dashboard

Bankers can review a consolidated client list, understand why each client appears and inspect the supporting information. Available RCF data is assessed using the agreed rules, with observed and inferred amounts clearly distinguished. Daily updates are demonstrated for the sources committed to that cadence. Restricted information is visible only to entitled users, and the limits of source coverage are apparent.

These are proposed review criteria. Performance targets, minimum data coverage and any predictive accuracy targets remain to be agreed.

## 8 Meeting references and terminology

The source record is `Jerome signals requirments.txt`. Repeated meeting summaries have been consolidated by topic. The local meeting links retained in that record are:

- Jerome and DCM market signals discussion: https://zoom.localhost/index-5.1.11504.html#/aic
- Simonti’s proposed predictive approach: https://zoom.localhost/index-5.1.11775.html#/aic
- Later discussion of the two approaches and historical data process: https://zoom.localhost/index-5.1.11818.html#/aic
- Email reference: “FW: Column Labels for info send to Dealogic Simonti”.

The DCM market signals meeting is titled “AI DCM / Use Case 6 - Market Signals”. The listed participants are Pankaj Pathak, Jerome Pierre Zecchini, Simonti Basu, Roksana Martirosjana and Shadi Nashed. “Roxana” and “Roksana” appear to refer to the same contact; the spelling should be confirmed.

DCM means Debt Capital Markets; RCF means Revolving Credit Facility; KYC means Know Your Customer; ML means machine learning; MNPI means material non-public information. GRA is the risk modelling team referenced in the notes. CALM, CLO, CME, CIP and GRB are retained as source-system or role labels pending confirmation of their full names and ownership.

## 9 Decisions from the follow-up DCM meetings (v1.1)

| Topic | Decision | Implication |
| --- | --- | --- |
| RCF definition | Any drawing on any Cat A bank facility (RCF, term loan, bilateral, direct lending) above EUR 50m is material. Two amounts: HSBC share, and the inferred total (÷ participation). Parent and subsidiary both count; small local drawings are noise. | Requires drawn amounts by facility (LoanIQ), Cat A category, HSBC participation share and an agreed FX source |
| Bridge date | Use the internal credit approval date from the credit team; it is earlier than signing and straightforward to obtain. | Credit approval dates per facility/application |
| Pre-hedging | FX swaps indicate pre-hedging. Two independent signals: roll of a swap tied to maturing debt; enquiry for a new pre-hedge swap. Bloomberg chatrooms raised as a possible source (open). | Derivatives trade data; an enquiry source still to be built |
| Rating advisory | Source is call notes / call reports from senior banker–client interactions; rare and not automated. | Depends on CME access (as SIG05) |
| Investor sales | Dropped as a weak signal (HSBC initiates the interaction). | No action |
| Covenant pressure | Leverage within half a turn (0.5x) of the covenant maximum, e.g. ≥ 2.5x against 3x. | Requires covenant metric, actual value, maximum and test date |

