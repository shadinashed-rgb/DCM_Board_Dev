"""Signal catalogue, definitions and findings for rule version development-2.

Single source of the text used by tools/build_package.py: the package Markdown
reports and the workbooks' Definitions and Findings sheets. The dashboard reads the
workbooks. Decisions come from the DCM meetings recorded in
../docs/MEETING_ALIGNMENT_REVIEW.md. Counts quoted in findings are checked against
the run by build_package.py.
"""

RULE_VERSION = 'development-2'
ASSESSMENT = dict(core='2026-11-03', crr='2026-11-04', export='2026-11-05')
CLIENTS = [('VODAFONE', 'MG001356'), ('Siemens Energy', 'MG102229'), ('SOFTBANK', 'MG101624')]

# id, name, kind (signal/context/excluded), coverage status, workbook
CATALOGUE = [
    ('SIG01', 'Material drawing on a Cat A bank facility', 'signal', 'partial_development_evidence', 'SIG01'),
    ('SIG02', 'New RCF, term loan or bridge (credit approval)', 'signal', 'partial_development_evidence', 'SIG02'),
    ('SIG03A', 'Swap roll on maturing debt', 'signal', 'source_missing', 'SIG03'),
    ('SIG03B', 'New pre-hedge swap enquiry', 'signal', 'source_missing', 'SIG03'),
    ('SIG04', 'KYC onboarding or signatory refresh', 'signal', 'empty_export', 'SIG04'),
    ('SIG05', 'CME call report keywords', 'excluded', 'excluded', None),
    ('SIG06', 'Financial covenant breach or pressure', 'signal', 'source_missing', 'SIG06'),
    ('SIG07', 'Rating advisory request (call reports)', 'signal', 'source_not_integrated', 'SIG07'),
    ('CTX_UTIL', 'Facility utilisation (context)', 'context', 'partial_development_evidence', 'CTX_UTIL'),
    ('CTX_CREDIT', 'Credit category and rating (context)', 'context', 'partial_development_evidence', 'CTX_CREDIT'),
]

D, M, R, U, S, X = 'Business definition', 'Meeting decision', 'Development rule', 'Unresolved', 'Source constraints', 'Missing source'

