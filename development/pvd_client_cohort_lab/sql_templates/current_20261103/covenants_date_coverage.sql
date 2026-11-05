-- READ ONLY; copy into Starburst and export manually. No Python/database connection.
-- Save as covenants_current.csv. Keep identifiers as text; do not round in a spreadsheet.
-- Observed ID routes are discovery candidates, not verified cross-source joins.
-- SELECT DISTINCT removes identical rows only, never sums or chooses conflicting amounts.
-- Latest AVAILABLE within the bounded window; may be stale. Retain reporting/load dates.
WITH filtered AS (
  SELECT t.* FROM "delta"."prod_credit_and_lending_gda"."covenants" t
  WHERE t."run_date" BETWEEN '20260706' AND '20261103'
    AND (UPPER(TRIM(CAST(t."relationship_id" AS VARCHAR))) IN ('2020052910083'))
)
SELECT "run_date", COUNT(*) AS raw_rows FROM filtered GROUP BY "run_date" ORDER BY "run_date" DESC;
