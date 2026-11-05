-- SIG07: CRR-only projection. No agency ratings or category/advisory inference.
-- READ ONLY. Fixed observed snapshot; retain ALL matched application versions.
-- Expected counts from the earlier profiles are guidance, not a completeness promise.
-- Save as application_ratings_siemens_energy_full.csv. Preserve identifiers as text.
-- Do not filter latest_record, approval flags, CRR or provider fields at landing.
SELECT
  t."source_system_unique_id",
  t."source_system_name",
  t."country_code",
  t."carm_instance",
  t."branch_code",
  t."cin",
  t."customer_id",
  t."relationship_id",
  t."credit_proposal_serial_no",
  t."mastergroup_name",
  t."customer_name",
  t."run_date",
  t."record_start_dt",
  t."record_end_dt",
  t."latest_record",
  t."latest_approved_appl_flag",
  t."app_status",
  t."approval_dt",
  t."assessment_creation_dt",
  t."assessment_approval_dt",
  t."crr_scale",
  t."final_crr",
  t."previous_crr",
  t."proposed_crr",
  t."approved_crr",
  t."proposed_manual_crr",
  t."overriden_crr",
  t."crr_prior_ovrd",
  t."crr_post_ovrd",
  t."model_crr"
FROM "delta"."prod_credit_and_lending_gda"."application_ratings" t
WHERE t."run_date" = '20261103'
  AND (UPPER(TRIM(CAST(t."cin" AS VARCHAR))) IN ('INHSBC030630271', 'FRHBFR024125312', 'CNHSBC026005165', '878370', 'AEJFSC926000142', 'INHSBC042846030', 'CNHSBC095095337', 'CNHSBC002084895', 'FRHBFR024123135', 'SIHO', '015791', '2020052910221', '2020061913563', '2020052910083', 'KRHSBC002004968', 'INHSBC042448878', 'CNHSBC006064364', 'SIHC', 'CNHSBC006054423', 'AUHKBA001634278', 'CNHSBC005014402', '2021072908540', 'SIRT', 'INHSBC042004655', 'INHSBC042387472', 'FRHBFR024144594', 'ESMDBK001075886', 'INHSBC042791178', 'FRHBFR024100836', 'CNHSBC038001285', 'SECL', 'CNHSBC002066348', 'FRHBFR024123101', 'QABBME001787100', 'CNHSBC002077832', 'DE54009015791', 'TWHSBC001265222', 'CNHSBC006037741', '2020120111381', 'SIIT', 'FRHBFR024123721', 'AEBBME035063734', 'CNHSBC006068993', 'FRHBFR024159386', 'GPRQO5LH6UDCBBD', 'SMSA', 'FRHBFR024120503', '1017118210', 'SIPP', 'FRHBFR024125304', 'FRHBFR024208811', '017854', 'SITF', 'SMHN', 'AEBBME021335351', 'CNHSBC002069714', 'EGHKEB039157771', 'SIFO', '2020052909382', 'CNHSBC002054443'))
ORDER BY t.country_code, t.cin, t.carm_instance, t.customer_id,
         t.credit_proposal_serial_no, t.record_start_dt;