DEFINITIONS = {
    'SIG01': [
        ('Business purpose', 'A drawing on a bank facility shows the client needs cash; the first source of funding is usually the RCF, so a material drawing may precede bond refinancing.', M),
        ('Eligible facilities', 'Any Cat A bank facility: RCF, term loan, bilateral or other direct lending. The RCF label is not required. Engine: CLO REV and TERM; blank products stay ineligible (unknown).', M),
        ('Cat A eligibility', 'Facilities limit_cat = CAT-A, looked up where the CLO sub-limit ID equals the Facilities facility_id. Observed development link, not an approved cross-source identity.', R),
        ('Measure', 'Drawing = current drawn minus prior drawn for the same sub-limit, keeping the actual comparison dates and gap. An absent prior observation is unavailable.', R),
        ('Materiality', 'Drawing above EUR 50m is material. HSBC share is a lower bound (share never exceeds the whole facility); the inferred total = HSBC drawing ÷ participation share is used when a share is available (sole lender = 100%).', M),
        ('Currency', 'Non-EUR amounts are converted only with configured FX rates (none supplied); no fallback conversion.', R),
        ('Missing values', 'Blank drawn is zero only for SIG01, with current/prior flags; imputed comparisons are never assessed for materiality.', 'User decision'),
        ('Alternative drawn field', 'ag_acc_bal_drawn_sub_lim_usd is compared separately (component drawing_change_alt_usd) and never mixed with facility_drawn_amount.', R),
        ('Open definitions', 'Authoritative drawn field (LoanIQ), FX source/date, participation-share field, comparison horizon, validation of the CLO/Facilities ID link.', U),
    ],
    'SIG02': [
        ('Business purpose', 'A newly approved RCF, term loan or bridge has a high chance of being refinanced in the bond market.', M),
        ('Event date', 'Internal credit approval date from the credit team (earlier than signing).', M),
        ('Date source', 'Facilities loan_approva_dt if valid (currently a 0 placeholder); otherwise facility_creation_date as a labelled candidate; then Application Ratings approval_dt linked by credit_proposal_serial_no (same CIN preferred).', R),
        ('Recency test', 'Age = core assessment date minus event date; the 90-day inclusive lookback is a development test.', R),
        ('Ambiguity', 'Contexts with conflicting products or dates are withheld rather than resolved with arbitrary first/MAX values.', R),
        ('Open definitions', 'Confirm the linked application approval is the approval of the new facility (not a review/renewal); product dictionary for RCF / term / bridge; publishing scope (Siemens DE).', U),
    ],
    'SIG03A': [
        ('Business purpose', 'A client rolling an existing swap tied to maturing debt points to refinancing of that debt.', M),
        ('Independence', 'Treated independently of SIG03B even though both point to a potential issuance.', M),
        ('Primary input', 'Derivatives trade/booking data (FX swaps first; IRS/CCS). Not supplied.', X),
        ('Required fields', 'Client identifiers, trade id, product, trade and maturity dates, notional and currency, linked debt reference, roll/novation indicator.', 'Required contract'),
        ('Open definitions', 'Source system and owner, roll definition, linkage to maturing debt.', U),
    ],
    'SIG03B': [
        ('Business purpose', 'An enquiry about a new pre-hedge swap ahead of an issuance; FX swaps in particular indicate pre-hedging (MSS team).', M),
        ('Primary input', 'Pre-hedge / swap-pricing enquiries. The signal does not exist in markets systems today; Bloomberg chatrooms were raised as a possible source (open).', X),
        ('Required fields', 'Client identifiers, enquiry id and date, product, status, notional and currency, financing purpose.', 'Required contract'),
        ('Open definitions', 'Source, enquiry eligibility, repeated-request rules, identity route.', U),
    ],
    'SIG04': [
        ('Business purpose', 'Onboarding a new entity or refreshing KYC of signatories may precede a bond transaction.', D),
        ('Primary input', 'delta.prod_party_gda.kyc; the selected target export is valid but header-only.', 'Empty export'),
        ('Development fields', 'review_request_created_time_stamp and candidate NTB/TRG purpose codes; 90-day lookback unverified.', R),
        ('Identity and schema', 'cdd_topco_legal_name is an array; mg_parent_grid/groupguci are not automatically mastergroup IDs.', S),
        ('Open definitions', 'Known target case/entity, NTB/Trigger/Periodic/Remediation meanings, case dates, signatory coverage.', U),
    ],
    'SIG06': [
        ('Business purpose', 'A covenant breach or covenant pressure may signal a financing need, including a hybrid transaction; the originator should be alerted.', M),
        ('Covenant pressure', 'Leverage (e.g. net debt / EBITDA) within half a turn (0.5x) of the covenant maximum: >= 2.5x against 3.0x, >= 3.5x against 4.0x, >= 1.5x against 2.0x.', M),
        ('Engine rule', 'For approved financial tests with a maximum-type operator (<, <=): headroom = maximum - actual; pressure when headroom <= 0.5; breach when the compliance condition fails.', R),
        ('Primary input', 'Genuine financial covenant tests: metric, actual/final value, maximum, operator, test date, approval state. Not supplied; the file labelled covenants is Counterparty data (quarantined).', X),
        ('Utilisation', 'Utilisation above 70% is not covenant pressure; it is reported as CTX_UTIL context.', M),
        ('Open definitions', 'Covenant source, metric naming, units and operator semantics, approval states.', U),
    ],
    'SIG07': [
        ('Business purpose', 'A client asking about HSBC acting as rating advisor; rare and linked to the CME call-report signal.', M),
        ('Source', 'Call notes / call reports recorded by senior bankers after client discussions. Will not be automated in AI Markets.', M),
        ('Integration', 'CME is not integrated: MNPI handling and entitlements must be resolved (same dependency as SIG05).', X),
        ('Former inputs', 'Facilities limit_cat/advised_ind, PVD category/CRR and Application Ratings CRR are credit context (CTX_CREDIT), not SIG07 evidence.', M),
    ],
    'CTX_UTIL': [
        ('Purpose', 'Supporting context on facility usage shown beside the signals. Not a signal and not covenant pressure.', M),
        ('Calculation', 'Utilisation percent = valid utilisation / compatible approved limit x 100; values above 70% are flagged for context.', R),
        ('Compatibility', 'Numerator/denominator must share currency, units, scope, date and participation basis; otherwise unavailable.', R),
        ('No aggregation', 'No sums across sources, currencies, snapshots, parent/child limits or whole-facility versus share.', S),
    ],
    'CTX_CREDIT': [
        ('Purpose', 'Credit context: Facilities limit_cat (Cat A/B/S), advised_ind and grades, PVD category/CRR, Application Ratings CRR. Cat A also drives SIG01 eligibility.', M),
        ('Displayed CRR', 'Non-placeholder final_crr with crr_scale; previous/proposed/approved/manual/overridden kept separately; blank/N/A unavailable without fallback.', 'User decision'),
        ('Version selection', 'Latest supplied snapshot per source/country/CARM scope, then candidate effective periods; HISTORICAL can coexist with an open period.', R),
        ('Multiple ratings', 'Competing applications and multiple CRRs per CIN are kept; no MAX, averaging or numeric direction.', S),
    ],
}

