-- Bond Radar PORTFOLIO extraction · clo · PROFILE (run first)
-- READ ONLY. Engine: Starburst / Trino. Copy, run, download as CSV with headers.
-- Save as: profiles/clo_profile.csv
-- As-of 2026-11-06, window 2026-07-09 .. 2026-11-06. All clients, no client/ID/name filter.
-- Keep identifiers as text. Do not open/re-save the CSV in Excel before processing.
-- DISTINCT removes identical rows only. Nothing is summed and no conflicting value is chosen.
-- Row counts the extract would return, by snapshot/partition. Use them to choose the number of parts
-- (rows per part should stay below your Starburst download limit).
WITH base AS (
  SELECT
    t."run_date",
    t."source_system",
    t."mapping_system",
    t."hsbc_booking_legal_entity",
    t."sub_lim_id",
    t."rct_facility_ref",
    t."facility_id",
    t."obligor_cin",
    t."rct_gid",
    t."rct_mastergroup_id",
    t."rct_mastergroup_name",
    t."liq_gcdu_gid",
    t."liq_gcdu_mastergroup_id",
    t."liq_gcdu_mastergroup_name",
    t."local_product_type_lbs",
    t."facility_name",
    t."facility_currency",
    t."facility_limit_amount",
    t."facility_drawn_amount",
    t."facility_undrawn_amount",
    t."ag_acc_bal_drawn_sub_lim_usd",
    t."hsbc_facility_limits_gross",
    t."deal_indicator_sole_lender",
    t."primary_borrower_indicator",
    t."facility_maturity_date",
    t."facility_effective_date",
    t."rct_industry_level_1",
    t."rct_dm_country",
    t."rct_dm_region",
    t."obligor_customer_name",
    -- Group key for snapshot selection: native mastergroup, else borrower CIN/GID, else the facility itself.
    COALESCE(NULLIF(TRIM(t."rct_mastergroup_id"), ''), 'CIN:' || NULLIF(TRIM(t."obligor_cin"), ''),
             'GID:' || NULLIF(TRIM(t."rct_gid"), ''), 'FAC:' || COALESCE(t."sub_lim_id", t."rct_facility_ref", t."facility_id")) AS group_key
  FROM "hive"."clo_prod"."clo_cda_contract_lvl" t
  WHERE t."run_date" BETWEEN '20260709' AND '20261106'
    -- Any bank facility type Jerome described: revolving and term loans. Blank product kept (unknown, not excluded).
    AND (UPPER(TRIM(t."local_product_type_lbs")) IN ('REV', 'TERM') OR NULLIF(TRIM(t."local_product_type_lbs"), '') IS NULL)
), dates AS (
  SELECT DISTINCT group_key, "run_date" FROM base
), latest AS (
  SELECT group_key, MAX("run_date") AS latest_date FROM dates GROUP BY group_key
), prior AS (
  -- Prior snapshot = newest date at least 1 day(s) before the group's latest (SIG01 comparison side).
  SELECT d.group_key, MAX(d."run_date") AS prior_date
  FROM dates d JOIN latest l ON l.group_key = d.group_key
  WHERE date_parse(d."run_date", '%Y%m%d') <= date_add('day', -1, date_parse(l.latest_date, '%Y%m%d'))
  GROUP BY d.group_key
),
selected AS (
SELECT DISTINCT b.* FROM base b
JOIN latest l ON l.group_key = b.group_key
LEFT JOIN prior p ON p.group_key = b.group_key
WHERE b."run_date" = l.latest_date OR b."run_date" = p.prior_date
)
SELECT x."run_date" AS partition_value, COUNT(*) AS rows_selected, COUNT(DISTINCT x.group_key) AS distinct_bucket_keys
FROM selected x
GROUP BY 1
ORDER BY rows_selected DESC;
