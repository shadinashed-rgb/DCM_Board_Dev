-- READ ONLY; copy into Starburst and export manually. No Python/database connection.
-- Save as facilities_current.csv. Keep identifiers as text; do not round in a spreadsheet.
-- Observed ID routes are discovery candidates, not verified cross-source joins.
-- SELECT DISTINCT removes identical rows only, never sums or chooses conflicting amounts.
-- Latest AVAILABLE within the bounded window; may be stale. Retain reporting/load dates.
-- Effective-period selection is a development rule to verify. Do not filter latest_record=CURRENT.
WITH filtered AS (
  SELECT t.* FROM "delta"."prod_credit_and_lending_gda"."facilities_limits" t
  WHERE t."run_date" BETWEEN '20260706' AND '20261103'
    AND (UPPER(TRIM(CAST(t."cin" AS VARCHAR))) IN ('00020705144', '00022297013', '015791', '017854', '1007546581', '1017118210', '1018534202', '1018544917', '1018958303', '1030366064', '1034107555', '1034377208', '1059394022', '1087788129', '1091209375', '1095186264', '2020052909382', '2020052910083', '2020052910221', '2020061913563', '2020120111381', '2021072908540', '4396526', '6685339', '878370', 'AEBBME035063734', 'AUHKBA001634278', 'CNHSBC002054443', 'CNHSBC002066348', 'CNHSBC002069714', 'CNHSBC002077832', 'CNHSBC002084895', 'CNHSBC002645802', 'CNHSBC005014402', 'CNHSBC006037741', 'CNHSBC006054423', 'CNHSBC006064364', 'CNHSBC006068993', 'CNHSBC026005165', 'CNHSBC038001285', 'CNHSBC095095337', 'DE54009015791', 'EGHKEB001700202', 'EGHKEB005092390', 'EGHKEB016555666', 'GPRQO5LH6UDCBBD', 'INHSBC002489946', 'INHSBC002853513', 'INHSBC019329739', 'INHSBC030630271', 'INHSBC105833313', 'JPHSBC009054222', 'JPHSBC009054297', 'KIUL', 'MOFG', 'P757001', 'QABBME001787100', 'SBGC', 'SECL', 'SFBKBND', 'SIFO', 'SIHC', 'SIHO', 'SIIT', 'SIPP', 'SIRT', 'SITF', 'SMHN', 'SMSA', 'SOBCBND', 'SOBKTKY', 'SOFT', 'SOFTBND', 'SOFTSDT', 'VDFGBND', 'VDIS', 'VETL', 'VFGP', 'VGCG', 'VISP', 'VODA', 'VODAFON', 'VODGBND', 'VOET', 'VOTEADJ') OR UPPER(TRIM(CAST(t."relationship_id" AS VARCHAR))) IN ('2020052910083'))
), ranked AS (
  SELECT f.*, DENSE_RANK() OVER (ORDER BY "run_date" DESC) AS _extract_snapshot_rank
  FROM filtered f
)
SELECT DISTINCT r.* FROM ranked r
WHERE _extract_snapshot_rank <= 1
  AND (TRY(DATE_PARSE(NULLIF(TRIM(record_start_dt), ''), '%Y%m%d')) IS NULL OR record_start_dt <= run_date)
  AND (TRY(DATE_PARSE(NULLIF(TRIM(record_end_dt), ''), '%Y%m%d')) IS NULL OR record_end_dt = '99991231' OR record_end_dt >= run_date);
