-- Bond Radar · DISCOVERY of sources still missing for SIG03A, SIG03B, SIG06, SIG07 and SIG01 (LoanIQ).
-- READ ONLY, metadata only. Run each statement separately and save each result as discovery/<file>.csv.
-- No row can mean "not found" OR "no metadata permission", it never proves absence.

-- 1. Tables by name (save as discovery/tables_by_name.csv)
SELECT table_catalog, table_schema, table_name, table_type FROM "delta".information_schema.tables
WHERE table_schema <> 'information_schema' AND (lower(table_name) LIKE '%swap%' OR lower(table_name) LIKE '%deriv%' OR lower(table_name) LIKE '%otc%' OR lower(table_name) LIKE '%fx%trade%' OR lower(table_name) LIKE '%hedge%' OR lower(table_name) LIKE '%pricing%request%' OR lower(table_name) LIKE '%rfq%' OR lower(table_name) LIKE '%enquir%' OR lower(table_name) LIKE '%inquir%' OR lower(table_name) LIKE '%covenant%' OR lower(table_name) LIKE '%loaniq%' OR lower(table_name) LIKE '%loan_iq%' OR lower(table_name) LIKE '%liq%drawdown%' OR lower(table_name) LIKE '%drawdown%' OR lower(table_name) LIKE '%participation%' OR lower(table_name) LIKE '%syndicat%' OR lower(table_name) LIKE '%call%report%' OR lower(table_name) LIKE '%cme%' OR lower(table_name) LIKE '%call%note%' OR lower(table_name) LIKE '%rating%advis%')
UNION ALL
SELECT table_catalog, table_schema, table_name, table_type FROM "hive".information_schema.tables
WHERE table_schema <> 'information_schema' AND (lower(table_name) LIKE '%swap%' OR lower(table_name) LIKE '%deriv%' OR lower(table_name) LIKE '%otc%' OR lower(table_name) LIKE '%fx%trade%' OR lower(table_name) LIKE '%hedge%' OR lower(table_name) LIKE '%pricing%request%' OR lower(table_name) LIKE '%rfq%' OR lower(table_name) LIKE '%enquir%' OR lower(table_name) LIKE '%inquir%' OR lower(table_name) LIKE '%covenant%' OR lower(table_name) LIKE '%loaniq%' OR lower(table_name) LIKE '%loan_iq%' OR lower(table_name) LIKE '%liq%drawdown%' OR lower(table_name) LIKE '%drawdown%' OR lower(table_name) LIKE '%participation%' OR lower(table_name) LIKE '%syndicat%' OR lower(table_name) LIKE '%call%report%' OR lower(table_name) LIKE '%cme%' OR lower(table_name) LIKE '%call%note%' OR lower(table_name) LIKE '%rating%advis%')
ORDER BY 1, 2, 3;

-- 2. Columns by name (save as discovery/columns_by_name.csv)
SELECT table_catalog, table_schema, table_name, column_name, data_type FROM "delta".information_schema.columns
WHERE table_schema <> 'information_schema' AND (lower(column_name) LIKE '%notional%' OR lower(column_name) LIKE '%swap%' OR lower(column_name) LIKE '%hedge%' OR lower(column_name) LIKE '%trade_date%' OR lower(column_name) LIKE '%maturity_date%' OR lower(column_name) LIKE '%net_debt%' OR lower(column_name) LIKE '%ebitda%' OR lower(column_name) LIKE '%leverage%' OR lower(column_name) LIKE '%participation%' OR lower(column_name) LIKE '%share_pct%' OR lower(column_name) LIKE '%hsbc_share%' OR lower(column_name) LIKE '%drawdown%' OR lower(column_name) LIKE '%call_report%' OR lower(column_name) LIKE '%meeting_note%')
UNION ALL
SELECT table_catalog, table_schema, table_name, column_name, data_type FROM "hive".information_schema.columns
WHERE table_schema <> 'information_schema' AND (lower(column_name) LIKE '%notional%' OR lower(column_name) LIKE '%swap%' OR lower(column_name) LIKE '%hedge%' OR lower(column_name) LIKE '%trade_date%' OR lower(column_name) LIKE '%maturity_date%' OR lower(column_name) LIKE '%net_debt%' OR lower(column_name) LIKE '%ebitda%' OR lower(column_name) LIKE '%leverage%' OR lower(column_name) LIKE '%participation%' OR lower(column_name) LIKE '%share_pct%' OR lower(column_name) LIKE '%hsbc_share%' OR lower(column_name) LIKE '%drawdown%' OR lower(column_name) LIKE '%call_report%' OR lower(column_name) LIKE '%meeting_note%')
ORDER BY 1, 2, 3, 4;
