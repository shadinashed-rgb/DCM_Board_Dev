-- READ ONLY: run in your Starburst/Trino SQL client; no statement is submitted by this package.
-- Verify live schema, native date format and partition properties. Capture all selected columns.
-- No business materiality/product/utilisation filters. Counts are raw observations, not facilities.
-- NAME CANDIDATES ONLY: save separately as a chunk for this source; review before linking.
SELECT t.* FROM "hive"."clo_prod"."clo_cda_contract_lvl" t
WHERE t."run_date" >= '20261001' AND t."run_date" <= '20261030'
  AND (STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."rct_mastergroup_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'VODAFONE') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."rct_mastergroup_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SIEMENS ENERGY') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."rct_mastergroup_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SOFTBANK') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."rct_mastergroup_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SOFT BANK') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."rct_group_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'VODAFONE') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."rct_group_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SIEMENS ENERGY') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."rct_group_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SOFTBANK') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."rct_group_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SOFT BANK') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."obligor_customer_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'VODAFONE') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."obligor_customer_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SIEMENS ENERGY') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."obligor_customer_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SOFTBANK') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."obligor_customer_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SOFT BANK') > 0);
