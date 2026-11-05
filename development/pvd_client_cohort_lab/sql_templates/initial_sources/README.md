# Reviewed cohort SQL pack

Run schema statements separately first. Execute 02_extract.sql only after source/schema/date checks. 04_name_candidates.sql is supplementary candidate discovery, never an approved identifier match. Missing 02_extract.sql is explained by 02_BLOCKED.txt. No source table writes or staging privileges are required. No SQL was executed by generation.

CIN/GID links must be discovered and reviewed to unlock sources without direct mastergroup fields. Preserve full query text, parameters and export outcome. CSVs keep original headers/values.