COMMON_FINDINGS = [
    ('Meeting alignment', 'Rules follow the DCM meeting decisions (development-2): Cat A drawing over EUR 50m, credit approval date, SIG03A/SIG03B split, half-turn covenant pressure, call-report rating advisory, investor sales dropped.', 'Confirm each rule with its owner before setting definitions_verified.'),
    ('Scope', 'Three target mastergroups: Vodafone MG001356, Siemens Energy MG102229 and SoftBank MG101624. SIG05 and PVD sector aggregate excluded.', 'Preserve scope.'),
    ('Evidence versus alerts', '631 records are development evidence/context; business_trigger is blank on every record.', 'Define and verify business rules before confirming triggers.'),
    ('Assessment dates', 'Core assessed 3 November 2026; CRR assessed 4 November from 3 November snapshots.', 'Do not silently rebase dates to export date.'),
    ('Identity', 'CIN, GID and PVD namespaces differ. The development-2 lookups (CLO sub-limit = Facilities facility_id; serial + CIN to Application Ratings) are development links.', 'Use explicit reviewed, date-scoped mappings; keep conflicts.'),
    ('Freshness', 'PVD observation date is 30 September; daily refresh is a preference, not verified capability.', 'Show actual source dates; do not treat stale or empty data as no activity.'),
    ('Validation', '87 local tests pass (52 package, 35 engine); development-2 sample reference verified (609 core / 619 combined).', 'Use the owner-review files for business validation.'),
    ('DE publishing', 'Additional Siemens DE extraction remains deferred; DE history is shown separately.', 'Validate publishing/current selection.'),
]

