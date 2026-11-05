# SIG07 Application Ratings: CRR only

Decision: **4 November 2026**. Application Ratings contributes CRR context to
the rating-advisory signal in this stage. No S&P/Moody/Fitch ratings or other
Application Ratings categories/engagement fields are added by this adapter.
The existing Facilities/PVD evidence remains available in the previous run.

Use final_crr as the displayed CRR when populated and not a placeholder. Preserve
crr_scale, previous/proposed/approved/manual/overridden CRR states and source
dates separately. Do not replace a missing final_crr with zero or another state.
No CRR value or change automatically proves advisory activity.

## Data now added

The available 207 sample rows give ten candidate effective-period application
records on the 3 November snapshot: Vodafone one, Siemens seven, SoftBank two.
Nine have non-placeholder final_crr; one is unavailable. This is partial sample
coverage, not one verified rating per group. Multiple Siemens records remain
visible, and six have HISTORICAL labels despite open periods/latest-approved flags.
The version rule and cross-source CIN namespace remain development assumptions.

The new CSVs are in `analysis/sig07_crr_addition_20261104/` in the main project:
`SIG07_Application_Ratings_CRR.csv` and
`DCM_Run_003_All_Signal_Evidence_With_CRR.csv`.
The latter preserves the previous 604 evidence items and adds these ten, for 614.
Advisory business_trigger remains blank. Old source data and the old export remain
separate; Application Ratings adds only CRR fields.

## Next full-cohort extraction

These three SQLs return the verified identity, application, date/status and CRR
columns, rather than all 227 source columns. They retain the same candidate CIN
lookups and fixed run_date=20261103, with all application versions and no row cap:

| SQL | Save CSV as |
| --- | --- |
| 01_vodafone_crr.sql | application_ratings_vodafone_full.csv |
| 02_siemens_energy_crr.sql | application_ratings_siemens_energy_full.csv |
| 03_softbank_crr.sql | application_ratings_softbank_full.csv |

Transfer results into `sql/SIG07/application_ratings_full/`. If the pinned snapshot
is no longer available, confirm the source date before changing all three queries.
Preserve IDs and rating codes as text. Do not drop history at landing using only
latest_record or latest_approved_appl_flag; their scope needs source-owner checks.

## Rebuild the added CRR evidence locally

Run from the project root after transferring the full exports:

```sh
python3 pvd_client_cohort_lab/sig07_crr.py \
  --input sql/SIG07/application_ratings_full \
  --base analysis/dcm_run_003_review_20261103/DCM_Run_003_All_Signal_Evidence.csv \
  --as-of 2026-11-04 \
  --out analysis/sig07_crr_full_next
```

Choose the actual assessment date and a fresh output folder. The adapter uses
the latest supplied snapshot per source/country/CARM instance, then candidate
record periods; it never resurrects an old application after a later ineligible
snapshot. Conflicting CRRs remain separate, with multiple_crrs_for_cin flagged.
Unknown effective periods and unresolved CIN links remain unavailable. Source
rows, dates, raw placeholders, flags and identifiers are preserved in the output.
The identifier inventory is discovery evidence, not production identity approval.

This step supplements the existing seven-source refresh; it does not require
re-extracting or recomputing the other sources. No live SQL is executed locally.
