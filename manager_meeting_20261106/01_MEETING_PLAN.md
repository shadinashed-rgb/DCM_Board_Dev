# Meeting plan — Bond Radar results and practicality

**Meeting:** Bond Radar (AI DCM / Use Case 6 – Market Signals) · results, development status and practicality of a banker-facing board
**Date:** 6 November 2026 · **Length:** 60 minutes (a 45-minute version is marked ⏱)
**Presenter:** Shadi Nashed · **Attendee:** line manager

## Objectives for the meeting

1. Share what has been built and what the data shows, with honest limits.
2. Agree whether a banker-facing Bond Radar board is practical, and in what form.
3. Leave with decisions on the pilot scope, data-access escalation and resourcing.

## What to bring / have open

| Item | File |
|---|---|
| Dashboard (live demo, works offline) | `attachments/dashboard/dcm_signals_dashboard.html` |
| Screenshots (backup if the demo can't run) | `attachments/dashboard/screenshots/` |
| One-page briefing | `02_BRIEFING_ONE_PAGER.md` (also in `Bond_Radar_Manager_Briefing.docx`) |
| Practicality assessment | `06_PRACTICALITY_ASSESSMENT.md` |
| Next steps and roadmap | `07_NEXT_STEPS_AND_ROADMAP.md` |
| Likely questions with answers | `08_QUESTIONS_AND_ANSWERS.md` |
| Reports | `attachments/reports/SIGNAL_OVERVIEW.xlsx` and the per-signal workbooks |

## Agenda

| # | Time | Topic | Goal | Material |
|---|---|---|---|---|
| 1 | 0–5 | Context and purpose | Re-establish why DCM wants Bond Radar | 02 one-pager, 03 requirements |
| 2 | 5–15 | Demo of the dashboard | Show the working board and its drill-downs | Dashboard (demo script below) |
| 3 | 15–25 | Results: what the data tells us | Present findings honestly: one live signal today, several data gaps | 05 results |
| 4 | 25–30 | Alignment with DCM requirements | Show the board now follows Jerome's definitions | 03, 04, alignment review |
| 5 | 30–45 | Practicality: can we build this for users? | Discuss feasibility, effort, risks and options | 06 practicality |
| 6 | 45–55 | Decisions and asks | Get decisions on pilot, escalation and resources | Decision list below |
| 7 | 55–60 | Next steps and close | Agree owners and dates | 07 roadmap |

⏱ **45-minute version:**
- Shorten the demo to 7 minutes: steps 1, 3, 4, 6 and 9 below.
- Cover results and alignment together in 8 minutes.
- Keep the practicality section (15 minutes) and the decisions (10 minutes) intact.
- Close in 5 minutes.

## Talking points by section

### 1 · Context (5 min)

- DCM wants to know **which clients may issue bonds**, early, from internal signals they cannot see today. Today, LAF casts a wide net manually: news, filings and matching done by teams in India.
- The agreed format is a **dashboard, not email alerts**, to avoid information overload. The LAF board is the design reference.
- This phase is **development on three known clients**: Vodafone, Siemens Energy and SoftBank. The aim is to prove the data and definitions before scaling.

### 2 · Demo (10 min) — see the demo script below

### 3 · Results (10 min)

**Headline:**
- The engine and board work end to end on real data.
- Under the agreed definitions, **one signal (SIG02, new facilities by credit approval date) produces candidates today: 9 facilities** approved in the last 90 days.

**Why so few?** It is a data problem, not a design problem:
- the drawn-amount field needed for SIG01 is blank in the CLO extract
- there is no derivatives or enquiry source (SIG03A/B)
- the KYC export is empty (SIG04)
- there are no covenant tests (SIG06)
- call reports (SIG07) need CME access

**Best example:**
- SoftBank's new USD 400m facility was approved 17 Sep 2026.
- The same facility ID shows USD 179.7m drawn as a Cat A term loan.
- DRR independently shows USD 179.7m utilised of a USD 400m limit.
- That is Jerome's pattern of a new facility that is being drawn. It needs validation before it can be called a trigger.

**What we learned that matters:**
- Credit approval and creation dates differ for most older facilities.
- Cat A is in the Facilities data and can filter drawings.
- SoftBank has a USD 179.7m term-loan drawing with no prior snapshot to compare against.

### 4 · Alignment (5 min)

- After the DCM meetings, every signal was re-defined to Jerome's wording:
  - any Cat A drawing over EUR 50m
  - the credit approval date
  - two pre-hedging signals
  - covenant pressure within half a turn
  - rating advisory from call reports
  - investor sales dropped
- Code, results, reports and the dashboard were all updated (rule version development-2). 87 tests pass.

### 5 · Practicality (15 min) — the core of the meeting

- **The board itself is the easy part.** It is built and reuses the LAF style.
- **The hard parts:**
  1. production data feeds and daily refresh
  2. entity matching at scale
  3. owners signing off definitions
  4. MNPI and entitlement rules for CME
  5. an operating model (who runs it)
- **Signal by signal:** build now (SIG02, maturity windows); build after one data request (SIG01, SIG03A); needs a governance decision (SIG07/SIG05); park (SIG03B).
- **Recommendation:** a **phased pilot**. Phase 1 is an MVP for ~20–30 investment-grade clients with SIG02 + SIG01 (once LoanIQ drawn amounts arrive) + debt maturity windows + the existing LAF news feed, refreshed weekly, used by 3–5 DCM bankers. In parallel, back-test against the completed-deals file to prove value.

### 6 · Decisions and asks (10 min) — see the list below

### 7 · Close (5 min)

- Confirm the owners and dates in `07_NEXT_STEPS_AND_ROADMAP.md`.
- Agree the next check-in (suggest two weeks).

## Demo script (dashboard)

Open `attachments/dashboard/dcm_signals_dashboard.html` in a browser. It is one file and needs no internet.

1. **Header and KPIs:** 71 signal records, 9 test candidates, 5 signals without data, 560 context records, 0 confirmed triggers. *"Everything here is development evidence, not alerts."*
2. **Radar:** one shape per client. Toggle *Development tests* and *Evidence coverage*. Point out that only the New facility axis fires.
3. **Client view:** each row is a client and each cell a signal. Red is a test candidate, amber is evidence needing validation, grey is missing data.
4. **Click SoftBank:** the drill-down shows the FCL facility approved 17 Sep in SIG02 and the same ID with USD 179.7m drawn in SIG01. Then **click Vodafone** to open its drill-down. It shows the 7 facilities approved on 17 Sep, the Cat A sub-limits with no drawing increase, the utilisation context and the CRR context.
5. **Development tests:** the approval-age chart with the 90-day band; the utilisation strip shown as context.
6. **Signal catalogue:** 7 signals, 2 with evidence; SIG05 excluded; two context datasets.
7. **"What the meetings changed":** the six decision cards, each with a "before" line.
8. **Evidence explorer:** filter SIG02 → *Test candidate*, click a row, show the lineage back to the source CSV record.
9. **Owner review queue:** 44 questions that source owners must answer before triggers can be switched on.

Backup: if the browser can't open the file, use the PNGs in `attachments/dashboard/screenshots/`.

## Decisions to ask for

| # | Decision | Recommended answer |
|---|---|---|
| D1 | Proceed to a **Phase 1 pilot** of the board? | Yes: phased MVP with clear exit criteria (see 06) |
| D2 | **Pilot scope:** which clients and which bankers? | 20–30 IG Cat A clients chosen with Jerome; 3–5 DCM originators |
| D3 | **Sponsor escalation of data requests**: LoanIQ drawn + participation, derivatives trades, financial covenants | Manager to sponsor with Roksana's credit team and the markets data owners |
| D4 | **CME call reports (SIG05/SIG07):** start the MNPI/entitlement review now or defer? | Start the governance conversation now; it has the longest lead time |
| D5 | **Hosting / production route:** AI Markets, CIP/HDP46, or a scheduled Starburst extract | Agree a target with the AI Markets team; keep the prototype local until then |
| D6 | **Time and resources** for the next 6–8 weeks | Named time from Shadi plus a data engineer for feeds and entity mapping |
| D7 | **Predictive model** (Simonti's proposal): in parallel or after the pilot? | After: start with back-testing only (cheap), and model once the signals are proven |

## Notes space

| Topic | Decision / comment | Owner | Date |
|---|---|---|---|
| D1 |  |  |  |
| D2 |  |  |  |
| D3 |  |  |  |
| D4 |  |  |  |
| D5 |  |  |  |
| D6 |  |  |  |
| D7 |  |  |  |
