-- READ ONLY; copy into Starburst and export manually. No Python/database connection.
-- Save as counterparty_current.csv. Keep identifiers as text; do not round in a spreadsheet.
-- Observed ID routes are discovery candidates, not verified cross-source joins.
-- SELECT DISTINCT removes identical rows only, never sums or chooses conflicting amounts.
-- Latest AVAILABLE within the bounded window; may be stale. Retain reporting/load dates.
-- Delta catalog corrected by user, 3 November 2026. Verify live columns/date format first.
-- Latest snapshot and preceding CLO mapping snapshots; inactive/conflicting mappings retained.
WITH filtered AS (
  SELECT t.* FROM "delta"."prod_party_gda"."counterparty_core" t
  WHERE t."run_date" BETWEEN '20260706' AND '20261103'
    AND (UPPER(TRIM(CAST(t."mastergroup_esr_identifier" AS VARCHAR))) IN ('MG001356', 'MG101624', 'MG102229') OR UPPER(TRIM(CAST(t."customer_relationship_cin_identifier" AS VARCHAR))) IN ('00020705144', '00022297013', '015791', '017854', '1007546581', '1017118210', '1018534202', '1018544917', '1018958303', '1030366064', '1034107555', '1034377208', '1059394022', '1087788129', '1091209375', '1095186264', '2020052909382', '2020052910083', '2020052910221', '2020061913563', '2020120111381', '2021072908540', '4396526', '6685339', '878370', 'AEBBME035063734', 'AUHKBA001634278', 'CNHSBC002054443', 'CNHSBC002066348', 'CNHSBC002069714', 'CNHSBC002077832', 'CNHSBC002084895', 'CNHSBC002645802', 'CNHSBC005014402', 'CNHSBC006037741', 'CNHSBC006054423', 'CNHSBC006064364', 'CNHSBC006068993', 'CNHSBC026005165', 'CNHSBC038001285', 'CNHSBC095095337', 'DE54009015791', 'EGHKEB001700202', 'EGHKEB005092390', 'EGHKEB016555666', 'GPRQO5LH6UDCBBD', 'INHSBC002489946', 'INHSBC002853513', 'INHSBC019329739', 'INHSBC030630271', 'INHSBC105833313', 'JPHSBC009054222', 'JPHSBC009054297', 'KIUL', 'MOFG', 'P757001', 'QABBME001787100', 'SBGC', 'SECL', 'SFBKBND', 'SIFO', 'SIHC', 'SIHO', 'SIIT', 'SIPP', 'SIRT', 'SITF', 'SMHN', 'SMSA', 'SOBCBND', 'SOBKTKY', 'SOFT', 'SOFTBND', 'SOFTSDT', 'VDFGBND', 'VDIS', 'VETL', 'VFGP', 'VGCG', 'VISP', 'VODA', 'VODAFON', 'VODGBND', 'VOET', 'VOTEADJ') OR UPPER(TRIM(CAST(t."customer_relationship_gid_identifier" AS VARCHAR))) IN ('G001604602', 'G002599455', 'G018762836', 'G026977903', 'G048563206', 'G055572350', 'G057028735', 'G076276826', 'G078541356', 'G094775446', 'G159367525', 'G162853321', 'G170805444', 'G177397146', 'G185668402', 'G212437910', 'G235457848', 'G312136344', 'G321262331', 'G382800205', 'G390539832', 'G450770610', 'G554930406', 'G592196340', 'G611504514', 'G622308435', 'G626293354', 'G629026734', 'G632429537', 'G642434617', 'G664906546', 'G667265030', 'G711489926', 'G801403349', 'G816598754', 'G873944403', 'G888143740', 'G918302442', 'G968580339', 'G999720847'))
), clo_dates AS (
  SELECT DISTINCT rct_mastergroup_id, run_date FROM "hive"."clo_prod"."clo_cda_contract_lvl"
  WHERE run_date BETWEEN '20260706' AND '20261103' AND rct_mastergroup_id IN ('MG001356', 'MG101624', 'MG102229')
), ranked_clo_dates AS (
  SELECT run_date, DENSE_RANK() OVER (PARTITION BY rct_mastergroup_id ORDER BY run_date DESC) AS snapshot_rank FROM clo_dates
), anchors AS (
  SELECT '20261103' AS anchor_date
  UNION SELECT run_date FROM ranked_clo_dates WHERE snapshot_rank <= 2
), mapping_dates AS (
  SELECT MAX(f.run_date) AS mapping_date FROM filtered f CROSS JOIN anchors a
  WHERE f.run_date <= a.anchor_date GROUP BY a.anchor_date
)
SELECT DISTINCT f.* FROM filtered f
WHERE f.run_date IN (SELECT mapping_date FROM mapping_dates);
