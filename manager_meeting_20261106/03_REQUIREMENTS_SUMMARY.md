# Requirements summary and status

Sources:
- `attachments/requirements/Bond Radar Requirements.docx` (v1.1, 5 Nov 2026)
- the DCM meeting notes
- the comparison in `attachments/requirements/MEETING_ALIGNMENT_REVIEW.md`

## Business objective

Give DCM bankers and originators a consolidated view of clients with potentially relevant bond-issuance signals, so they can prioritise proactive conversations. A predictive model is a possible later direction, not yet established as feasible.

## Dashboard requirements

| ID | Requirement | Status | Comment |
|---|---|---|---|
| DASH01 | DCM prospecting dashboard bringing signals and client context together | ✅ Prototype built | Self-contained HTML in the LAF/HSBC style; 3 clients |
| DASH02 | Match external activity to HSBC clients and enrich with facility information | ⚠️ Partial | Internal enrichment done. External news exists in the LAF board but is not yet combined with Bond Radar |
| DASH03 | Include RCF information and upcoming debt maturity windows | ⚠️ Partial | RCF/drawing context included; **maturity windows not yet built** (data available) |
| DASH04 | Aim for daily data updates | ❌ Not yet | Manual Starburst extracts; needs a production feed |
| DASH05 | Dashboard as the primary channel (no email triggers) | ✅ | Design decision followed |
| DASH06 | Support prioritisation of clients | ⚠️ Partial | Clients ordered by test candidates; no agreed score yet |
| DASH07 | Resolve CME entitlement and MNPI before integrating call reports | ❌ Open | Blocks SIG05 and now SIG07 |

## Signal requirements (after the DCM meetings)

| ID | Signal | Agreed definition | Data source | Status |
|---|---|---|---|---|
| SIG01 | Material drawing | Any drawing over **EUR 50m** on any **Cat A** bank facility (RCF, term loan, bilateral); HSBC share and inferred total | CLO / LoanIQ + Facilities (Cat A) | Rule built; drawn field blank, FX/participation missing |
| SIG02 | New RCF / term loan / bridge | Dated by **internal credit approval date** | Facilities + Application Ratings | **Working:** 9 candidates |
| SIG03A | Swap roll on maturing debt | Roll of a swap tied to maturing debt (FX swaps first) | Derivatives trades | No source yet |
| SIG03B | New pre-hedge enquiry | Enquiry for a new pre-hedge swap before issuance | Not in markets systems; Bloomberg chat open | No source |
| SIG04 | KYC onboarding / refresh | New entity or signatory KYC refresh | Party KYC | Export empty |
| SIG05 | CME call-report keywords | "Acquisition", "drawing", "opportunistic", "liquidity" | CME | Excluded (MNPI) |
| SIG06 | Covenant breach / pressure | Leverage within **0.5x** of the covenant maximum (e.g. ≥ 2.5x vs 3.0x) | Financial covenant tests | Rule built; no data |
| SIG07 | Rating advisory | Requests recorded in **call reports** | CME | Blocked with SIG05 |
| — | Number of investor sales | **Dropped**: a weak signal because HSBC initiates the interaction | — | Removed |

## Data / access requirements (from the meetings)

| Need | Who | Status |
|---|---|---|
| Source and country for each credit signal; route to AI Markets | Roksana (CCM credit) | Partly explored. Credit data exists but the drawn amount, participation and covenant tests have not been located |
| LoanIQ as the RCF source | Credit / LoanIQ owners | CLO used as a proxy; the LoanIQ field is still needed |
| Completed DCM deals (2 years) and 2025 mandates | Simonti, Ayush | To review for back-testing |
| Dealogic historical issuance | DCM | Proposed for back-testing / modelling |
| GRADE historical credit time series | Luke Reader (GRA) | After the data need is clarified |
