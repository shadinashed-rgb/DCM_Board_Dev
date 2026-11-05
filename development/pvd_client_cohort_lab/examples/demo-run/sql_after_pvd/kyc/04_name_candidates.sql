-- READ ONLY: run in your Starburst/Trino SQL client; no statement is submitted by this package.
-- Verify live schema, native date format and partition properties. Capture all selected columns.
-- No business materiality/product/utilisation filters. Counts are raw observations, not facilities.
-- NAME CANDIDATES ONLY: save separately as a chunk for this source; review before linking.
SELECT t.* FROM "delta"."prod_party_gda"."kyc" t
WHERE t."run_date" >= '20261001' AND t."run_date" <= '20261030'
  AND (STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."legal_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'VODAFONE') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."legal_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SIEMENS ENERGY') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."legal_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SOFTBANK') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."legal_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SOFT BANK') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(ARRAY_JOIN(t."cdd_topco_legal_name", ' '), '')), '[^A-Z0-9]+', ' ')), 'VODAFONE') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(ARRAY_JOIN(t."cdd_topco_legal_name", ' '), '')), '[^A-Z0-9]+', ' ')), 'SIEMENS ENERGY') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(ARRAY_JOIN(t."cdd_topco_legal_name", ' '), '')), '[^A-Z0-9]+', ' ')), 'SOFTBANK') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(ARRAY_JOIN(t."cdd_topco_legal_name", ' '), '')), '[^A-Z0-9]+', ' ')), 'SOFT BANK') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."mg_parent_legal_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'VODAFONE') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."mg_parent_legal_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SIEMENS ENERGY') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."mg_parent_legal_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SOFTBANK') > 0 OR
    STRPOS(TRIM(REGEXP_REPLACE(UPPER(COALESCE(CAST(t."mg_parent_legal_name" AS VARCHAR), '')), '[^A-Z0-9]+', ' ')), 'SOFT BANK') > 0);
