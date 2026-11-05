# Next steps and roadmap

All dates are indicative and depend on the decisions in the meeting and on data access.

## Immediately after the meeting (next 2 weeks)

| # | Action | Owner | Depends on |
|---|---|---|---|
| 1 | Share the meeting outcome and the alignment review with Simonti and Jerome; confirm the pilot client list and pilot bankers | Shadi | D1, D2 |
| 2 | Send the data requests to the credit team, sponsored by the manager:<br>- **LoanIQ drawn amount by facility** (current + prior)<br>- **HSBC participation share**<br>- **FX rate source/date**<br>- **financial covenant tests** (net debt/EBITDA actual vs maximum) | Shadi → Roksana / credit | D3 |
| 3 | Ask markets data owners for **derivatives trades** (FX swaps first) for SIG03A | Shadi / manager | D3 |
| 4 | Credit team to confirm SIG02: is `application_ratings.approval_dt` the approval of the new facility? Which product codes are RCF / term / bridge? | Credit team | Owner-review file |
| 5 | Validate the SoftBank example (same facility ID across Facilities and CLO; prior drawing) | Shadi + credit | — |
| 6 | Open the **CME call-report governance** conversation (MNPI, entitlements) | Manager | D4 |
| 7 | Obtain the **completed DCM deals file** (2 years) and the 2025 mandates for back-testing | Simonti / Ayush | — |
| 8 | Agree the hosting / production route with the AI Markets team | Manager / Shadi | D5 |

## Phase 1 — Pilot MVP (indicative 6–8 weeks after data access)

| Workstream | Deliverable |
|---|---|
| Client scope | Reviewed entity mapping for 20–30 IG Cat A clients (shared with LAF) |
| Signals | SIG02 (approval date) live; SIG01 once LoanIQ data arrives; SIG03A if the trade source is found |
| Context | Debt-maturity windows (< 12m, 12–24m); LAF news feed (Refinitiv); utilisation and CRR context |
| Board | Pilot version of the dashboard with a client search, a "contacted / not relevant" feedback field and a weekly refresh |
| Back-test | Report: share of past issuances with a signal 3–12 months before the deal |
| Governance | Definitions signed off for SIG01/SIG02; CME decision path agreed |

**Exit review:** compare the results with the criteria in `06_PRACTICALITY_ASSESSMENT.md`: value, use, data and governance.

## Phase 2 — Scale (next quarter, if Phase 1 passes)

- Automated extracts and a daily refresh for the signals that have feeds
- Expansion to the wider IG client list
- Add SIG06 (covenant pressure) and SIG04 (KYC) when their sources are confirmed
- SIG07/SIG05 via CME if governance allows
- Combine the LAF and DCM views on one platform
- Simple transparent priority score

## Phase 3 — Predictive exploration (optional)

- Build on the back-test: use historical signals before past issuances, plus GRADE time series (Luke Reader, GRA) and Sergey's loan-prediction experience
- Only proceed if Phase 1 and 2 show the signals carry information
- A score would require model governance

## Technical next steps already prepared

- The engine already holds the agreed rules. Each needs only a data feed and an owner sign-off (switching its `definitions_verified` flag on).
- `development/NEXT_STEPS.md` lists the exact data requests and the rebuild commands.
- Owner-review files (`attachments/reports/owner_review/`) contain the 44 specific questions for source owners.
- Still to build in code:
  - debt-maturity windows on the board
  - a feedback field
  - a client search over a larger client list
  - a scheduled refresh once feeds exist
