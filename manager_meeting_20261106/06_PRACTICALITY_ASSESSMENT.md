# Practicality assessment — can we build Bond Radar for DCM users?

## Short answer

**Yes, as a phased pilot, but not yet as a full production board.**

- **The interface is not the risk.** It is built, it reuses the LAF board's design, and it can be extended quickly.
- **The value depends on data.** Today 2 of 7 signals have usable data and 1 produces candidates. A banker will only use the board if it regularly surfaces things they did not already know. In practice that means at least three working signals plus debt-maturity and news context.

## What is proven vs. what is not

| Proven by the prototype | Not yet proven |
|---|---|
| Internal sources can be extracted, linked to client groups and turned into auditable evidence | That signals **precede real issuances** (no back-test yet) |
| The DCM definitions can be encoded as testable rules (87 tests) | That data for SIG01, SIG03, SIG06 and SIG07 **exists and is accessible** |
| A single, offline, HSBC-style board can present signals, gaps and lineage | **Daily refresh** from production feeds |
| Missing data can be shown honestly, without false negatives | **Entity matching at scale** beyond three hand-checked clients |
| SIG02 credit approval dates can be sourced | That bankers will **use it weekly** and act on it |

## Signal-by-signal feasibility

Business value is from the DCM meetings. Effort is indicative relative sizing (S = days, M = weeks, L = months or governance-dependent).

| Signal | Business value | Data today | Effort to production | Main blocker | Verdict |
|---|---|---|---|---|---|
| SIG02 New facility (approval date) | High | ✅ Facilities + Application Ratings | S–M | Credit-team confirmation; product dictionary | **Build now** (MVP anchor) |
| Debt-maturity windows (DASH03) | High (classic refinancing trigger) | ✅ Facilities / CLO maturity dates | S | None material | **Build now** (quick win) |
| External news (from LAF) | Medium–High | ✅ Refinitiv in LAF board | S–M | Reuse and entity matching | **Reuse** in Phase 1 |
| SIG01 Cat A drawing > EUR 50m | **Very high** (Jerome's priority) | ⚠️ CLO drawn field blank | M | LoanIQ drawn by facility, participation share, FX rule | **Build after one data request** |
| SIG03A Swap roll | Medium–High | ❌ | M | Derivatives trade source / owner | **Request source** |
| SIG06 Covenant pressure | High (hybrid angle) | ❌ | M–L | Financial covenant tests may only exist in credit papers | **Confirm a source exists** first |
| SIG04 KYC | Medium (noisy) | ❌ Empty export | M | Known case and purpose definitions | **Retry with a known case** |
| SIG05 / SIG07 Call reports | High | ❌ | L + governance | MNPI, entitlements, information barriers | **Start governance now**; build later |
| SIG03B Pre-hedge enquiry | High | ❌ Not captured anywhere | L | New capture process or chat analytics + compliance | **Park** for now |

## The real cost drivers (beyond the dashboard)

1. **Production data feeds.** Replace manual Starburst copy/paste with scheduled, owned extracts (or AI Markets ingestion). This is a prerequisite for daily or weekly refresh.
2. **Entity resolution.** CIN, GID and PVD identifiers differ by source and country. Three clients were mapped by hand. Twenty to fifty clients need a maintained, reviewed mapping table. This should be shared with LAF, which has the same problem.
3. **Definition ownership.** Every rule needs a named owner to sign off: credit for SIG01/SIG02, markets for SIG03, risk for SIG06. Without sign-off, nothing can be shown as a trigger.
4. **Governance.** MNPI and entitlements for call reports, permitted use of KYC and credit data, and the information barrier between DCM (private side) and other users.
5. **Operating model.** Someone must run the refresh, handle data breaks and keep mappings current. A pilot can live with a person; production needs a team or platform.

## Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| A. Continue as a prototype | Keep developing on 3 clients until all data is found | Low cost | No user feedback; risk of building in a vacuum |
| **B. Phased pilot (recommended)** | MVP for 20–30 IG Cat A clients with SIG02 + maturity windows + news, adding SIG01 once LoanIQ data lands; weekly refresh; 3–5 bankers; back-test in parallel | Real feedback early; proves value with evidence; data requests get priority because there is a user | Needs sponsor support for data access and some engineering time |
| C. Pause | Wait until all sources are secured | No wasted effort | Momentum lost; data owners have no reason to prioritise |

## Recommendation (Option B) with exit criteria

**Phase 1 pilot (indicative 6–8 weeks after data access is confirmed):**

**Scope**
- 20–30 IG Cat A clients agreed with Jerome
- 3–5 DCM originators as users
- weekly refresh

**Content**
- SIG02 (approval date)
- debt-maturity windows (< 12m, 12–24m)
- LAF news feed
- SIG01 as soon as LoanIQ drawn amounts and participation arrive
- coverage gaps shown explicitly

**Back-test in parallel**
- Using the completed-deals file (2 years) and Dealogic: for each past issuer, did SIG01, SIG02 or a maturity window appear 3–12 months before the deal?
- This is the cheapest way to prove or disprove value before scaling.

**Exit criteria to decide on Phase 2**

| Test | Measure |
|---|---|
| Value | Back-test shows signals preceding a meaningful share of past issuances |
| Use | Pilot bankers use the board weekly and log at least some conversations it prompted |
| Data | Feeds for at least 3 signals are owned and refreshing |
| Governance | A decision on CME call reports, and sign-off of the SIG01 and SIG02 definitions |

## Other considerations worth raising

| Area | Consideration |
|---|---|
| **Prove value before scaling** | Back-testing against historical DCM mandates is cheap and turns a nice prototype into a business case. Note that HSBC-won deals understate opportunity; Dealogic adds deals HSBC did not win |
| **Alert fatigue** | Thresholds (EUR 50m, Cat A, 90 days) keep noise down. Start conservative and measure how many signals per client per month the bankers find useful |
| **Prioritisation / scoring** | Bankers will ask "who first?" Begin with a transparent rule-based order (number and strength of signals) before any predictive score |
| **Explainability** | Every cell already links to its source record. Keep this: it is what makes bankers trust the board |
| **Missing ≠ no activity** | Keep data gaps visible (grey cells). A silent gap is worse than a visible one |
| **Reuse with LAF** | Same style, same entity-matching need and same news feed. One platform with two views (LAF and DCM) is cheaper than two boards |
| **Hosting** | Agree early where the board lives (AI Markets, an internal web host, or a shared drive HTML for the pilot) and who can see it (entitlements) |
| **MNPI / information barriers** | DCM is private-side. Confirm who may see credit and KYC data on the board before widening access |
| **Model risk** | Rule-based signals are simple. If a predictive score is added later, it will need model-governance review |
| **Change management** | Agree how bankers record "contacted / not relevant" so the board learns and value can be measured |
| **Data quality** | Blank fields (CLO drawn amount), placeholders (`0` approval dates) and stale sources (PVD at 30 Sep) are real. Freshness labels must stay on the board |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Key data (LoanIQ drawn, covenants, derivatives) not accessible | Medium | High | Manager sponsorship; start with signals that already work |
| Signals do not precede issuance | Medium | High | Back-test before scaling |
| Entity mapping effort underestimated | High | Medium | Limit the pilot to 20–30 clients; share the mapping work with LAF |
| CME/MNPI review takes months | High | Medium | Start now; do not make Phase 1 depend on it |
| Pilot depends on one person | High | Medium | Document the runbook (exists), add a data engineer, agree hosting |
| Bankers do not adopt it | Medium | High | Co-design with Jerome; keep it small and relevant; measure use |
