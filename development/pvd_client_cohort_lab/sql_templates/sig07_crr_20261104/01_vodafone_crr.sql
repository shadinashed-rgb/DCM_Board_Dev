-- SIG07: CRR-only projection. No agency ratings or category/advisory inference.
-- READ ONLY. Fixed observed snapshot; retain ALL matched application versions.
-- Expected counts from the earlier profiles are guidance, not a completeness promise.
-- Save as application_ratings_vodafone_full.csv. Preserve identifiers as text.
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
  AND (UPPER(TRIM(CAST(t."cin" AS VARCHAR))) IN ('FRHBFR004012233', 'INHSBC105003149', 'INHSBC002146447', 'VGCG', 'INHSBC006196810', 'VOTEADJ', 'INHSBC006196844', 'P757001', 'MUMOBU080136161', 'INHSBC002450633', 'INHSBC006196794', 'INHSBC006196828', 'EGHKEB001260736', '1018534202', 'MUMOBU080063274', 'INHSBC105002679', '1018544917', '1087788129', 'INHSBC002489946', 'VETL', 'MUMOBU080055684', 'VISP', 'MUMOBU080099500', 'QABBME001123314', 'INHSBC030852719', 'MUMOBU080068281', 'FRHBFR024102808', 'MUMOBU080014707', 'INHSBC030428189', '4396526', 'INHSBC019329739', 'MUMOBU080063282', 'MUMOBU080162282', '6685339', 'AEBBME023751316', 'INHSBC166127530', 'INHSBC030367825', 'INHSBC002761567', 'FRHBFR222181000', 'INHSBC006136220', 'VODA', 'INHSBC052422375', 'INHSBC006075782', '1030366064', 'INHSBC030721583', 'AEBBME036738425', 'VODAFON', 'INHSBC006196786', 'INHSBC019065481', 'INHSBC006196802', 'EGHKEB001700202', 'INHSBC030819510', 'MUMOBU080063225', 'MUMOBU080133507', 'INHSBC030725535', 'INHSBC105833313', 'MUHSBC072079098', 'MUMOBU080074016', 'INHSBC019231083', 'VDFGBND', 'FRHBFR024345530', 'INHSBC054053905', 'MUMOBU080133432', 'AUHBAP557015609', 'EGHKEB071228837', 'MUMOBU080074537', '1018958303', 'MUMOBU080133473', 'VODGBND', '1007546581', 'INHSBC006196760', 'MUMOBU080054943', 'USMMBI377644455', 'INHSBC030823231', 'INHSBC006213276', '1095186264', 'MUMOBU080014483', '918940', 'INHSBC002853513', 'MUMOBU080030547', '761358758', 'EGHKEB005092390', 'INHSBC019231075', 'FRHBFR512055138', 'EGHKEB016028888', '1091209375', 'INHSBC030251409', 'INHSBC002032621', 'VFGP', 'EGHKEB016555666', 'VOET', 'INHSBC030722003', 'VDIS', 'INHSBC006196836'))
ORDER BY t.country_code, t.cin, t.carm_instance, t.customer_id,
         t.credit_proposal_serial_no, t.record_start_dt;
