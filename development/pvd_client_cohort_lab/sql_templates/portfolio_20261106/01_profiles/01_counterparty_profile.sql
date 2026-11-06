-- Bond Radar PORTFOLIO extraction · counterparty · PROFILE (run first)
-- READ ONLY. Engine: Starburst / Trino. Copy, run, download as CSV with headers.
-- Save as: profiles/counterparty_profile.csv
-- As-of 2026-11-06, window 2026-07-09 .. 2026-11-06. All clients, no client/ID/name filter.
-- Keep identifiers as text. Do not open/re-save the CSV in Excel before processing.
-- DISTINCT removes identical rows only. Nothing is summed and no conflicting value is chosen.
-- Row counts the extract would return, by snapshot/partition. Use them to choose the number of parts
-- (rows per part should stay below your Starburst download limit).
WITH base AS (
  SELECT
    t."run_date",
    t."source_system_name",
    t."source_system_instance_country",
    t."customer_relationship_cin_identifier",
    t."customer_relationship_gid_identifier",
    t."customer_relationship_lifecycle_status_code",
    t."customer_relationship_segment_local_code",
    t."customer_relationship_cin_name",
    t."customer_relationship_hsbc_booking_entity_country_code",
    t."mastergroup_esr_identifier",
    t."mastergroup_name",
    t."mastergroup_lifecycle_status_code",
    t."mastergroup_business_line_code",
    t."mastergroup_designation_name",
    t."mastergroup_principal_country_code",
    t."mastergroup_industry_classification_sector_name",
    t."mastergroup_supergroup_identifier",
    t."mastergroup_supergroup_name",
    t."organisation_grid_identifier",
    t."organisation_legal_entity_lei_identifier"
  FROM "delta"."prod_party_gda"."counterparty_core" t
  WHERE t."run_date" BETWEEN '20260709' AND '20261106'
), snapshots AS (
  -- Latest two snapshots per publishing instance: latest mapping plus the one the prior CLO comparison needs.
  SELECT part, "run_date", DENSE_RANK() OVER (PARTITION BY part ORDER BY "run_date" DESC) AS snapshot_rank
  FROM (SELECT DISTINCT COALESCE("source_system_instance_country", '~') AS part, "run_date" FROM base) d
),
selected AS (
SELECT DISTINCT b.* FROM base b
JOIN snapshots s ON s.part = COALESCE(b."source_system_instance_country", '~') AND s."run_date" = b."run_date"
WHERE s.snapshot_rank <= 2
)
SELECT x."source_system_instance_country" AS partition_value, COUNT(*) AS rows_selected, COUNT(DISTINCT COALESCE(x."customer_relationship_cin_identifier", x."customer_relationship_gid_identifier")) AS distinct_bucket_keys
FROM selected x
GROUP BY 1
ORDER BY rows_selected DESC;
