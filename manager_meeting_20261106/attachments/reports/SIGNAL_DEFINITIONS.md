# Signal definitions — development-2 (meeting-aligned)

Authority: the DCM meeting decisions (see `docs/MEETING_ALIGNMENT_REVIEW.md`) and explicit user decisions supersede older discovery notes. No business trigger is confirmed: every `definitions_verified` flag is false. Core assessment is 3 November 2026; CRR context assessment is 4 November.

## SIG01 — Material drawing on a Cat A bank facility

*Kind:* signal · *Coverage:* partial_development_evidence · *Records:* 8

- **Business purpose (Meeting decision):** A drawing on a bank facility shows the client needs cash; the first source of funding is usually the RCF, so a material drawing may precede bond refinancing.
- **Eligible facilities (Meeting decision):** Any Cat A bank facility: RCF, term loan, bilateral or other direct lending. The RCF label is not required. Engine: CLO REV and TERM; blank products stay ineligible (unknown).
- **Cat A eligibility (Development rule):** Facilities limit_cat = CAT-A, looked up where the CLO sub-limit ID equals the Facilities facility_id. Observed development link, not an approved cross-source identity.
- **Measure (Development rule):** Drawing = current drawn minus prior drawn for the same sub-limit, keeping the actual comparison dates and gap. An absent prior observation is unavailable.
- **Materiality (Meeting decision):** Drawing above EUR 50m is material. HSBC share is a lower bound (share never exceeds the whole facility); the inferred total = HSBC drawing ÷ participation share is used when a share is available (sole lender = 100%).
- **Currency (Development rule):** Non-EUR amounts are converted only with configured FX rates (none supplied); no fallback conversion.
- **Missing values (User decision):** Blank drawn is zero only for SIG01, with current/prior flags; imputed comparisons are never assessed for materiality.
- **Alternative drawn field (Development rule):** ag_acc_bal_drawn_sub_lim_usd is compared separately (component drawing_change_alt_usd) and never mixed with facility_drawn_amount.
- **Open definitions (Unresolved):** Authoritative drawn field (LoanIQ), FX source/date, participation-share field, comparison horizon, validation of the CLO/Facilities ID link.

## SIG02 — New RCF, term loan or bridge (credit approval)

*Kind:* signal · *Coverage:* partial_development_evidence · *Records:* 63

- **Business purpose (Meeting decision):** A newly approved RCF, term loan or bridge has a high chance of being refinanced in the bond market.
- **Event date (Meeting decision):** Internal credit approval date from the credit team (earlier than signing).
- **Date source (Development rule):** Facilities loan_approva_dt if valid (currently a 0 placeholder); otherwise facility_creation_date as a labelled candidate; then Application Ratings approval_dt linked by credit_proposal_serial_no (same CIN preferred).
- **Recency test (Development rule):** Age = core assessment date minus event date; the 90-day inclusive lookback is a development test.
- **Ambiguity (Development rule):** Contexts with conflicting products or dates are withheld rather than resolved with arbitrary first/MAX values.
- **Open definitions (Unresolved):** Confirm the linked application approval is the approval of the new facility (not a review/renewal); product dictionary for RCF / term / bridge; publishing scope (Siemens DE).

## SIG03A — Swap roll on maturing debt

*Kind:* signal · *Coverage:* source_missing · *Records:* 0

- **Business purpose (Meeting decision):** A client rolling an existing swap tied to maturing debt points to refinancing of that debt.
- **Independence (Meeting decision):** Treated independently of SIG03B even though both point to a potential issuance.
- **Primary input (Missing source):** Derivatives trade/booking data (FX swaps first; IRS/CCS). Not supplied.
- **Required fields (Required contract):** Client identifiers, trade id, product, trade and maturity dates, notional and currency, linked debt reference, roll/novation indicator.
- **Open definitions (Unresolved):** Source system and owner, roll definition, linkage to maturing debt.

## SIG03B — New pre-hedge swap enquiry

*Kind:* signal · *Coverage:* source_missing · *Records:* 0

- **Business purpose (Meeting decision):** An enquiry about a new pre-hedge swap ahead of an issuance; FX swaps in particular indicate pre-hedging (MSS team).
- **Primary input (Missing source):** Pre-hedge / swap-pricing enquiries. The signal does not exist in markets systems today; Bloomberg chatrooms were raised as a possible source (open).
- **Required fields (Required contract):** Client identifiers, enquiry id and date, product, status, notional and currency, financing purpose.
- **Open definitions (Unresolved):** Source, enquiry eligibility, repeated-request rules, identity route.

