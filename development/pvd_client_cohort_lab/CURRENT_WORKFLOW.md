# Current extraction and signal testing, 3 November 2026

**Current Application Ratings contribution:** use the [CRR-only workflow](sql_templates/sig07_crr_20261104/README.md)
and sig07_crr.py to add CRR context to the consolidated export. This supplements
the seven-source process below; external ratings are not added by that step.

**4 November SIG07 addition:** Application Ratings is another candidate source.
Use the separate [schema/sample guide](sql_templates/sig07_application_ratings_20261104/README.md)
for `delta.prod_credit_and_lending_gda.application_ratings`. Keep its discovery
samples separate from the seven-source round below until fields/keys/dates are
verified. Existing SIG07 Facilities/PVD context remains in scope.

Use this workflow for the next round. The older recovery instructions describe
previous rounds. Targets remain Vodafone MG001356, Siemens Energy MG102229 and
SoftBank MG101624. You execute SQL manually in Starburst and transfer CSVs;
Python only processes local files and never connects to Starburst.

## 1 Run the new SQL in Starburst

Open **`sql_templates/current_20261103/`**. Run each source's `_schema.sql`
statements separately to check columns/access, then its `_extract.sql`.
Counterparty now uses **delta.prod_party_gda.counterparty_core**, as instructed.
The package has not verified live access, columns or date formats. Keep schema
errors rather than guessing replacement columns. Date-coverage SQL is included
for empty or stale results.

| SQL file | Save data CSV as | Purpose |
| --- | --- | --- |
| `counterparty_extract.sql` | `counterparty_current.csv` | CLO enrichment |
| `clo_extract.sql` | `clo_current_and_previous.csv` | SIG01 and SIG06 |
| `drr_extract.sql` | `drr_current.csv` | SIG06 |
| `facilities_extract.sql` | `facilities_current.csv` | SIG02 and SIG07 |
| `pvd_extract.sql` | `pvd_current.csv` | SIG06 and SIG07 |
| `kyc_extract.sql` | `kyc_current.csv` | SIG04 |
| `covenants_extract.sql` | `covenants_current.csv` | SIG06 covenant discovery |

Keep headers for empty results. Download original CSVs directly and preserve IDs
as text. Opening/resaving in a spreadsheet can round long facility IDs; casting
an already rounded value to text cannot recover the original digits.

The search window is 6 July–3 November 2026, but only selected latest snapshots
are returned. CLO keeps its latest two available group dates. Counterparty keeps
the latest snapshot plus snapshots preceding those CLO dates. Other sources
keep one latest snapshot per explicit group, or across the cohort export when
there is no verified group field. All candidate attributes are retained in this
round; reducing daily snapshots and old versions controls the main row expansion.
No arbitrary row limit, amount threshold or speculative product filter is applied.

PVD uses the exact supplied MG values in its native relationship field. Names and
supergroups do not expand the cohort. Observed CIN/GID and covenant relationship
lookups are discovery routes, not approvals of shared namespaces. Counterparty
lookups preserve conflicting/non-target group mappings found through CIN/GID.

## 2 Transfer only the new data CSVs

Put them in this new folder inside the package:

```text
pvd_client_cohort_lab/starburst_exports/round_005/
```

Keep schema, error and date-profile exports separately. Do not mix old round_002
or round_003 data into this folder. Missing/empty results remain unresolved
coverage, not proof of no client activity.

## 3 Run one local command

From inside `pvd_client_cohort_lab`:

```sh
python3 refresh.py process \
  --input starburst_exports/round_005 \
  --out runs/round_005 \
  --as-of 2026-11-03 \
  --test-observed-links
```

Use the actual assessment date when running later; choose a new output name if
round_005 already exists. Python 3.10+ and its standard library are sufficient.

`--test-observed-links` explicitly enables bounded development associations:
Facilities/KYC CINs must link to exactly one target group in the supplied
native-group CLO/DRR/Counterparty rows. Facilities also requires source/country
scope. PVD permits exact supplied MG values in its native relationship field.
Associations are restricted to the target source and observed date, recorded in
`test_identifiers.csv` with their assumptions. Conflicting CIN links remain
unresolved. Names and ID shapes are never approved. These are test assumptions,
not production identity approvals or proof of historical legal membership.
Omit the option for review-only matching, or pass a genuinely reviewed mapping
file with `--approved path/to/file.csv`. Covenant namespace links are not
automatically approved.

