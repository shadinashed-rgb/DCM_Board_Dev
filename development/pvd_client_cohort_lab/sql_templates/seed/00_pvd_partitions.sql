-- READ ONLY: run in your Starburst/Trino SQL client; no statement is submitted by this package.
-- Verify live schema, native date format and partition properties. Capture all selected columns.
-- No business materiality/product/utilisation filters. Counts are raw observations, not facilities.
-- Metadata only. Availability depends on the Hive connector and permissions.
-- Inspect these values before choosing source/partition dates.
SELECT portfolio, etlmonth
FROM "hive"."pvd_prod_wave"."pvd_omnia_drr$partitions"
ORDER BY etlmonth DESC, portfolio;
