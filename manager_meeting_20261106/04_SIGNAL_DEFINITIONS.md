# Signal definitions — at a glance (rule version development-2)

Full definitions with status labels: `attachments/reports/SIGNAL_DEFINITIONS.md` and the *Definitions* sheet of `SIGNAL_OVERVIEW.xlsx`.

| ID | Signal | Why it matters to DCM | How it is measured | What blocks a trigger today |
|---|---|---|---|---|
| **SIG01** | Material drawing on a Cat A bank facility | A client drawing on its bank lines needs cash; refinancing in the bond market may follow | Drawn amount now minus prior snapshot, for any Cat A facility (RCF, term loan, bilateral). **> EUR 50m** is material. HSBC share is a lower bound; inferred total = HSBC drawing ÷ participation | Blank drawn field in CLO (LoanIQ needed); FX source/date; participation share; validating the CLO ↔ Facilities ID link |
| **SIG02** | New RCF, term loan or bridge | New facilities are often refinanced in the bond market | **Credit approval date** (Application Ratings, linked by credit proposal serial) within 90 days | Credit team to confirm the approval relates to the new facility; product codes for RCF / term / bridge |
| **SIG03A** | Swap roll on maturing debt | Rolling a swap tied to maturing debt signals refinancing | Roll/novation of an existing swap (FX swaps first) | No derivatives trade source supplied |
| **SIG03B** | New pre-hedge swap enquiry | Pre-hedging is a strong pre-issuance indicator | Enquiry/pricing request for a new swap | Does not exist in markets systems; Bloomberg chat is an open idea |
| **SIG04** | KYC onboarding / signatory refresh | New issuing entity or signatory changes can precede a deal | KYC case purpose and date within a lookback | Target KYC export is empty; purpose codes undefined |
| **SIG05** | CME call-report keywords | Banker notes mention acquisition, drawing, liquidity | Keyword detection in GRB call reports | **Excluded:** MNPI and entitlements |
| **SIG06** | Covenant breach or pressure | Pressure can lead to refinancing or a hybrid | Leverage (net debt / EBITDA) **within 0.5x of the covenant maximum**; or a breach | No genuine financial covenant tests available |
| **SIG07** | Rating advisory request | Rare but very relevant to DCM | Requests recorded in call reports | Same CME dependency as SIG05 |
| CTX_UTIL | Utilisation (context) | Supporting view of facility usage | Utilised ÷ approved limit; > 70% flagged | Context only — not covenant pressure |
| CTX_CREDIT | Credit category and CRR (context) | Cat A status and credit quality | Facilities limit_cat, PVD category, Application Ratings CRR | Context only |

**Rules that apply to all signals:**
- **Evidence, not alerts.** No trigger fires until the owner of a definition signs it off and its `definitions_verified` flag is switched on.
- **Missing data is not "no activity".** Empty or missing sources are shown in grey.
- **No hidden arithmetic.** There is no FX conversion without an agreed rate, no summing across sources or currencies, and no "best" CRR picked from competing ones.
