# Bond Radar workspace conventions

Read START_HERE.md and PROJECT_STATE.md before making changes. This is the continuing project, not a greenfield rewrite. Explicit user instructions take precedence. Respect planning/question turns that say not to change code/files. Use clear sequential instructions, exact filenames and fresh output folders.

## Active implementation and checks

- Active package: pvd_client_cohort_lab. Python 3.10+ standard library and SQLite. No network/database connection is required for local processing.
- Portable combined reference: `python3 -B run_reference.py --out runs/reference_001 --test-observed-links --verify-reference` (development-2 expectations; development-1 kept in REFERENCE_EXPECTATIONS_development-1.json). Use a fresh output path. Full run: add `--ratings-input data/application_ratings_full`, then `tools/review_run.py <run>`.
- Tests: `python3 -B -m unittest discover -s pvd_client_cohort_lab/tests -q` and `python3 -B -m unittest discover -s pvd_client_cohort_lab/engine/tests -q`.
- The opt-in observed-link flag reproduces bounded test assumptions; never describe those as production approvals. The older refresh CLI supports genuinely reviewed mappings with `--approved`.
- SQL is copied manually into Starburst by the user. Do not build credential handling or automatic query submission unless asked.
- Keep raw CSVs and archived evidence unchanged. New rounds go in separate folders with submitted SQL, source date, export time, scope, row-limit status and any error recorded. Preserve headers in empty exports and IDs as strings.
- MANIFEST.json describes the shipped snapshot. Intentional edits will change its integrity result; retain the original manifest and record new development separately. New untracked outputs are ignored by the verifier.

## Decisions that must survive

- Targets: MG001356 VODAFONE; MG102229 Siemens Energy; MG101624 SOFTBANK. SIG05 and PVD sector aggregate are excluded from active scope.
- SIG01 only: blank/missing drawn amount becomes zero with current/prior flags. Invalid numeric values and absent prior observations remain unavailable. Do not propagate this imputation to utilisation or ratings.
- Counterparty location is `delta.prod_party_gda.counterparty_core`, not Hive. The old CLO/Counterparty handover is a matching reference, not the solution to adopt.
- Preserve valid original CLO mastergroups; use point-in-time CIN/GID mapping, keep conflicts, and fill missing groups only from a unique combined candidate under explicit assumptions. No arbitrary first/MAX mapping or transitive group expansion.
- PVD-first identity discovery is the user's preference. joi_key, relationship and supergroup IDs have distinct namespaces; no inferred CIN/GID from appearance. Names are review clues only. Facility IDs are not universally interchangeable across sources/countries.
- Latest selection must respect publishing grain, dates, history and scope. A global max date can lose Siemens DE Facilities. HISTORICAL labels can coexist with effective open periods; do not filter CURRENT only without validation.
- Supplied `covenants_extract.csv` in historical DCM_Run_003 is Counterparty data. Quarantine it; do not ingest or infer covenant breaches from it. Genuine financial covenants are missing.
- **DCM meeting decisions (development-2, 5 November 2026)** — see ../docs/MEETING_ALIGNMENT_REVIEW.md:
  - **SIG01** = any drawing over EUR 50m on any **Cat A** bank facility (RCF, term loan, bilateral). Consider HSBC share and the inferred total (÷ participation share). Convert currency only with configured FX rates. Cat A comes from Facilities `limit_cat` via a development facility-ID link.
  - **SIG02** event date = internal **credit approval date** (Application Ratings `approval_dt` via `credit_proposal_serial_no`); `facility_creation_date` is a labelled candidate only.
  - **SIG03** is two independent signals: **SIG03A** swap roll on maturing debt, **SIG03B** new pre-hedge swap enquiry (FX swaps first).
  - **SIG06** = financial covenant breach or **pressure** (leverage within 0.5x of the covenant maximum). Utilisation is `CTX_UTIL` context, never covenant pressure.
  - **SIG07** rating advisory is sourced from **call reports** (CME, not integrated). Facilities/PVD category fields and Application Ratings CRR are `CTX_CREDIT` context.
  - The investor-sales count is dropped.
- CTX_UTIL keeps the strict >70% test only for compatible valid numerator/denominator currency, units, scope and date. No missing-as-zero; no sums across sources, currencies, snapshots or parent/child limits.
- CRR (CTX_CREDIT) handling: preserve final_crr/scale and other CRR states separately. Missing/N/A is unavailable, not zero or a fallback. No numeric CRR direction without definitions.
- Local Application Ratings samples contain 207 rows, not the profiled full 722. External ratings are not uniformly absent: alternate CRA fields hold two historical Siemens records. These are excluded from the current CRR-only adapter.
- The 631 development-2 records (626 in development-1) are evidence, not confirmed alerts. All business triggers remain unverified until a rule's `definitions_verified` flag is set after owner confirmation. Empty/missing data is not negative client activity.
- In the git repository raw inputs are not committed; restore them with `tools/extract_inputs.py` from the archived zip.

For future HTML, use hsbc-house-style.md and the copied style skill assets; historical diagrams can lag the data decisions. Do not adopt legacy code as the active engine. No instructions here require an approval pause for routine authorized local development.
