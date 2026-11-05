-- SQLite: execute one query at a time against a cohort run's cohort.sqlite.
SELECT * FROM coverage ORDER BY mastergroup_id, source;
SELECT * FROM source_status ORDER BY source;
SELECT * FROM signal_readiness ORDER BY mastergroup_id, signal_id;

-- Which routes associated an exported source record with each target?
SELECT m.mastergroup_id, m.source, m.raw_id, m.status, m.routes_json,
       r.filename, r.csv_record, r.observation_date, r.payload
FROM matches m JOIN raw_rows r USING(source, raw_id)
ORDER BY m.mastergroup_id, m.source, m.raw_id;

-- Conflicts remain available without assigning an arbitrary target group.
SELECT m.*, r.payload
FROM matches m JOIN raw_rows r USING(source, raw_id)
WHERE m.status='conflict';

-- Approved links used by this run, with namespace, scope and validity.
SELECT * FROM approved_links ORDER BY mastergroup_id, identifier_type;

-- A control: this query should return zero rows.
SELECT source, raw_id, COUNT(*) AS assigned_groups
FROM matches WHERE status='matched'
GROUP BY source, raw_id HAVING COUNT(*)>1;

-- Queries below target a signal run's results/bond_radar.sqlite instead.
SELECT cohort_mastergroup_id, signal_id, component, assessment_status, stale,
       COUNT(*) AS evidence_items
FROM cohort_signal_evidence
GROUP BY cohort_mastergroup_id, signal_id, component, assessment_status, stale;

SELECT * FROM cohort_signal_evidence
WHERE cohort_group_status='shared_or_unresolved_group';

SELECT * FROM cohort_row_groups ORDER BY source, raw_id;
