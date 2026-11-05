-- READ ONLY: run in your Starburst/Trino SQL client; no statement is submitted by this package.
-- Verify live schema, native date format and partition properties. Capture all selected columns.
-- No business materiality/product/utilisation filters. Counts are raw observations, not facilities.
-- EXISTS returns each source row once even if several identifiers match.
WITH cohort(identifier_type, identifier_value, valid_from, valid_to) AS (
  VALUES
    ('PVD_RELATIONSHIP_ID', 'MG001356', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR)),
    ('PVD_RELATIONSHIP_ID', 'PVD_SUB_DEMO', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR)),
    ('PVD_RELATIONSHIP_ID', 'MG101624', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR)),
    ('PVD_RELATIONSHIP_ID', 'MG102229', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR))
)
SELECT t.*
FROM "hive"."pvd_prod_wave"."pvd_omnia_drr" t
WHERE t."joi_date" >= '2026-10-01' AND t."joi_date" <= '2026-10-30'
  AND EXISTS (SELECT 1 FROM cohort c WHERE ((c.identifier_type='PVD_RELATIONSHIP_ID' AND UPPER(REGEXP_REPLACE(TRIM(CAST(t."joi_relationship_id" AS VARCHAR)), '\s+', ' '))=c.identifier_value)) AND (c.valid_from IS NULL OR t."joi_date" >= c.valid_from) AND (c.valid_to IS NULL OR t."joi_date" <= c.valid_to));