FINDINGS = {
    'SIG01': [
        ('Eligible comparisons', '4 sub-limit comparisons on the default drawn field (Vodafone 2 REV, Siemens 1 REV, SoftBank 1 TERM) and 4 on the USD field.', 'Confirm the authoritative drawn field (LoanIQ).'),
        ('Default drawn field', 'facility_drawn_amount is blank on all 276 CLO rows, so every default comparison is imputed zero and not assessable for materiality.', 'Obtain drawn amounts by facility.'),
        ('USD drawn field', 'On ag_acc_bal_drawn_sub_lim_usd the Vodafone and Siemens sub-limits show no increase between 30 Oct and 2 Nov.', 'Confirm field meaning (HSBC drawn balance in USD).'),
        ('SoftBank term loan', 'TERM sub-limit 00010341075552511210201 carries USD 179.7m drawn (Cat A) but has no prior snapshot, so no increase can be computed.', 'Supply the prior snapshot.'),
        ('SoftBank USD 200m', 'Sub-limit 00010341075552607090201 is unchanged at USD 200m across snapshots and has a blank CLO product, so it is not assessed.', 'Confirm product.'),
        ('Cat A link', 'Vodafone and SoftBank sub-limits match a CAT-A Facilities record; the Siemens REV sub-limit has no matching facility_id.', 'Validate the ID link; obtain Cat A for Siemens.'),
        ('Materiality', 'No comparison is material: FX rates and participation share are not configured and the default field is blank.', 'Agree FX source/date and the participation-share field.'),
    ],
    'SIG02': [
        ('Raw grain', '105 supplied rows; 63 source/country/facility keys; 13 contexts withheld for conflicting products or dates; 50 usable.', 'Preserve product and borrower child contexts.'),
        ('Approval link', 'All 63 keys link to Application Ratings by credit_proposal_serial_no and CIN; 50 usable contexts receive an approval date. Facilities loan_approva_dt is a 0 placeholder.', 'Credit team to confirm the link.'),
        ('Approval vs creation', 'Approval equals facility_creation_date for 9 of 50; older facilities were approved weeks after creation (e.g. created 12 Apr 2005, approved 10 Jun 2005).', 'Confirm which date is the credit approval of the new facility.'),
        ('Recent candidates', '9 within 90 days of approval: seven Vodafone (17 Sep), Siemens AE FGL AED 40m (6 Oct) and SoftBank FCL 00010341075552511210201 (created 9 Jul, approved 17 Sep).', 'Confirm new-financing meaning and product eligibility.'),
        ('German history', '349 archived DE rows at 30 October are shown separately, not as current transactions.', 'Additional extraction remains deferred.'),
    ],
    'SIG03A': [('Missing source', 'No derivatives trade data supplied; no swap-roll events can be assessed. DRR FSWP/FFEX limit lines are limits, not trades.', 'Identify the derivatives trade source (FX swaps first).')],
    'SIG03B': [('Missing source', 'No pre-hedge enquiry source exists in markets systems; Bloomberg chat is an open option.', 'Decide on a source and event contract.')],
    'SIG04': [
        ('Empty target export', 'Zero supplied KYC rows with 326 native headers retained.', 'Locate a known target case through a verified identity route.'),
        ('Purpose ambiguity', 'NTB, Trigger, Periodic and Remediation meanings are unverified; a Trigger case alone is not a financing event.', 'Obtain definitions.'),
    ],
    'SIG06': [
        ('Missing covenant tests', 'No genuine financial covenant tests: earlier samples are non-financial reporting obligations and the covenants file is Counterparty data (quarantined).', 'Request net debt / EBITDA actuals, maxima and test dates.'),
        ('Rule ready', 'The half-turn pressure rule is implemented and tested (2.6x vs 3.0x = pressure; 2.4x = none; 4.0x = breach).', 'Run on the first genuine covenant extract.'),
        ('Utilisation moved', 'The five utilisation ratios above 70% are context (CTX_UTIL), not covenant pressure.', 'Do not present utilisation as covenant pressure.'),
    ],
    'SIG07': [
        ('Source not integrated', 'Rating advisory requests are only recorded in CME call reports; CME access is pending MNPI/entitlement decisions.', 'Decide on CME access (with SIG05).'),
        ('Former evidence', '118 former SIG07 records are now CTX_CREDIT context (96 Facilities/PVD category, 22 CRR).', 'Use as credit context only.'),
    ],
    'CTX_UTIL': [
        ('DRR exposures', '642 native target rows reduce to 405 candidate exposures: 57 usable ratios and 348 unavailable.', 'Preserve shared borrower lineage.'),
        ('Ratios above 70%', 'Vodafone 94.28%; Siemens 76.80% and 74.22%; SoftBank two at 100%; all 2 November; products FGTE, FCTA, FLNS (none RVCF).', 'Context only; confirm product, units and participation.'),
        ('Other sources', 'Four CLO and 33 PVD utilisation contexts are unavailable.', 'Do not force alternative or stale ratios.'),
    ],
    'CTX_CREDIT': [
        ('Full CRR inputs', '722 Application Ratings rows (Vodafone 477, Siemens 238, SoftBank 7) give 22 CRR contexts: 18 populated, 4 unavailable.', 'Keep each application separate.'),
        ('Competing CRRs', 'Siemens CIN AEBBME035063734 has 2.1, 3.1 and N/A across three applications.', 'No numeric direction or group rating.'),
        ('Historical flags', 'Nine open-period contexts are HISTORICAL (two Vodafone, seven Siemens).', 'Validate version semantics.'),
        ('Category context', '96 Facilities/PVD category contexts; CAT-A drives SIG01 eligibility.', 'Obtain CAT-A/B/S definitions.'),
    ],
}

