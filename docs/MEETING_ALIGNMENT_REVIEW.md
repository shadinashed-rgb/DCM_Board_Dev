# Meeting requirements vs development: alignment review

Date: 5 November 2026 · Scope: Bond Radar (AI DCM / Use Case 6 – Market Signals) · Baseline reviewed: `signal_workbooks_20261105_003` (rule version `development-1`, 626 evidence records)

This review compares the decisions captured in the DCM meeting notes (Jerome Pierre Zecchini, Simonti Basu, Pankaj Pathak, Roksana Martirosjana, Shadi Nashed) with what the development package implemented, and checks the raw source data where it bears on a decision. The resulting changes are recorded in [Status after the update](#status-after-the-update).

## Summary

The overall direction matches the meetings: the signal list, the dashboard-first approach and the cautious treatment of evidence. However, six later decisions were not recorded anywhere in the development documents:

1. the broader RCF definition
2. the credit approval date for bridges
3. the split of pre-hedging into two signals
4. call reports as the rating-advisory source
5. the half-turn covenant-pressure rule
6. dropping "number of investor sales"

Because of this, SIG01, SIG06 and SIG07 were built to different definitions from the ones Jerome gave.

## Decisions captured in the meetings

| Topic | Decision |
|---|---|
| RCF drawing (SIG01) | Not limited to products labelled RCF. Any drawing by a client on any **Cat A** bank facility (RCF, term loan, bilateral or other direct lending) of **more than EUR 50m** is material and should be signalled. |
| RCF thresholds | Two amounts: HSBC's own share of the drawing, and the inferred total drawing (HSBC drawing ÷ HSBC participation; e.g. EUR 10m at 10% = EUR 100m). Below EUR 50m total is insignificant for investment-grade corporates. Parent and subsidiary drawings both count; small local drawings (EUR 5–10m) are noise. |
| Bridge facility date (SIG02) | Use the **internal credit approval date** from the credit team, not the signing date. It comes earlier than signing and is straightforward to obtain. |
| Pre-hedging (SIG03) | FX swaps in particular indicate pre-hedging. There are **two independent signals**: (a) rolling an existing swap tied to maturing debt, and (b) enquiries about a new pre-hedge swap ahead of a new issuance. Whether Bloomberg chatrooms could be a source is left open; the signal does not exist in markets systems today. |
| Rating advisory (SIG07) | Source is **call notes / call reports**. Requests are rare and will not be automated in AI Markets or other systems. Directly linked to CME call reports (SIG05). |
| Number of investor sales | **Dropped**: a weak signal because HSBC initiates the investor interaction. |
| Covenant pressure (SIG06) | A leverage covenant (e.g. net debt / EBITDA) is under pressure when the actual ratio is **within half a turn (0.5x) of the covenant maximum**: 2.5x against 3x, 3.5x against 4x, 1.5x against 2x. The originator should be alerted. |
| Signal list | Existing RCF or new RCF/term loan/bridge; derivatives / pre-hedge pricing; KYC onboarding or signatory refresh; CME call-report keywords (acquisition, drawing, opportunistic, liquidity); covenant breach or pressure (possible hybrid). |
| Delivery | A dashboard (like the LAF board) rather than email triggers; daily rather than weekly data; LoanIQ is the RCF source; CME is complex because of MNPI and entitlements; flag upcoming debt maturity windows. |
| Data requests (Simonti to Roksana) | Source and country for: RCF drawings and materiality, new term loans and bridges, covenant pressure, ratings advisory, KYC, CME. |

## Requirement-by-requirement comparison (baseline `development-1`)

| Meeting requirement | What was developed | Alignment |
|---|---|---|
| Signal list (RCF, new facilities, derivatives, KYC, CME, covenants) | SIG01–SIG07 cover all of them; SIG05 (CME) excluded for MNPI/entitlement reasons | ✅ Aligned |
| Dashboard instead of email triggers, LAF style | Dashboard built; no automated triggers | ✅ Aligned |
| "Number of investor sales" dropped | Never developed | ✅ Nothing to remove |
| RCF drawing = any Cat A facility drawing > EUR 50m (RCF, term, bilateral) | SIG01 restricted to CLO product `REV`; no Cat A filter; no EUR 50m test; compares current with prior drawn balance | ❌ Too narrow |
| Two thresholds: HSBC share and inferred total | Participation inference deliberately not done; no FX to EUR | ❌ Not implemented |
| Parent and subsidiary drawings count; threshold filters small local drawings | Facility/borrower grain kept | ✅ In principle; needs the threshold |
| Bridge date = internal credit approval date | SIG02 uses `facility_creation_date`; open question still "signing vs amendment" | ⚠️ Decision not captured (see finding 1) |
| Pre-hedging: two separate signals; FX swaps highlighted | One SIG03 "enquiry" signal, no source; notes say executed trades cannot substitute for enquiries | ❌ Out of date; signal (a) could use booked trade data |
| Rating advisory source = call reports | SIG07 built from Facilities `limit_cat`, PVD category/CRR fields and Application Ratings CRR | ❌ Wrong source; call reports are the CME source (SIG05) |
| Covenant pressure = leverage within 0.5x of covenant maximum | SIG06 tests utilisation > 70% (an internal proposal: "extract approved and utilisation limit to calculate covenants pressure"); no genuine covenant data; the file labelled covenants was Counterparty data | ❌ Different definition |
| Daily refresh | Static snapshots; manual dashboard rebuild | ❌ Not yet |
| Debt maturity windows on the dashboard | Not built, although CLO and Facilities carry maturity dates | ❌ Gap |

## Findings in the source data

1. **The credit approval date may already be present.** For all 8 SIG02 recent candidates, the facility's `credit_proposal_serial_no` links to an Application Ratings application whose `approval_dt` equals `facility_creation_date` (17 Sep 2026 for serial 260917; 6 Oct 2026 for serial 261006). `facility_creation_date` may therefore be the credit approval date the meeting agreed to use, subject to source-owner confirmation. Facilities' own `loan_approva_dt` is a `0` placeholder on all 8 rows and is not usable.
2. **Jerome's broader definition brings in drawings SIG01 excludes.** The default CLO drawn field `facility_drawn_amount` is empty on all 276 rows, which is why the three SIG01 comparisons were imputed zero. The only non-zero drawn values are in `ag_acc_bal_drawn_sub_lim_usd`, all on SoftBank `TERM` sub-limits:
   - USD 179.7m: current snapshot only, no prior row
   - USD 200m: present in both snapshots, unchanged
3. **"Cat A" is in the data but was used for the wrong signal.** Facilities `limit_cat` = `CAT-A` on 85 of 105 rows. The development treated it as a SIG07 advisory clue, whereas Jerome uses Cat A as the eligibility filter for drawings. CLO has no category field; 3 of its 5 sub-limit IDs match a Facilities `facility_id`, which supports a lookup that must be validated.

## Recommended changes

1. Record the six decisions in the development definitions and close the questions they answer: what the EUR 50m baseline applies to, the qualifying products, the bridge date, and covenant pressure.
2. **SIG01:** any Cat A facility type; measure the drawing against EUR 50m; apply an HSBC-share lower-bound test and inferred-total logic; agree an FX source and the participation-share field.
3. **SIG02:** use the credit approval date and confirm that the creation date equals it.
4. **SIG03:** split into SIG03A (swap rolls from derivatives trade data, FX swaps first) and SIG03B (new pre-hedge enquiries; source open).
5. **SIG06:** implement the half-turn rule; stop presenting utilisation as covenant pressure; request financial covenant data (actual ratio, covenant maximum, test date).
6. **SIG07:** move to call reports, which ties it to CME access (SIG05); keep CRR and Cat A as credit context.
7. Add debt-maturity windows and plan for daily refresh.

## Status after the update

Applied in rule version `development-2` (run `development/runs/aligned_20261105_004`, package `signal_workbooks_20261105_004`). See `development/DEVELOPMENT_UPDATE_MEETING_ALIGNMENT_20261105.md` for detail.

| Item | Change made | Still open |
|---|---|---|
| SIG01 | Products widened to REV and TERM; Cat A lookup from Facilities via the matching facility ID; EUR 50m materiality test on the drawing increase (HSBC-share lower bound; inferred total when a participation share is available); separate comparison on the populated USD drawn field | FX rates and participation-share field not supplied, so materiality stays "undetermined"; facility-ID match across CLO and Facilities needs validation; LoanIQ remains the named source |
| SIG02 | Event date is the credit approval date: Application Ratings `approval_dt` via `credit_proposal_serial_no`, otherwise Facilities `loan_approva_dt`, otherwise `facility_creation_date` flagged as candidate | Source owner to confirm that creation date equals approval date; bridge product codes |
| SIG03 | Split into SIG03A (swap roll) and SIG03B (new pre-hedge enquiry), both reported as source missing, with the required fields documented | Derivatives trade source for SIG03A; enquiry source (e.g. Bloomberg chat) for SIG03B |
| SIG06 | Covenant-pressure rule implemented (headroom ≤ 0.5 turns below a maximum-type leverage covenant); utilisation moved to `CTX_UTIL` context | Genuine financial covenant data |
| SIG07 | Source set to CME call reports (not integrated; MNPI/entitlement); Facilities/PVD category and Application Ratings CRR moved to `CTX_CREDIT` context | CME access decision |
| Investor sales | Recorded as dropped | — |
| Maturity windows / daily refresh | Recorded as dashboard requirements | Not yet built |

### Results under the updated rules

| Dataset | development-1 | development-2 | Note |
|---|---:|---:|---|
| SIG01 | 3 | 8 | REV + TERM, two drawn fields; 0 material (default field blank; FX and participation not configured). SoftBank TERM USD 179.7m drawn has no prior snapshot |
| SIG02 | 63 (8 recent) | 63 (9 recent) | Approval date linked for all 50 usable contexts; equals creation date for only 9. New candidate: SoftBank FCL approved 17 Sep 2026 |
| SIG03A / SIG03B / SIG04 / SIG06 / SIG07 | 0 / – / 0 / 442 / 118 | 0 / 0 / 0 / 0 / 0 | Former SIG06 and SIG07 records moved to context |
| CTX_UTIL | – | 442 | 5 ratios above 70% (context) |
| CTX_CREDIT | – | 118 | 96 category + 22 CRR (18 populated) |
| **Total** | **626** | **631** | All 626 map forward + 5 new SIG01 comparisons |

**Checks:** 87 tests pass (52 package + 35 engine), and the development-2 sample reference is verified (609 core / 619 combined).

**Where to find the outputs:**

| What | Path |
|---|---|
| Run | `development/runs/aligned_20261105_004/` |
| Review | `development/runs/aligned_20261105_004/REVIEW.md` |
| Owner questions | `development/runs/aligned_20261105_004/OWNER_REVIEW_*.csv` |
| Workbooks and reports | `signal_workbooks_20261105_004/` |
| Dashboard | `dashboard/dcm_signals_dashboard.html` |
