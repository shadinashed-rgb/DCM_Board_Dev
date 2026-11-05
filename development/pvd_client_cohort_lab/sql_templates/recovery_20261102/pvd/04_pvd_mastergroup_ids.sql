-- READ ONLY: run in your Starburst/Trino SQL client; no statement is submitted by this package.
-- Verify live schema, native date format and partition properties. Capture all selected columns.
-- No business materiality/product/utilisation filters. Counts are raw observations, not facilities.
-- ID-FIRST: exact supplied mastergroup values observed in joi_relationship_id.
-- No name filter. This extracts their records; identifier semantics remain a separate review.
SELECT t.* FROM "hive"."pvd_prod_wave"."pvd_omnia_drr" t
WHERE t."joi_date" >= '2026-07-01' AND t."joi_date" <= '2026-10-30'
  AND UPPER(REGEXP_REPLACE(TRIM(CAST(t."joi_relationship_id" AS VARCHAR)), '\s+', ' ')) IN ('MG001356', 'MG102229', 'MG101624');
