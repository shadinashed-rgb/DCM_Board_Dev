-- READ ONLY: run in your Starburst/Trino SQL client; no statement is submitted by this package.
-- Verify live schema, native date format and partition properties. Capture all selected columns.
-- No business materiality/product/utilisation filters. Counts are raw observations, not facilities.
SHOW COLUMNS FROM "hive"."prod_party_gda"."counterparty_core";

SHOW CREATE TABLE "hive"."prod_party_gda"."counterparty_core";
