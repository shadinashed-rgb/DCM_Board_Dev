-- SIG07: CRR-only projection. No agency ratings or category/advisory inference.
-- READ ONLY. Fixed observed snapshot; retain ALL matched application versions.
-- Expected counts from the earlier profiles are guidance, not a completeness promise.
-- Save as application_ratings_softbank_full.csv. Preserve identifiers as text.
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
  AND (UPPER(TRIM(CAST(t."cin" AS VARCHAR))) IN ('SOFTBND', '00020705144', '101551354', '102007092', '101523640', '101934336', '101934339', '101551351', '101934342', '101523641', '102145119', '101523638', '101889223', 'MOFG', '046832927', 'SOBCBND', '1034377208', '101523619', '101645479', 'INHSBC054419403', 'SBGC', '101523623', '101522782', '994767618', 'JPHSBC009054297', '1034107555', '101524228', '101890679', '101645481', '102042985', 'OMHOMB010003861', 'INHSBC057002768', 'MYHBMB300329869', '102042981', 'USMMBI375121308', 'FRHBFR811198621', '1059394022', '101523642', 'SFBKBND', 'SOFTSDT', 'SOBKTKY', 'INHSBC054144076', '101934340', 'KIUL', '00022297013', 'SOFT', 'INHSBC054731179', '101523620', 'JPHSBC009054222', '101523625'))
ORDER BY t.country_code, t.cin, t.carm_instance, t.customer_id,
         t.credit_proposal_serial_no, t.record_start_dt;
