-- Bond Radar PORTFOLIO extraction · pvd · PROFILE (run first)
-- READ ONLY. Engine: Starburst / Trino. Copy, run, download as CSV with headers.
-- Save as: profiles/pvd_profile.csv
-- As-of 2026-11-06, window 2026-07-09 .. 2026-11-06. All clients, no client/ID/name filter.
-- Keep identifiers as text. Do not open/re-save the CSV in Excel before processing.
-- DISTINCT removes identical rows only. Nothing is summed and no conflicting value is chosen.
-- Row counts the extract would return, by snapshot/partition. Use them to choose the number of parts
-- (rows per part should stay below your Starburst download limit).
WITH base AS (
  SELECT
    t."joi_date",
    t."joi_relationship_id",
    t."joi_relationship_name",
    t."joi_key",
    t."joi_segment",
    t."joi_b_country",
    t."joi_m_lob",
    t."drr_supergroup_id",
    t."drr_supergroup_name",
    t."omn_mastergroup_name",
    t."drr_product",
    t."drr_fac_category",
    t."joi_facility_category",
    t."drr_act_limit",
    t."drr_carm_limit",
    t."drr_utils",
    t."drr_commitment",
    t."exposure_usd",
    t."drr_crr",
    t."drr_pd",
    t."month_year",
    t."etlmonth",
    t."etlmonth_drr"
  FROM "hive"."pvd_prod_wave"."pvd_omnia_drr" t
  WHERE t."joi_date" BETWEEN '2026-07-09' AND '2026-11-06'
    AND (t."etlmonth" IS NULL OR TRIM(CAST(t."etlmonth" AS VARCHAR)) = '' OR SUBSTR(REPLACE(CAST(t."etlmonth" AS VARCHAR), '-', ''), 1, 8) <= '20261106')
    AND (t."etlmonth_drr" IS NULL OR TRIM(CAST(t."etlmonth_drr" AS VARCHAR)) = '' OR SUBSTR(REPLACE(CAST(t."etlmonth_drr" AS VARCHAR), '-', ''), 1, 8) <= '20261106')
), latest AS (
  SELECT "joi_relationship_id", MAX("joi_date") AS latest_date FROM base GROUP BY "joi_relationship_id"
),
selected AS (
SELECT DISTINCT b.* FROM base b
JOIN latest l ON l."joi_relationship_id" = b."joi_relationship_id" AND l.latest_date = b."joi_date"
)
SELECT x."joi_date" AS partition_value, COUNT(*) AS rows_selected, COUNT(DISTINCT x."joi_relationship_id") AS distinct_bucket_keys
FROM selected x
GROUP BY 1
ORDER BY rows_selected DESC;
