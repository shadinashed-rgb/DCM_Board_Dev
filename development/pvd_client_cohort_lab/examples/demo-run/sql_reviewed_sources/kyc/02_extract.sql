-- READ ONLY: run in your Starburst/Trino SQL client; no statement is submitted by this package.
-- Verify live schema, native date format and partition properties. Capture all selected columns.
-- No business materiality/product/utilisation filters. Counts are raw observations, not facilities.
-- EXISTS returns each source row once even if several identifiers match.
WITH cohort(identifier_type, identifier_value, valid_from, valid_to) AS (
  VALUES
    ('CIN', '00000001', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR)),
    ('CIN', '00000001', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR)),
    ('CIN', '00000001', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR)),
    ('CIN', '00000001', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR)),
    ('CIN', '00000003', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR)),
    ('CIN', '00000003', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR)),
    ('CIN', '00000003', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR)),
    ('CIN', '00000003', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR)),
    ('CIN', '00000002', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR)),
    ('CIN', '00000002', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR)),
    ('CIN', '00000002', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR)),
    ('CIN', '00000002', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR))
)
SELECT t.*
FROM "delta"."prod_party_gda"."kyc" t
WHERE t."run_date" >= '20261001' AND t."run_date" <= '20261030'
  AND EXISTS (SELECT 1 FROM cohort c WHERE ((c.identifier_type='CIN' AND UPPER(REGEXP_REPLACE(TRIM(CAST(t."cin" AS VARCHAR)), '\s+', ' '))=c.identifier_value)) AND (c.valid_from IS NULL OR t."run_date" >= c.valid_from) AND (c.valid_to IS NULL OR t."run_date" <= c.valid_to));
