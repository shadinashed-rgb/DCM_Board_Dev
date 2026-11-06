-- Bond Radar PORTFOLIO extraction · facilities · PROFILE (run first)
-- READ ONLY. Engine: Starburst / Trino. Copy, run, download as CSV with headers.
-- Save as: profiles/facilities_profile.csv
-- As-of 2026-11-06, window 2026-07-09 .. 2026-11-06. All clients, no client/ID/name filter.
-- Keep identifiers as text. Do not open/re-save the CSV in Excel before processing.
-- DISTINCT removes identical rows only. Nothing is summed and no conflicting value is chosen.
-- Row counts the extract would return, by snapshot/partition. Use them to choose the number of parts
-- (rows per part should stay below your Starburst download limit).
WITH base AS (
  SELECT
    t."run_date",
    t."source_system_name",
    t."country_code",
    t."booking_country",
    t."facility_id",
    t."facility_number",
    t."main_limit_facility_id",
    t."cin",
    t."relationship_id",
    t."customer_id",
    t."source_system_unique_id",
    t."credit_proposal_serial_no",
    t."application_serial_number",
    t."product_code",
    t."product_type",
    t."facility_purpose",
    t."limit_cat",
    t."limit_type",
    t."limit_category_type",
    t."advised_ind",
    t."facility_grade_code",
    t."facility_grade_desc",
    t."sustainable_risk_rating_impact_approved",
    t."facility_ccy",
    t."proposed_limit",
    t."previous_limit",
    t."allocated_limit_amount",
    t."commitment_ind",
    t."unconditional_cancel_ind",
    t."cancellation_ind",
    t."facility_cancelled_ind",
    t."active_facility_ind",
    t."facility_creation_date",
    t."loan_approva_dt",
    t."limit_review_dt",
    t."loan_maturity_dt",
    t."final_loan_maturity_dt",
    t."facility_expiry_dt",
    t."date_of_expiry",
    t."record_start_dt",
    t."record_end_dt",
    t."latest_record",
    t."facility_record_updated_date"
  FROM "delta"."prod_credit_and_lending_gda"."facilities_limits" t
  WHERE t."run_date" BETWEEN '20260709' AND '20261106'
), snapshots AS (
  -- Latest snapshot per source system and country: avoids losing partitions that publish later.
  SELECT part_sys, part_cty, MAX("run_date") AS latest_date
  FROM (SELECT DISTINCT COALESCE("source_system_name", '~') AS part_sys, COALESCE("country_code", '~') AS part_cty, "run_date" FROM base) d
  GROUP BY part_sys, part_cty
),
selected AS (
SELECT DISTINCT b.* FROM base b
JOIN snapshots s ON s.part_sys = COALESCE(b."source_system_name", '~') AND s.part_cty = COALESCE(b."country_code", '~') AND s.latest_date = b."run_date"
-- Versions effective at the snapshot date (open end 99991231). Development rule, overlaps are kept for conflict checks.
WHERE (TRY(date_parse(NULLIF(TRIM(b."record_start_dt"), ''), '%Y%m%d')) IS NULL OR b."record_start_dt" <= b."run_date")
  AND (TRY(date_parse(NULLIF(TRIM(b."record_end_dt"), ''), '%Y%m%d')) IS NULL OR b."record_end_dt" = '99991231' OR b."record_end_dt" >= b."run_date")
)
SELECT x."country_code" AS partition_value, COUNT(*) AS rows_selected, COUNT(DISTINCT COALESCE(x."cin", x."relationship_id", x."facility_id")) AS distinct_bucket_keys
FROM selected x
GROUP BY 1
ORDER BY rows_selected DESC;