## SIG04 — KYC onboarding or signatory refresh

*Kind:* signal · *Coverage:* empty_export · *Records:* 0

- **Business purpose (Business definition):** Onboarding a new entity or refreshing KYC of signatories may precede a bond transaction.
- **Primary input (Empty export):** delta.prod_party_gda.kyc; the selected target export is valid but header-only.
- **Development fields (Development rule):** review_request_created_time_stamp and candidate NTB/TRG purpose codes; 90-day lookback unverified.
- **Identity and schema (Source constraints):** cdd_topco_legal_name is an array; mg_parent_grid/groupguci are not automatically mastergroup IDs.
- **Open definitions (Unresolved):** Known target case/entity, NTB/Trigger/Periodic/Remediation meanings, case dates, signatory coverage.

## SIG05 — CME call report keywords

*Kind:* excluded · *Coverage:* excluded · *Records:* 0

- Excluded pending CME MNPI handling and entitlements; also the source for SIG07.

## SIG06 — Financial covenant breach or pressure

*Kind:* signal · *Coverage:* source_missing · *Records:* 0

- **Business purpose (Meeting decision):** A covenant breach or covenant pressure may signal a financing need, including a hybrid transaction; the originator should be alerted.
- **Covenant pressure (Meeting decision):** Leverage (e.g. net debt / EBITDA) within half a turn (0.5x) of the covenant maximum: >= 2.5x against 3.0x, >= 3.5x against 4.0x, >= 1.5x against 2.0x.
- **Engine rule (Development rule):** For approved financial tests with a maximum-type operator (<, <=): headroom = maximum - actual; pressure when headroom <= 0.5; breach when the compliance condition fails.
- **Primary input (Missing source):** Genuine financial covenant tests: metric, actual/final value, maximum, operator, test date, approval state. Not supplied; the file labelled covenants is Counterparty data (quarantined).
- **Utilisation (Meeting decision):** Utilisation above 70% is not covenant pressure; it is reported as CTX_UTIL context.
- **Open definitions (Unresolved):** Covenant source, metric naming, units and operator semantics, approval states.

## SIG07 — Rating advisory request (call reports)

*Kind:* signal · *Coverage:* source_not_integrated · *Records:* 0

- **Business purpose (Meeting decision):** A client asking about HSBC acting as rating advisor; rare and linked to the CME call-report signal.
- **Source (Meeting decision):** Call notes / call reports recorded by senior bankers after client discussions. Will not be automated in AI Markets.
- **Integration (Missing source):** CME is not integrated: MNPI handling and entitlements must be resolved (same dependency as SIG05).
- **Former inputs (Meeting decision):** Facilities limit_cat/advised_ind, PVD category/CRR and Application Ratings CRR are credit context (CTX_CREDIT), not SIG07 evidence.

## CTX_UTIL — Facility utilisation (context)

*Kind:* context · *Coverage:* partial_development_evidence · *Records:* 442

- **Purpose (Meeting decision):** Supporting context on facility usage shown beside the signals. Not a signal and not covenant pressure.
- **Calculation (Development rule):** Utilisation percent = valid utilisation / compatible approved limit x 100; values above 70% are flagged for context.
- **Compatibility (Development rule):** Numerator/denominator must share currency, units, scope, date and participation basis; otherwise unavailable.
- **No aggregation (Source constraints):** No sums across sources, currencies, snapshots, parent/child limits or whole-facility versus share.

## CTX_CREDIT — Credit category and rating (context)

*Kind:* context · *Coverage:* partial_development_evidence · *Records:* 118

- **Purpose (Meeting decision):** Credit context: Facilities limit_cat (Cat A/B/S), advised_ind and grades, PVD category/CRR, Application Ratings CRR. Cat A also drives SIG01 eligibility.
- **Displayed CRR (User decision):** Non-placeholder final_crr with crr_scale; previous/proposed/approved/manual/overridden kept separately; blank/N/A unavailable without fallback.
- **Version selection (Development rule):** Latest supplied snapshot per source/country/CARM scope, then candidate effective periods; HISTORICAL can coexist with an open period.
- **Multiple ratings (Source constraints):** Competing applications and multiple CRRs per CIN are kept; no MAX, averaging or numeric direction.

## Dropped

- **Number of investor sales:** dropped by DCM as a weak signal, because HSBC initiates the investor interaction. Jerome agreed.
