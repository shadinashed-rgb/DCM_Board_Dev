-- Bond Radar PORTFOLIO extraction · application_ratings · PROFILE (run first)
-- READ ONLY. Engine: Starburst / Trino. Copy, run, download as CSV with headers.
-- Save as: profiles/application_ratings_profile.csv
-- As-of 2026-11-06, window 2026-07-09 .. 2026-11-06. All clients, no client/ID/name filter.
-- Keep identifiers as text. Do not open/re-save the CSV in Excel before processing.
-- DISTINCT removes identical rows only. Nothing is summed and no conflicting value is chosen.
-- Row counts the extract would return, by snapshot/partition. Use them to choose the number of parts
-- (rows per part should stay below your Starburst download limit).
WITH base AS (
  SELECT
    t."source_system_unique_id",
    t."source_system_name",
    t."country_code",
    t."carm_instance",
    t."branch_code",
    t."cin",
    t."customer_id",
    t."relationship_id",
    t."credit_proposal_serial_no",
    t."mastergroup_name",
    t."customer_name",
    t."run_date",
    t."record_start_dt",
    t."record_end_dt",
    t."latest_record",
    t."latest_approved_appl_flag",
    t."app_status",
    t."approval_dt",
    t."assessment_creation_dt",
    t."assessment_approval_dt",
    t."crr_scale",
    t."final_crr",
    t."previous_crr",
    t."proposed_crr",
    t."approved_crr",
    t."proposed_manual_crr",
    t."overriden_crr",
    t."crr_prior_ovrd",
    t."crr_post_ovrd",
    t."model_crr"
  FROM "delta"."prod_credit_and_lending_gda"."application_ratings" t
  WHERE t."run_date" BETWEEN '20260709' AND '20261106'
), snapshots AS (
  -- Latest snapshot per source / country / CARM instance (the CRR adapter applies the same rule).
  SELECT part_sys, part_cty, part_carm, MAX("run_date") AS latest_date
  FROM (SELECT DISTINCT COALESCE("source_system_name", '~') AS part_sys, COALESCE("country_code", '~') AS part_cty,
                        COALESCE("carm_instance", '~') AS part_carm, "run_date" FROM base) d
  GROUP BY part_sys, part_cty, part_carm
),
selected AS (
SELECT DISTINCT b.* FROM base b
JOIN snapshots s ON s.part_sys = COALESCE(b."source_system_name", '~') AND s.part_cty = COALESCE(b."country_code", '~')
                AND s.part_carm = COALESCE(b."carm_instance", '~') AND s.latest_date = b."run_date"
-- Keep (a) applications effective at the snapshot (CRR context) and
--      (b) any application approved within the approval lookback (SIG02 credit approval dates).
WHERE ((TRY(date_parse(NULLIF(TRIM(b."record_start_dt"), ''), '%Y%m%d')) IS NULL OR b."record_start_dt" <= b."run_date")
       AND (TRY(date_parse(NULLIF(TRIM(b."record_end_dt"), ''), '%Y%m%d')) IS NULL OR b."record_end_dt" = '99991231' OR b."record_end_dt" >= b."run_date"))
   OR TRY(date_parse(NULLIF(TRIM(b."approval_dt"), ''), '%Y%m%d')) >= DATE '2025-10-02'
)
SELECT x."country_code" AS partition_value, COUNT(*) AS rows_selected, COUNT(DISTINCT x."cin") AS distinct_bucket_keys
FROM selected x
GROUP BY 1
ORDER BY rows_selected DESC;
