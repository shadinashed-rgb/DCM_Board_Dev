-- Bond Radar PORTFOLIO extraction · kyc · part 1 of 1
-- READ ONLY. Engine: Starburst / Trino. Copy, run, download as CSV with headers.
-- Save as: kyc/part_01_of_01.csv
-- As-of 2026-11-06, window 2026-07-09 .. 2026-11-06. All clients, no client/ID/name filter.
-- Keep identifiers as text. Do not open/re-save the CSV in Excel before processing.
-- DISTINCT removes identical rows only. Nothing is summed and no conflicting value is chosen.
-- Purpose: SIG04 KYC onboarding / refresh events
WITH base AS (
  SELECT
    t."run_date",
    t."source_system_name",
    t."cin",
    t."grid",
    t."legal_name",
    t."entity_type",
    t."entity_status",
    t."mg_name",
    t."mg_parent_grid",
    t."mg_parent_legal_name",
    t."groupguci",
    t."guci",
    t."related_case_id",
    t."related_case_type",
    t."related_case_class",
    t."related_case_status",
    t."related_case_resolved_time",
    t."related_case_update_time",
    t."review_purpose_code",
    t."review_purpose_desc",
    t."review_request_created_time_stamp",
    t."kyc_case_event_trigger_type_code",
    t."kyc_case_workflow_stage_name",
    t."workflow_status",
    t."kyc_case_review_decision_name",
    t."kyc_case_review_decision_date",
    t."next_review_date",
    ARRAY_JOIN(t."cdd_topco_legal_name", ' | ') AS cdd_topco_legal_name
  FROM "delta"."prod_party_gda"."kyc" t
  WHERE t."run_date" BETWEEN '20260709' AND '20261106'
    -- Event window: only cases requested within the KYC lookback. Routine history outside it is not a signal.
    AND TRY_CAST(SUBSTR(CAST(t."review_request_created_time_stamp" AS VARCHAR), 1, 10) AS DATE)
        BETWEEN DATE '2025-11-06' AND DATE '2026-11-06'
), snapshots AS (
  SELECT COALESCE("source_system_name", '~') AS part, MAX("run_date") AS latest_date FROM base GROUP BY COALESCE("source_system_name", '~')
),
selected AS (
SELECT DISTINCT b.* FROM base b
JOIN snapshots s ON s.part = COALESCE(b."source_system_name", '~') AND s.latest_date = b."run_date"
)
SELECT
  x."run_date",
  x."source_system_name",
  x."cin",
  x."grid",
  x."legal_name",
  x."entity_type",
  x."entity_status",
  x."mg_name",
  x."mg_parent_grid",
  x."mg_parent_legal_name",
  x."groupguci",
  x."guci",
  x."related_case_id",
  x."related_case_type",
  x."related_case_class",
  x."related_case_status",
  x."related_case_resolved_time",
  x."related_case_update_time",
  x."review_purpose_code",
  x."review_purpose_desc",
  x."review_request_created_time_stamp",
  x."kyc_case_event_trigger_type_code",
  x."kyc_case_workflow_stage_name",
  x."workflow_status",
  x."kyc_case_review_decision_name",
  x."kyc_case_review_decision_date",
  x."next_review_date",
  x."cdd_topco_legal_name"
FROM selected x
WHERE TRUE;
