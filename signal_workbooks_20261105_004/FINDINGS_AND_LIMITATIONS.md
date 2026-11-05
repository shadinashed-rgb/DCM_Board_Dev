# Findings and limitations — 5 November 2026 (development-2)

The 631 records are development evidence and context. The additional DE extraction is deferred. Run: `development/runs/aligned_20261105_004` (review in its `REVIEW.md`).

## All signals

- **Meeting alignment:** Rules follow the DCM meeting decisions (development-2): Cat A drawing over EUR 50m, credit approval date, SIG03A/SIG03B split, half-turn covenant pressure, call-report rating advisory, investor sales dropped. Confirm each rule with its owner before setting definitions_verified.
- **Scope:** Three target mastergroups: Vodafone MG001356, Siemens Energy MG102229 and SoftBank MG101624. SIG05 and PVD sector aggregate excluded. Preserve scope.
- **Evidence versus alerts:** 631 records are development evidence/context; business_trigger is blank on every record. Define and verify business rules before confirming triggers.
- **Assessment dates:** Core assessed 3 November 2026; CRR assessed 4 November from 3 November snapshots. Do not silently rebase dates to export date.
- **Identity:** CIN, GID and PVD namespaces differ. The development-2 lookups (CLO sub-limit = Facilities facility_id; serial + CIN to Application Ratings) are development links. Use explicit reviewed, date-scoped mappings; keep conflicts.
- **Freshness:** PVD observation date is 30 September; daily refresh is a preference, not verified capability. Show actual source dates; do not treat stale or empty data as no activity.
- **Validation:** 87 local tests pass (52 package, 35 engine); development-2 sample reference verified (609 core / 619 combined). Use the owner-review files for business validation.
- **DE publishing:** Additional Siemens DE extraction remains deferred; DE history is shown separately. Validate publishing/current selection.

## SIG01 — Material drawing on a Cat A bank facility

- **Eligible comparisons:** 4 sub-limit comparisons on the default drawn field (Vodafone 2 REV, Siemens 1 REV, SoftBank 1 TERM) and 4 on the USD field. Confirm the authoritative drawn field (LoanIQ).
- **Default drawn field:** facility_drawn_amount is blank on all 276 CLO rows, so every default comparison is imputed zero and not assessable for materiality. Obtain drawn amounts by facility.
- **USD drawn field:** On ag_acc_bal_drawn_sub_lim_usd the Vodafone and Siemens sub-limits show no increase between 30 Oct and 2 Nov. Confirm field meaning (HSBC drawn balance in USD).
- **SoftBank term loan:** TERM sub-limit 00010341075552511210201 carries USD 179.7m drawn (Cat A) but has no prior snapshot, so no increase can be computed. Supply the prior snapshot.
- **SoftBank USD 200m:** Sub-limit 00010341075552607090201 is unchanged at USD 200m across snapshots and has a blank CLO product, so it is not assessed. Confirm product.
- **Cat A link:** Vodafone and SoftBank sub-limits match a CAT-A Facilities record; the Siemens REV sub-limit has no matching facility_id. Validate the ID link; obtain Cat A for Siemens.
- **Materiality:** No comparison is material: FX rates and participation share are not configured and the default field is blank. Agree FX source/date and the participation-share field.

## SIG02 — New RCF, term loan or bridge (credit approval)

- **Raw grain:** 105 supplied rows; 63 source/country/facility keys; 13 contexts withheld for conflicting products or dates; 50 usable. Preserve product and borrower child contexts.
- **Approval link:** All 63 keys link to Application Ratings by credit_proposal_serial_no and CIN; 50 usable contexts receive an approval date. Facilities loan_approva_dt is a 0 placeholder. Credit team to confirm the link.
- **Approval vs creation:** Approval equals facility_creation_date for 9 of 50; older facilities were approved weeks after creation (e.g. created 12 Apr 2005, approved 10 Jun 2005). Confirm which date is the credit approval of the new facility.
- **Recent candidates:** 9 within 90 days of approval: seven Vodafone (17 Sep), Siemens AE FGL AED 40m (6 Oct) and SoftBank FCL 00010341075552511210201 (created 9 Jul, approved 17 Sep). Confirm new-financing meaning and product eligibility.
- **German history:** 349 archived DE rows at 30 October are shown separately, not as current transactions. Additional extraction remains deferred.

## SIG03A — Swap roll on maturing debt

- **Missing source:** No derivatives trade data supplied; no swap-roll events can be assessed. DRR FSWP/FFEX limit lines are limits, not trades. Identify the derivatives trade source (FX swaps first).

## SIG03B — New pre-hedge swap enquiry

- **Missing source:** No pre-hedge enquiry source exists in markets systems; Bloomberg chat is an open option. Decide on a source and event contract.

## SIG04 — KYC onboarding or signatory refresh

- **Empty target export:** Zero supplied KYC rows with 326 native headers retained. Locate a known target case through a verified identity route.
- **Purpose ambiguity:** NTB, Trigger, Periodic and Remediation meanings are unverified; a Trigger case alone is not a financing event. Obtain definitions.

## SIG06 — Financial covenant breach or pressure

- **Missing covenant tests:** No genuine financial covenant tests: earlier samples are non-financial reporting obligations and the covenants file is Counterparty data (quarantined). Request net debt / EBITDA actuals, maxima and test dates.
- **Rule ready:** The half-turn pressure rule is implemented and tested (2.6x vs 3.0x = pressure; 2.4x = none; 4.0x = breach). Run on the first genuine covenant extract.
- **Utilisation moved:** The five utilisation ratios above 70% are context (CTX_UTIL), not covenant pressure. Do not present utilisation as covenant pressure.

## SIG07 — Rating advisory request (call reports)

- **Source not integrated:** Rating advisory requests are only recorded in CME call reports; CME access is pending MNPI/entitlement decisions. Decide on CME access (with SIG05).
- **Former evidence:** 118 former SIG07 records are now CTX_CREDIT context (96 Facilities/PVD category, 22 CRR). Use as credit context only.

## CTX_UTIL — Facility utilisation (context)

- **DRR exposures:** 642 native target rows reduce to 405 candidate exposures: 57 usable ratios and 348 unavailable. Preserve shared borrower lineage.
- **Ratios above 70%:** Vodafone 94.28%; Siemens 76.80% and 74.22%; SoftBank two at 100%; all 2 November; products FGTE, FCTA, FLNS (none RVCF). Context only; confirm product, units and participation.
- **Other sources:** Four CLO and 33 PVD utilisation contexts are unavailable. Do not force alternative or stale ratios.

## CTX_CREDIT — Credit category and rating (context)

- **Full CRR inputs:** 722 Application Ratings rows (Vodafone 477, Siemens 238, SoftBank 7) give 22 CRR contexts: 18 populated, 4 unavailable. Keep each application separate.
- **Competing CRRs:** Siemens CIN AEBBME035063734 has 2.1, 3.1 and N/A across three applications. No numeric direction or group rating.
- **Historical flags:** Nine open-period contexts are HISTORICAL (two Vodafone, seven Siemens). Validate version semantics.
- **Category context:** 96 Facilities/PVD category contexts; CAT-A drives SIG01 eligibility. Obtain CAT-A/B/S definitions.
