# Bond Radar — one-page briefing

**Status at 5 November 2026 · development on three target clients (Vodafone MG001356, Siemens Energy MG102229, SoftBank MG101624)**

## Why

DCM bankers want to see, early, which clients may need bond financing, using **internal HSBC signals** that are invisible from the market: facility drawings, new facilities, hedging activity, KYC, covenants and rating advisory. Today this context is assembled by hand, if at all. The agreed output is a **dashboard rather than email triggers**, in the style of the existing LAF board.

## What has been built

- **A working signal engine.** It takes manual Starburst extracts from six internal sources, resolves them to client groups and produces auditable evidence. Every record traces back to its source row.
- **Signal rules that match the DCM meeting decisions.** These were agreed with Jerome, Simonti and the team (rule version *development-2*):
  - any Cat A drawing over EUR 50m
  - new facilities dated by credit approval
  - two pre-hedging signals
  - covenant pressure within half a turn of the maximum
  - rating advisory from call reports
  - investor sales dropped
- **A self-contained dashboard** in HSBC style: KPIs, client signal matrix, drill-downs, charts, evidence explorer, owner-review queue, definitions and sources.
- **Reports:** an overview workbook, eight signal/context workbooks, definitions, findings and requirements v1.1. 87 automated tests pass.

## What the data shows

| | Result |
|---|---|
| Records | 631 development records: 71 signal evidence, 560 context |
| Live signal | **SIG02:** 9 facilities approved by credit in the last 90 days (Vodafone 7, Siemens Energy 1, SoftBank 1) |
| SIG01 Cat A drawings | 8 comparisons, none assessable as material: the drawn-amount field is blank in CLO; FX and participation are not supplied. SoftBank has USD 179.7m drawn on a term loan but no prior snapshot |
| No data yet | SIG03A swap roll, SIG03B pre-hedge enquiry, SIG04 KYC (empty export), SIG06 covenants, SIG07 call reports (CME) |
| Context | Utilisation: 5 ratios above 70%. Credit: 18 CRRs; Cat A on 85 of 105 Facilities rows |
| Confirmed triggers | 0. Owners must sign off definitions first; 44 owner questions are listed |
| Best example | SoftBank: a new USD 400m facility approved 17 Sep 2026. The same facility ID shows USD 179.7m drawn as a Cat A term loan, and DRR independently shows USD 179.7m used of a USD 400m limit. It shows what the board is for, but needs validation |

## Is it practical?

**Yes, as a phased pilot. Not yet as a full production board.** The interface is proven and cheap to extend. The value depends on four things outside the dashboard:

1. production data feeds, starting with LoanIQ drawn amounts and participation
2. entity matching at scale
3. definition sign-off by data owners
4. an MNPI/entitlement decision for call reports

With today's data the board shows one live signal. That is enough to demonstrate the approach, not enough to change banker behaviour.

## Recommendation

**Phase 1 pilot (6–8 weeks, indicative):**
- 20–30 IG Cat A clients, chosen with Jerome
- signals: SIG02 + SIG01 (once LoanIQ drawn amounts arrive) + debt-maturity windows + the LAF news feed
- weekly refresh, used by 3–5 DCM originators
- **in parallel, back-test** the signals against the completed-deals file and Dealogic, to show whether they precede real issuances

## Asks

1. Agreement to run the Phase 1 pilot.
2. Sponsorship of the data requests: LoanIQ drawn + participation, derivatives trades, financial covenant tests.
3. Start the CME call-report governance review (MNPI and entitlements).
4. Named time and data-engineering support; agree the production route (AI Markets).
