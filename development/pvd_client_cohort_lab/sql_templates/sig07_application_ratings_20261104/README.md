# SIG07 application ratings samples

Source: **delta.prod_credit_and_lending_gda.application_ratings**.
Added as a candidate on **4 November 2026** alongside Facilities Limits and PVD.
The user reports S&P, CRR and other rating information; live field names, grain,
rating scales, client keys and advisory meaning have not yet been inspected.

Targets: Vodafone **MG001356**, Siemens Energy **MG102229**, SoftBank **MG101624**.
This pack uses the native group anchors plus 365 identifier candidates from the
DCM_Run_003 cohort review. It does not search client names or infer a CIN from ID
shape. Candidate CIN/GID, relationship and application/proposal serial routes
preserve their roles and provenance in client_identifier_candidates.csv.
They are discovery lookups, not approved cross-source joins or legal membership.

## Run these steps in Starburst

1. Run **01_columns.sql**. Save the result as **application_ratings_columns.csv**.
2. Run **02_table_definition.sql** separately. Save as
   **application_ratings_table_definition.csv**. Check the partition properties
   and the native source-date format before data extraction.
3. Run **03_generate_client_queries.sql**. It reads information_schema only and
   returns **three rows**, one per client. Save those results as
   **application_ratings_query_plan.csv**. It does not execute the sample SQL.
4. For each client whose plan_status is **candidate_sample_sql_ready**, copy
   the full **sample_sql** cell into a new Starburst query and run it. Save using
   the exact sample filename below. Copy the **profile_sql** cell and run that
   separately, saving its profile filename. Download the original CSVs directly;
   preserve identifiers as text, including leading zeros.

| Client | Save sample_sql result as | Save profile_sql result as |
| --- | --- | --- |
| MG001356 Vodafone | application_ratings_vodafone.csv | application_ratings_vodafone_profile.csv |
| MG102229 Siemens Energy | application_ratings_siemens_energy.csv | application_ratings_siemens_energy_profile.csv |
| MG101624 SoftBank | application_ratings_softbank.csv | application_ratings_softbank_profile.csv |

**04_rating_column_inventory.sql** is an optional metadata-only view of the
rating/application/date/status fields for review.

Transfer the files to this separate discovery folder inside the package:

```text
starburst_exports/sig07_application_ratings_20261104/
```

The new source is registered for SIG07 investigation; its schema/key/date contract
is not yet wired into the existing seven-source refresh.py process or the
604-row signal evidence export. Keep these samples in their discovery folder
until the returned schema and identifiers have been reviewed.

## What the generated queries do

- Use **only scalar identifier columns actually found in the live metadata**.
  Column-role names/synonyms are candidate clues; a match does not prove namespace
  equivalence. Generic customer_id and arbitrary application_id are not assumed
  to mean CIN or a proposal serial number.
- Prefer group/CIN/GID routes where available. Candidate relationship/proposal
  serial routes are used only when that client has no recognised primary route;
  check their source/country namespace and collisions before assigning a client.
- Bound source snapshot observations to **7 July–4 November 2026**. Recognised
  observation candidates are run_date, reporting_date, as_of_date, snapshot_date
  and data_as_of_date. Rating-effective/approval dates are preserved, not substituted
  for snapshot dates. The generated date conversion supports compact YYYYMMDD
  and ISO YYYY-MM-DD forms; verify the actual values and partition predicate.
- Where a recognised rating-type/provider column exists, return up to **25 rows
  per observed type/provider combination per client**, newest snapshot dates first.
  This prevents a common type from occupying the entire sample. With no recognised
  type/provider column, return up to **100 rows per client**, retaining all wide
  S&P/CRR/other columns through t.*. A row cap is not a completeness guarantee.
- Produce **uncapped type/date counts** within the same lookup/window. Use those
  profiles to identify types or dates that the sample does not fully represent.
- Retain multiple rating types/providers/history, statuses and source IDs. Do not
  deduplicate solely on application or facility ID, choose MAX(rating), compare
  internal CRR directly with S&P scales, or filter to a presumed advisory category.
- Keep original source group columns, including contradictions found by other ID
  routes. Per-client filenames identify lookup candidates, not confirmed assignments.

The date conversion may prevent native partition pushdown. LIMIT/ranking limits
downloaded rows, not necessarily scanned data. Use the SHOW CREATE output to add
verified native partition bounds if required by the connector.

## If a plan is blocked

- **schema_not_visible:** capture SHOW/access errors or the column export.
- **identifier_bridge_required:** the source has no recognised matching fields
  for that client. Return the column list so we can establish a source-specific
  application/customer bridge. Do not substitute a similar-looking ID.
- **snapshot_date_column_required:** return the schema/date definitions before
  assuming a rating event date is a dataset observation date.

A zero-row sample remains unresolved coverage. Return the schema, query plan,
profiles and samples together so failed access and empty results stay distinct.

## How we will compare SIG07 sources

Check client coverage, key stability, source/effective/approval dates, actual vs
proposed ratings, type/provider definitions, version/repetition grain, history and
whether a known advisory engagement is explicitly recorded. S&P/CRR rating data
can be useful rating context without identifying an advisory service. Keep this
source alongside limit_cat and PVD until those checks determine the best fit.

## Validation and regeneration

Metadata and returned sample/profile SQL were executed locally with SQLite
Trino-function adapters on synthetic schemas/data, including S&P/CRR type quotas,
all three clients, date bounds, wide ratings, unsupported arrays, escaped IDs,
missing schema/keys/dates and contradictory native groups. This is not live
Starburst execution, permission verification or approval of rating semantics.

The generator uses documented Trino [array functions](https://trino.io/docs/current/functions/array.html),
[aggregates](https://trino.io/docs/current/functions/aggregate.html) and
[string functions](https://trino.io/docs/current/functions/string.html).

To regenerate from an updated local cohort, run from inside pvd_client_cohort_lab:

```sh
python3 application_ratings_samples.py \
  --cohort ../analysis/dcm_run_003_review_20261103/local_test/cohort \
  --as-of 2026-11-04 \
  --out generated_sql/sig07_application_ratings_next
```

Choose a fresh output folder and the actual assessment date. This command only
writes metadata/sample-plan SQL and the identifier inventory; it does not query
Starburst. The delivered SQL is already prepared, so regeneration is optional.
