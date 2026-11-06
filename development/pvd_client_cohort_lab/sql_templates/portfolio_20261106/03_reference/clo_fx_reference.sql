-- Bond Radar PORTFOLIO extraction · CLO FX reference (optional, for the SIG01 EUR 50m test)
-- READ ONLY. Engine: Starburst / Trino. Copy, run, download as CSV with headers.
-- Save as: reference/clo_fx_reference.csv
-- As-of 2026-11-06, window 2026-07-09 .. 2026-11-06. All clients, no client/ID/name filter.
-- Keep identifiers as text. Do not open/re-save the CSV in Excel before processing.
-- DISTINCT removes identical rows only. Nothing is summed and no conflicting value is chosen.
-- Median of CLO instrument_currency_fx_to_usd by currency and snapshot. UNVALIDATED as an FX source:
-- the field is known to be dirty, which is why the median (not max) is used and min/max/count are kept.
SELECT t."run_date", t."facility_currency" AS currency, COUNT(*) AS rows_with_rate,
       approx_percentile(TRY_CAST(t."instrument_currency_fx_to_usd" AS double), 0.5) AS fx_to_usd_median,
       MIN(TRY_CAST(t."instrument_currency_fx_to_usd" AS double)) AS fx_to_usd_min,
       MAX(TRY_CAST(t."instrument_currency_fx_to_usd" AS double)) AS fx_to_usd_max
FROM "hive"."clo_prod"."clo_cda_contract_lvl" t
WHERE t."run_date" BETWEEN '20260709' AND '20261106'
  AND TRY_CAST(t."instrument_currency_fx_to_usd" AS double) > 0
GROUP BY t."run_date", t."facility_currency"
ORDER BY t."run_date" DESC, currency;