For CLO rows with missing/invalid original group IDs, this test option also allows
one combined Counterparty CIN/GID group at the latest per-key mapping date no
later than the CLO observation. It uses the existing, still-unverified lifecycle
settings and retains association/facility scope. A valid original group is never
overwritten. All Counterparty reference rows, including non-target/contradictory
mappings, reach the signal engine so conflicts are not hidden by cohort filtering.

## 4 Inspect the results

- `runs/round_005/current_selection.csv`: selected dates, raw/retained rows,
  version/duplicate reductions, scientific IDs and shared-facility counts.
- `runs/round_005/cohort/REPORT.md`: coverage by client and source.
- `runs/round_005/signals/results/exports/cohort_signal_evidence.csv`:
  candidate measures, imputation flags, reasons, source dates and group lineage.

Raw observations remain in `imported/`; `current_inputs/` is a separate selected
view. Error outcomes remain distinguishable from empty data. The 30-day freshness
setting is a configurable development check, not an agreed business SLA. Latest
available snapshots may be stale.

## Rules and interpretation

- **development-2 (5 November 2026):** the rules below are updated by the DCM
  meeting decisions in `../../docs/MEETING_ALIGNMENT_REVIEW.md`. The engine config
  (`engine/config.json`) and run profile (`profiles/current_signals_20261105_dev2.json`)
  encode them. The previous profile `current_signals_20261103.json` is development-1
  history and is not loadable by the development-2 engine.
- **SIG01:** any drawing above EUR 50m on any Cat A bank facility (CLO `REV` and
  `TERM`; Cat A from Facilities `limit_cat` via a facility-ID match). HSBC share is
  a lower bound; the inferred total is used when a participation share exists; FX
  only from configured rates. A separate comparison runs on
  `ag_acc_bal_drawn_sub_lim_usd`. Blank/missing drawn amounts are zero, with current/prior imputation
  flags. Invalid numbers and absent previous observations remain unavailable.
  Only current-snapshot facilities produce evidence; the earlier CLO snapshot
  supports comparison. Its actual date gap is recorded, not assumed to be an
  agreed comparison period. Threshold, participation and FX rules remain open.
  An imputed zero does not establish actual zero borrowing. SIG06 does not
  inherit zero imputation.
- **SIG02:** Facilities versions must cover the latest snapshot date using
  `record_start_dt`/`record_end_dt`, with `99991231` open-ended. Missing or
  unparseable bounds and overlapping versions remain for review. Do not select
  solely on `latest_record=CURRENT`: 13 open-ended sample rows are HISTORICAL.
  This effective-period rule and creation/product meanings need validation.
  The event date is the credit approval date: `loan_approva_dt` if valid, otherwise
  `facility_creation_date` as a labelled candidate. Then `alignment.py` attaches
  the Application Ratings `approval_dt` via `credit_proposal_serial_no`.
- **SIG03A / SIG03B:** swap roll on maturing debt / new pre-hedge enquiry. There is
  no source, so the assessment is unavailable.
- **SIG06:** financial covenant breach or pressure (leverage within 0.5x of the
  covenant maximum). Utilisation evidence is emitted as `CTX_UTIL` context. For
  utilisation, DRR UID is a candidate internal exposure key, never a cross-source
  facility key. Consolidate shared borrower associations only when all
  non-association attributes agree; conflicts withhold the metric. Without a UID,
  scientific-notation facility IDs cannot establish identity. Missing currencies
  and zero denominators remain unavailable. No totals across dates, currencies,
  overlapping sources or parent/child limits are computed. Covenant evidence
  remains separate from utilisation pressure.
- **SIG07:** rating advisory is sourced from CME call reports (not integrated).
  Facilities `limit_cat`/`advised_ind` and PVD category/CRR fields, plus
  Application Ratings CRR, are emitted as `CTX_CREDIT` context. CAT-A feeds the
  SIG01 eligibility filter. PVD's relationship/key grain and amounts still require
  validation.

## Regenerate for a later date or identifier inventory

The delivered pack already includes observed IDs from the supplied review,
DRR and Facilities files. Example for a later round:

```sh
python3 refresh.py sql \
  --identifiers runs/round_005/cohort/identifier_review.csv \
  --as-of 2026-11-10 \
  --out generated_sql/current_20261110
```

Choose the actual date. Add another `--identifiers` argument for a raw Facilities
file if further covenant relationship discovery is needed. Generation writes
SQL only and never overwrites an existing pack.
