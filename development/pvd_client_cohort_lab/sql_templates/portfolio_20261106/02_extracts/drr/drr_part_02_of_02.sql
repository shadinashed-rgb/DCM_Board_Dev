-- Bond Radar PORTFOLIO extraction · drr · part 2 of 2
-- READ ONLY. Engine: Starburst / Trino. Copy, run, download as CSV with headers.
-- Save as: drr/part_02_of_02.csv
-- As-of 2026-11-06, window 2026-07-09 .. 2026-11-06. All clients, no client/ID/name filter.
-- Keep identifiers as text. Do not open/re-save the CSV in Excel before processing.
-- DISTINCT removes identical rows only. Nothing is summed and no conflicting value is chosen.
-- Purpose: CTX_UTIL utilisation, covenant-waiver lead for SIG06
WITH base AS (
  SELECT
    t."reporting_date",
    t."run_date",
    t."source_system_name",
    t."source_system_unique_id",
    t."rpt_facility_country_code",
    t."base_entity_country",
    t."drr_mastergroup_id",
    t."gid",
    t."cin",
    t."grid",
    t."drr_customer_uid",
    t."drr_gid_uid",
    t."guci",
    t."groupguci",
    t."facility_id",
    t."drr_uid",
    t."drr_facility_uid",
    t."facility_type_code",
    t."local_facility_type",
    t."facility_category",
    t."committed_flag",
    t."unconditionally_cancellable",
    t."facility_as_parent",
    t."facility_as_child",
    t."shared_facility_flag",
    t."facility_start_date",
    t."facility_end_date",
    t."approved_limit",
    t."approved_limit_ccy",
    t."approved_limit_lcy",
    t."actual_limit",
    t."actual_limit_ccy",
    t."utilisation",
    t."utilisation_ccy",
    t."utilisation_lcy",
    t."undrawn",
    t."undrawn_ccy",
    t."advised_flag",
    t."purpose_code",
    t."covenaint_waiver_date",
    t."debt_restructure_flag",
    t."maturity_extension_date",
    COALESCE(NULLIF(TRIM(t."drr_mastergroup_id"), ''), 'GID:' || NULLIF(TRIM(t."gid"), ''), 'CIN:' || NULLIF(TRIM(t."cin"), ''),
             'FAC:' || t."facility_id") AS group_key
  FROM "delta"."prod_credit_and_lending_mda"."drr_facility_limits" t
  WHERE t."reporting_date" BETWEEN '20260709' AND '20261106' AND t."run_date" <= '20261106'
), latest AS (
  SELECT group_key, MAX("reporting_date") AS latest_date FROM base GROUP BY group_key
),
selected AS (
SELECT DISTINCT b.* FROM base b
JOIN latest l ON l.group_key = b.group_key AND l.latest_date = b."reporting_date"
)
SELECT
  x."reporting_date",
  x."run_date",
  x."source_system_name",
  x."source_system_unique_id",
  x."rpt_facility_country_code",
  x."base_entity_country",
  x."drr_mastergroup_id",
  x."gid",
  x."cin",
  x."grid",
  x."drr_customer_uid",
  x."drr_gid_uid",
  x."guci",
  x."groupguci",
  x."facility_id",
  x."drr_uid",
  x."drr_facility_uid",
  x."facility_type_code",
  x."local_facility_type",
  x."facility_category",
  x."committed_flag",
  x."unconditionally_cancellable",
  x."facility_as_parent",
  x."facility_as_child",
  x."shared_facility_flag",
  x."facility_start_date",
  x."facility_end_date",
  x."approved_limit",
  x."approved_limit_ccy",
  x."approved_limit_lcy",
  x."actual_limit",
  x."actual_limit_ccy",
  x."utilisation",
  x."utilisation_ccy",
  x."utilisation_lcy",
  x."undrawn",
  x."undrawn_ccy",
  x."advised_flag",
  x."purpose_code",
  x."covenaint_waiver_date",
  x."debt_restructure_flag",
  x."maturity_extension_date"
FROM selected x
WHERE MOD(ABS(from_big_endian_64(xxhash64(to_utf8(COALESCE(x.group_key, '~'))))), 2) = 1;
