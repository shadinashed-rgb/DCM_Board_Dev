-- READ ONLY; copy into Starburst and export manually. No Python/database connection.
-- Save as pvd_current.csv. Keep identifiers as text; do not round in a spreadsheet.
-- Observed ID routes are discovery candidates, not verified cross-source joins.
-- SELECT DISTINCT removes identical rows only, never sums or chooses conflicting amounts.
-- Latest AVAILABLE within the bounded window; may be stale. Retain reporting/load dates.
WITH filtered AS (
  SELECT t.* FROM "hive"."pvd_prod_wave"."pvd_omnia_drr" t
  WHERE t."joi_date" BETWEEN '2026-07-06' AND '2026-11-03'
    AND (UPPER(TRIM(CAST(t."joi_relationship_id" AS VARCHAR))) IN ('MG001356', 'MG101624', 'MG102229'))
    AND (t.etlmonth IS NULL OR TRIM(CAST(t.etlmonth AS VARCHAR)) = '' OR SUBSTR(REPLACE(CAST(t.etlmonth AS VARCHAR), '-', ''), 1, 8) <= '20261103')
    AND (t.etlmonth_drr IS NULL OR TRIM(CAST(t.etlmonth_drr AS VARCHAR)) = '' OR SUBSTR(REPLACE(CAST(t.etlmonth_drr AS VARCHAR), '-', ''), 1, 8) <= '20261103')
)
SELECT "joi_date", COUNT(*) AS raw_rows FROM filtered GROUP BY "joi_date" ORDER BY "joi_date" DESC;
