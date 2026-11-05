-- READ ONLY: run in your Starburst/Trino SQL client; no statement is submitted by this package.
-- Verify live schema, native date format and partition properties. Capture all selected columns.
-- No business materiality/product/utilisation filters. Counts are raw observations, not facilities.
SELECT t.joi_date, COUNT(*) AS raw_rows
FROM "hive"."pvd_prod_wave"."pvd_omnia_drr" t
WHERE t."joi_date" >= '2026-07-01' AND t."joi_date" <= '2026-10-30'
  AND (UPPER(REGEXP_REPLACE(TRIM(CAST(t."joi_relationship_id" AS VARCHAR)), '\s+', ' ')) IN ('MG001356', 'MG102229', 'MG101624') OR UPPER(REGEXP_REPLACE(TRIM(CAST(t."drr_supergroup_id" AS VARCHAR)), '\s+', ' ')) IN ('MG001356', 'MG102229', 'MG101624') OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."joi_relationship_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'VODAFONE') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."joi_relationship_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SIEMENS ENERGY') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."joi_relationship_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SOFTBANK') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."joi_relationship_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SOFT BANK') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."omn_mastergroup_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'VODAFONE') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."omn_mastergroup_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SIEMENS ENERGY') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."omn_mastergroup_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SOFTBANK') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."omn_mastergroup_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SOFT BANK') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."drr_supergroup_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'VODAFONE') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."drr_supergroup_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SIEMENS ENERGY') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."drr_supergroup_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SOFTBANK') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."drr_supergroup_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SOFT BANK') > 0)
GROUP BY t.joi_date ORDER BY t.joi_date;
