-- Bond Radar PORTFOLIO extraction · covenants · PROFILE (run first)
-- READ ONLY. Engine: Starburst / Trino. Copy, run, download as CSV with headers.
-- Save as: profiles/covenants_profile.csv
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
    t."relationship_id",
    t."local_customer_id",
    t."entity_id",
    t."facility_id",
    t."covenant_id",
    t."covenant_type",
    t."covenant_sub_type",
    t."covenant_financial_derived_type",
    t."covenant_title",
    t."covenant_category_type",
    t."covenant_status",
    t."covenant_approval_status",
    t."frequency",
    t."facility_covenant_level",
    t."active_testing_id",
    t."active_testing_actual_value",
    t."active_testing_final_value",
    t."active_testing_testing_threshold_value",
    t."active_testing_testing_threshold_operator",
    t."active_testing_testing_threshold_value_2",
    t."active_testing_testing_threshold_operator_2",
    t."active_testing_approval_status",
    t."active_testing_testing_result",
    t."active_testing_final_result",
    t."active_testing_testing_due_dt",
    t."reporting_dt",
    t."last_testing_result",
    t."historic_testing_due_dt",
    t."historic_final_value",
    t."historic_final_result",
    t."next_testing_dt"
  FROM "delta"."prod_credit_and_lending_gda"."covenants" t
  WHERE t."run_date" BETWEEN '20260709' AND '20261106'
    -- Tests reported or due within the covenant lookback. Financial-type filtering happens in the engine.
    AND (t."reporting_dt" >= DATE '2025-10-02' OR t."active_testing_testing_due_dt" >= DATE '2025-10-02')
), snapshots AS (
  SELECT part_sys, part_cty, MAX("run_date") AS latest_date
  FROM (SELECT DISTINCT COALESCE("source_system_name", '~') AS part_sys, COALESCE("country_code", '~') AS part_cty, "run_date" FROM base) d
  GROUP BY part_sys, part_cty
),
selected AS (
SELECT DISTINCT b.* FROM base b
JOIN snapshots s ON s.part_sys = COALESCE(b."source_system_name", '~') AND s.part_cty = COALESCE(b."country_code", '~') AND s.latest_date = b."run_date"
)
SELECT x."covenant_type" AS partition_value, COUNT(*) AS rows_selected, COUNT(DISTINCT COALESCE(x."relationship_id", x."facility_id")) AS distinct_bucket_keys
FROM selected x
GROUP BY 1
ORDER BY rows_selected DESC;
