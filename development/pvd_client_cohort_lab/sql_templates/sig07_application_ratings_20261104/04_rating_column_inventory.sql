-- READ ONLY METADATA; candidate names are clues, not confirmed definitions.
SELECT column_name, data_type, ordinal_position
FROM "delta".information_schema.columns
WHERE table_schema='prod_credit_and_lending_gda' AND table_name='application_ratings'
  AND REGEXP_LIKE(LOWER(column_name),'rating|crr|agency|grade|standard|poor|mood|fitch|application|approval|effective|status|date')
ORDER BY ordinal_position;
