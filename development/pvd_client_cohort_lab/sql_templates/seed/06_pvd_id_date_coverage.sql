-- READ ONLY: run in your Starburst/Trino SQL client; no statement is submitted by this package.
-- Verify live schema, native date format and partition properties. Capture all selected columns.
-- No business materiality/product/utilisation filters. Counts are raw observations, not facilities.
SELECT t.joi_relationship_id, t.joi_date, COUNT(*) AS raw_rows
FROM "hive"."pvd_prod_wave"."pvd_omnia_drr" t
WHERE t."joi_date" >= '2026-10-01' AND t."joi_date" <= '2026-10-30'
  AND UPPER(REGEXP_REPLACE(TRIM(CAST(t."joi_relationship_id" AS VARCHAR)), '\s+', ' ')) IN ('MG001356', 'MG102229', 'MG101624')
GROUP BY t.joi_relationship_id, t.joi_date
ORDER BY t.joi_relationship_id, t.joi_date;