SOURCES = {
    'SIG01': [('data/current_exports/clo_current_and_previous.csv', 'hive.clo_prod.clo_cda_contract_lvl', 276, 'Drawn amounts and comparison snapshots'),
              ('data/current_exports/facilities_current.csv', 'delta.prod_credit_and_lending_gda.facilities_limits', 105, 'Cat A lookup (limit_cat)')],
    'SIG02': [('data/current_exports/facilities_current.csv', 'delta.prod_credit_and_lending_gda.facilities_limits', 105, 'Facility contexts'),
              ('data/application_ratings_full/*_full.csv', 'delta.prod_credit_and_lending_gda.application_ratings', 722, 'Credit approval date (approval_dt)'),
              ('data/history/facilities_siemens_de_20261030.csv', 'delta.prod_credit_and_lending_gda.facilities_limits', 349, 'Historical context only')],
    'SIG03A': [('(none)', 'derivatives trade/booking data', 0, 'Source missing')],
    'SIG03B': [('(none)', 'pre-hedge enquiry / pricing requests', 0, 'Source missing')],
    'SIG04': [('data/current_exports/kyc_current.csv', 'delta.prod_party_gda.kyc', 0, 'Empty target export; native headers preserved')],
    'SIG06': [('(none)', 'financial covenant tests', 0, 'Source missing'),
              ('data/quarantine/covenants_extract_is_counterparty.csv', 'Counterparty data (mislabelled)', 167, 'Quarantined; not ingested')],
    'SIG07': [('(none)', 'CME call reports', 0, 'Not integrated (MNPI/entitlements)')],
    'CTX_UTIL': [('data/current_exports/drr_current.csv', 'delta.prod_credit_and_lending_mda.drr_facility_limits', 660, 'Utilisation and limits'),
                 ('data/current_exports/clo_current_and_previous.csv', 'hive.clo_prod.clo_cda_contract_lvl', 276, 'Utilisation (unavailable)'),
                 ('data/current_exports/pvd_current.csv', 'hive.pvd_prod_wave.pvd_omnia_drr', 143, 'Utilisation (stale, unavailable)')],
    'CTX_CREDIT': [('data/current_exports/facilities_current.csv', 'delta.prod_credit_and_lending_gda.facilities_limits', 105, 'limit_cat, advised_ind, grades'),
                   ('data/current_exports/pvd_current.csv', 'hive.pvd_prod_wave.pvd_omnia_drr', 143, 'drr_crr and categories'),
                   ('data/application_ratings_full/*_full.csv', 'delta.prod_credit_and_lending_gda.application_ratings', 722, 'CRR')],
}
