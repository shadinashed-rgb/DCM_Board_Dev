#!/usr/bin/env python3
"""Generate the PORTFOLIO extraction pack: every client, every source, no target list.

The earlier packs (current_20261103, sig07_crr_20261104) filter to the three
development clients by hard-coded mastergroup/CIN/GID lists and use SELECT t.*.
This generator writes read-only Trino/Starburst SQL that:

  * extracts ALL clients from each source — no client, name or ID filter;
  * projects only the columns the signal rules, identity resolution and lineage
    need (CLO is an exploded contract x account table; projecting to sub-limit
    level columns collapses it to one row per sub-limit x snapshot x borrower);
  * selects snapshots per publishing partition, never one global latest date
    (a global max loses lagging partitions such as Siemens DE Facilities);
  * splits large sources into N hash buckets so each download stays below the
    Starburst/UI export limit. Buckets are stable (xxhash64 of a group key) and
    every row lands in exactly one bucket;
  * keeps identical-row DISTINCT only — no sums, no MAX/first picking of
    conflicting values; conflicts surface downstream as conflicting observations.

Nothing here connects to Starburst. Copy each file into Starburst, run it,
download the CSV and save it under the exact name in EXTRACTION_CHECKLIST.csv.

Usage (from development/):
  python3 -B pvd_client_cohort_lab/portfolio_sql.py --as-of 2026-11-06 \
      --out pvd_client_cohort_lab/sql_templates/portfolio_20261106 \
      --buckets clo=8,facilities=2,drr=2,counterparty=4
"""
import argparse
from datetime import date, timedelta
import csv
import json
from pathlib import Path

HEADER = """-- Bond Radar PORTFOLIO extraction · {title}
-- READ ONLY. Engine: Starburst / Trino. Copy, run, download as CSV with headers.
-- Save as: {save_as}
-- As-of {as_of_iso}, window {start_iso} .. {as_of_iso}. All clients, no client/ID/name filter.
-- Keep identifiers as text. Do not open/re-save the CSV in Excel before processing.
-- DISTINCT removes identical rows only. Nothing is summed and no conflicting value is chosen.
"""

SOURCES = ['counterparty', 'clo', 'facilities', 'drr', 'pvd', 'kyc', 'covenants', 'application_ratings']
SIGNALS = {
    'counterparty': 'Identity backbone: CIN/GID -> mastergroup, names, business line (all signals)',
    'clo': 'SIG01 drawings (REV/TERM), CTX_UTIL, maturity windows',
    'facilities': 'SIG02 new facilities, SIG01 Cat A lookup, CTX_CREDIT, maturity windows, relationship->CIN route',
    'drr': 'CTX_UTIL utilisation, covenant-waiver lead for SIG06',
    'pvd': 'CTX_UTIL / CTX_CREDIT context (relationship grain, no mastergroup ID)',
    'kyc': 'SIG04 KYC onboarding / refresh events',
    'covenants': 'SIG06 covenant breach / pressure (financial tests)',
    'application_ratings': 'SIG02 credit approval dates and CTX_CREDIT CRR',
}


def bucket_clause(key_expr, n, b):
    if n <= 1:
        return 'TRUE'
    # Stable split: the same group key always lands in the same bucket.
    return f"MOD(ABS(from_big_endian_64(xxhash64(to_utf8(COALESCE({key_expr}, '~'))))), {n}) = {b}"


def q(cols, alias='t'):
    return ',\n    '.join(c if ' AS ' in c else f'{alias}."{c}"' for c in cols)


COLUMNS = {
    'counterparty': ['run_date', 'source_system_name', 'source_system_instance_country', 'customer_relationship_cin_identifier',
                     'customer_relationship_gid_identifier', 'customer_relationship_lifecycle_status_code', 'customer_relationship_segment_local_code',
                     'customer_relationship_cin_name', 'customer_relationship_hsbc_booking_entity_country_code', 'mastergroup_esr_identifier',
                     'mastergroup_name', 'mastergroup_lifecycle_status_code', 'mastergroup_business_line_code', 'mastergroup_designation_name',
                     'mastergroup_principal_country_code', 'mastergroup_industry_classification_sector_name', 'mastergroup_supergroup_identifier',
                     'mastergroup_supergroup_name', 'organisation_grid_identifier', 'organisation_legal_entity_lei_identifier'],
    # Sub-limit/facility-level columns only. Account- and contract-level columns are excluded on purpose:
    # they multiply rows (the table is exploded) and are not used by any signal rule.
    'clo': ['run_date', 'source_system', 'mapping_system', 'hsbc_booking_legal_entity', 'sub_lim_id', 'rct_facility_ref', 'facility_id',
            'obligor_cin', 'rct_gid', 'rct_mastergroup_id', 'rct_mastergroup_name', 'liq_gcdu_gid', 'liq_gcdu_mastergroup_id',
            'liq_gcdu_mastergroup_name', 'local_product_type_lbs', 'facility_name', 'facility_currency', 'facility_limit_amount',
            'facility_drawn_amount', 'facility_undrawn_amount', 'ag_acc_bal_drawn_sub_lim_usd', 'hsbc_facility_limits_gross',
            'deal_indicator_sole_lender', 'primary_borrower_indicator', 'facility_maturity_date', 'facility_effective_date',
            'rct_industry_level_1', 'rct_dm_country', 'rct_dm_region', 'obligor_customer_name'],
    'facilities': ['run_date', 'source_system_name', 'country_code', 'booking_country', 'facility_id', 'facility_number', 'main_limit_facility_id',
                   'cin', 'relationship_id', 'customer_id', 'source_system_unique_id', 'credit_proposal_serial_no', 'application_serial_number',
                   'product_code', 'product_type', 'facility_purpose', 'limit_cat', 'limit_type', 'limit_category_type', 'advised_ind',
                   'facility_grade_code', 'facility_grade_desc', 'sustainable_risk_rating_impact_approved', 'facility_ccy', 'proposed_limit',
                   'previous_limit', 'allocated_limit_amount', 'commitment_ind', 'unconditional_cancel_ind', 'cancellation_ind',
                   'facility_cancelled_ind', 'active_facility_ind', 'facility_creation_date', 'loan_approva_dt', 'limit_review_dt',
                   'loan_maturity_dt', 'final_loan_maturity_dt', 'facility_expiry_dt', 'date_of_expiry', 'record_start_dt', 'record_end_dt',
                   'latest_record', 'facility_record_updated_date'],
    'drr': ['reporting_date', 'run_date', 'source_system_name', 'source_system_unique_id', 'rpt_facility_country_code', 'base_entity_country',
            'drr_mastergroup_id', 'gid', 'cin', 'grid', 'drr_customer_uid', 'drr_gid_uid', 'guci', 'groupguci', 'facility_id', 'drr_uid',
            'drr_facility_uid', 'facility_type_code', 'local_facility_type', 'facility_category', 'committed_flag', 'unconditionally_cancellable',
            'facility_as_parent', 'facility_as_child', 'shared_facility_flag', 'facility_start_date', 'facility_end_date', 'approved_limit',
            'approved_limit_ccy', 'approved_limit_lcy', 'actual_limit', 'actual_limit_ccy', 'utilisation', 'utilisation_ccy', 'utilisation_lcy',
            'undrawn', 'undrawn_ccy', 'advised_flag', 'purpose_code', 'covenaint_waiver_date', 'debt_restructure_flag', 'maturity_extension_date'],
    'pvd': ['joi_date', 'joi_relationship_id', 'joi_relationship_name', 'joi_key', 'joi_segment', 'joi_b_country', 'joi_m_lob', 'drr_supergroup_id',
            'drr_supergroup_name', 'omn_mastergroup_name', 'drr_product', 'drr_fac_category', 'joi_facility_category', 'drr_act_limit',
            'drr_carm_limit', 'drr_utils', 'drr_commitment', 'exposure_usd', 'drr_crr', 'drr_pd', 'month_year', 'etlmonth', 'etlmonth_drr'],
    'kyc': ['run_date', 'source_system_name', 'cin', 'grid', 'legal_name', 'entity_type', 'entity_status', 'mg_name', 'mg_parent_grid',
            'mg_parent_legal_name', 'groupguci', 'guci', 'related_case_id', 'related_case_type', 'related_case_class', 'related_case_status',
            'related_case_resolved_time', 'related_case_update_time', 'review_purpose_code', 'review_purpose_desc', 'review_request_created_time_stamp',
            'kyc_case_event_trigger_type_code', 'kyc_case_workflow_stage_name', 'workflow_status', 'kyc_case_review_decision_name',
            'kyc_case_review_decision_date', 'next_review_date',
            # cdd_topco_legal_name is ARRAY(varchar) in Trino: join it so the CSV cell is text.
            'ARRAY_JOIN(t."cdd_topco_legal_name", \' | \') AS cdd_topco_legal_name'],
    'covenants': ['run_date', 'source_system_name', 'country_code', 'relationship_id', 'local_customer_id', 'entity_id', 'facility_id', 'covenant_id',
                  'covenant_type', 'covenant_sub_type', 'covenant_financial_derived_type', 'covenant_title', 'covenant_category_type', 'covenant_status',
                  'covenant_approval_status', 'frequency', 'facility_covenant_level', 'active_testing_id', 'active_testing_actual_value',
                  'active_testing_final_value', 'active_testing_testing_threshold_value', 'active_testing_testing_threshold_operator',
                  'active_testing_testing_threshold_value_2', 'active_testing_testing_threshold_operator_2', 'active_testing_approval_status',
                  'active_testing_testing_result', 'active_testing_final_result', 'active_testing_testing_due_dt', 'reporting_dt',
                  'last_testing_result', 'historic_testing_due_dt', 'historic_final_value', 'historic_final_result', 'next_testing_dt'],
    'application_ratings': ['source_system_unique_id', 'source_system_name', 'country_code', 'carm_instance', 'branch_code', 'cin', 'customer_id',
                            'relationship_id', 'credit_proposal_serial_no', 'mastergroup_name', 'customer_name', 'run_date', 'record_start_dt',
                            'record_end_dt', 'latest_record', 'latest_approved_appl_flag', 'app_status', 'approval_dt', 'assessment_creation_dt',
                            'assessment_approval_dt', 'crr_scale', 'final_crr', 'previous_crr', 'proposed_crr', 'approved_crr', 'proposed_manual_crr',
                            'overriden_crr', 'crr_prior_ovrd', 'crr_post_ovrd', 'model_crr'],
}

TABLES = {
    'counterparty': '"delta"."prod_party_gda"."counterparty_core"',
    'clo': '"hive"."clo_prod"."clo_cda_contract_lvl"',
    'facilities': '"delta"."prod_credit_and_lending_gda"."facilities_limits"',
    'drr': '"delta"."prod_credit_and_lending_mda"."drr_facility_limits"',
    'pvd': '"hive"."pvd_prod_wave"."pvd_omnia_drr"',
    'kyc': '"delta"."prod_party_gda"."kyc"',
    'covenants': '"delta"."prod_credit_and_lending_gda"."covenants"',
    'application_ratings': '"delta"."prod_credit_and_lending_gda"."application_ratings"',
}

# Bucket key per source: groups a client's rows together. Any key is valid for correctness
# because the pipeline re-combines every part before processing.
BUCKET_KEY = {
    'counterparty': 'COALESCE(b."customer_relationship_cin_identifier", b."customer_relationship_gid_identifier")',
    'clo': 'b.group_key',
    'facilities': 'COALESCE(b."cin", b."relationship_id", b."facility_id")',
    'drr': 'b.group_key',
    'pvd': 'b."joi_relationship_id"',
    'kyc': 'b."cin"',
    'covenants': 'COALESCE(b."relationship_id", b."facility_id")',
    'application_ratings': 'b."cin"',
}


def body(source, p):
    """Return (with_ctes, final_select_without_bucket, partition_expr_for_profile)."""
    t = TABLES[source]
    cols = q(COLUMNS[source])
    s, a = p['start'], p['as_of']
    if source == 'counterparty':
        return f"""WITH base AS (
  SELECT
    {cols}
  FROM {t} t
  WHERE t."run_date" BETWEEN '{s}' AND '{a}'{p['cp_scope']}
), snapshots AS (
  -- Latest two snapshots per publishing instance: latest mapping plus the one the prior CLO comparison needs.
  SELECT part, "run_date", DENSE_RANK() OVER (PARTITION BY part ORDER BY "run_date" DESC) AS snapshot_rank
  FROM (SELECT DISTINCT COALESCE("source_system_instance_country", '~') AS part, "run_date" FROM base) d
)""", """SELECT DISTINCT b.* FROM base b
JOIN snapshots s ON s.part = COALESCE(b."source_system_instance_country", '~') AND s."run_date" = b."run_date"
WHERE s.snapshot_rank <= 2""", 'b."source_system_instance_country"'
    if source == 'clo':
        return f"""WITH base AS (
  SELECT
    {cols},
    -- Group key for snapshot selection: native mastergroup, else borrower CIN/GID, else the facility itself.
    COALESCE(NULLIF(TRIM(t."rct_mastergroup_id"), ''), 'CIN:' || NULLIF(TRIM(t."obligor_cin"), ''),
             'GID:' || NULLIF(TRIM(t."rct_gid"), ''), 'FAC:' || COALESCE(t."sub_lim_id", t."rct_facility_ref", t."facility_id")) AS group_key
  FROM {t} t
  WHERE t."run_date" BETWEEN '{s}' AND '{a}'{p['clo_scope']}
), dates AS (
  SELECT DISTINCT group_key, "run_date" FROM base
), latest AS (
  SELECT group_key, MAX("run_date") AS latest_date FROM dates GROUP BY group_key
), prior AS (
  -- Prior snapshot = newest date at least {p['gap']} day(s) before the group's latest (SIG01 comparison side).
  SELECT d.group_key, MAX(d."run_date") AS prior_date
  FROM dates d JOIN latest l ON l.group_key = d.group_key
  WHERE date_parse(d."run_date", '%Y%m%d') <= date_add('day', -{p['gap']}, date_parse(l.latest_date, '%Y%m%d'))
  GROUP BY d.group_key
)""", """SELECT DISTINCT b.* FROM base b
JOIN latest l ON l.group_key = b.group_key
LEFT JOIN prior p ON p.group_key = b.group_key
WHERE b."run_date" = l.latest_date OR b."run_date" = p.prior_date""", 'b."run_date"'
    if source == 'facilities':
        return f"""WITH base AS (
  SELECT
    {cols}
  FROM {t} t
  WHERE t."run_date" BETWEEN '{s}' AND '{a}'
), snapshots AS (
  -- Latest snapshot per source system and country: avoids losing partitions that publish later.
  SELECT part_sys, part_cty, MAX("run_date") AS latest_date
  FROM (SELECT DISTINCT COALESCE("source_system_name", '~') AS part_sys, COALESCE("country_code", '~') AS part_cty, "run_date" FROM base) d
  GROUP BY part_sys, part_cty
)""", """SELECT DISTINCT b.* FROM base b
JOIN snapshots s ON s.part_sys = COALESCE(b."source_system_name", '~') AND s.part_cty = COALESCE(b."country_code", '~') AND s.latest_date = b."run_date"
-- Versions effective at the snapshot date (open end 99991231). Development rule, overlaps are kept for conflict checks.
WHERE (TRY(date_parse(NULLIF(TRIM(b."record_start_dt"), ''), '%Y%m%d')) IS NULL OR b."record_start_dt" <= b."run_date")
  AND (TRY(date_parse(NULLIF(TRIM(b."record_end_dt"), ''), '%Y%m%d')) IS NULL OR b."record_end_dt" = '99991231' OR b."record_end_dt" >= b."run_date")""", 'b."country_code"'
    if source == 'drr':
        return f"""WITH base AS (
  SELECT
    {cols},
    COALESCE(NULLIF(TRIM(t."drr_mastergroup_id"), ''), 'GID:' || NULLIF(TRIM(t."gid"), ''), 'CIN:' || NULLIF(TRIM(t."cin"), ''),
             'FAC:' || t."facility_id") AS group_key
  FROM {t} t
  WHERE t."reporting_date" BETWEEN '{s}' AND '{a}' AND t."run_date" <= '{a}'
), latest AS (
  SELECT group_key, MAX("reporting_date") AS latest_date FROM base GROUP BY group_key
)""", """SELECT DISTINCT b.* FROM base b
JOIN latest l ON l.group_key = b.group_key AND l.latest_date = b."reporting_date\"""", 'b."reporting_date"'
    if source == 'pvd':
        return f"""WITH base AS (
  SELECT
    {cols}
  FROM {t} t
  WHERE t."joi_date" BETWEEN '{p['start_iso']}' AND '{p['as_of_iso']}'
    AND (t."etlmonth" IS NULL OR TRIM(CAST(t."etlmonth" AS VARCHAR)) = '' OR SUBSTR(REPLACE(CAST(t."etlmonth" AS VARCHAR), '-', ''), 1, 8) <= '{a}')
    AND (t."etlmonth_drr" IS NULL OR TRIM(CAST(t."etlmonth_drr" AS VARCHAR)) = '' OR SUBSTR(REPLACE(CAST(t."etlmonth_drr" AS VARCHAR), '-', ''), 1, 8) <= '{a}')
), latest AS (
  SELECT "joi_relationship_id", MAX("joi_date") AS latest_date FROM base GROUP BY "joi_relationship_id"
)""", """SELECT DISTINCT b.* FROM base b
JOIN latest l ON l."joi_relationship_id" = b."joi_relationship_id" AND l.latest_date = b."joi_date\"""", 'b."joi_date"'
    if source == 'kyc':
        return f"""WITH base AS (
  SELECT
    {cols}
  FROM {t} t
  WHERE t."run_date" BETWEEN '{s}' AND '{a}'
    -- Event window: only cases requested within the KYC lookback. Routine history outside it is not a signal.
    AND TRY_CAST(SUBSTR(CAST(t."review_request_created_time_stamp" AS VARCHAR), 1, 10) AS DATE)
        BETWEEN DATE '{p['kyc_start_iso']}' AND DATE '{p['as_of_iso']}'
), snapshots AS (
  SELECT COALESCE("source_system_name", '~') AS part, MAX("run_date") AS latest_date FROM base GROUP BY COALESCE("source_system_name", '~')
)""", """SELECT DISTINCT b.* FROM base b
JOIN snapshots s ON s.part = COALESCE(b."source_system_name", '~') AND s.latest_date = b."run_date\"""", 'b."source_system_name"'
    if source == 'covenants':
        return f"""WITH base AS (
  SELECT
    {cols}
  FROM {t} t
  WHERE t."run_date" BETWEEN '{s}' AND '{a}'
    -- Tests reported or due within the covenant lookback. Financial-type filtering happens in the engine.
    AND (t."reporting_dt" >= DATE '{p['cov_start_iso']}' OR t."active_testing_testing_due_dt" >= DATE '{p['cov_start_iso']}')
), snapshots AS (
  SELECT part_sys, part_cty, MAX("run_date") AS latest_date
  FROM (SELECT DISTINCT COALESCE("source_system_name", '~') AS part_sys, COALESCE("country_code", '~') AS part_cty, "run_date" FROM base) d
  GROUP BY part_sys, part_cty
)""", """SELECT DISTINCT b.* FROM base b
JOIN snapshots s ON s.part_sys = COALESCE(b."source_system_name", '~') AND s.part_cty = COALESCE(b."country_code", '~') AND s.latest_date = b."run_date\"""", 'b."covenant_type"'
    if source == 'application_ratings':
        return f"""WITH base AS (
  SELECT
    {cols}
  FROM {t} t
  WHERE t."run_date" BETWEEN '{s}' AND '{a}'
), snapshots AS (
  -- Latest snapshot per source / country / CARM instance (the CRR adapter applies the same rule).
  SELECT part_sys, part_cty, part_carm, MAX("run_date") AS latest_date
  FROM (SELECT DISTINCT COALESCE("source_system_name", '~') AS part_sys, COALESCE("country_code", '~') AS part_cty,
                        COALESCE("carm_instance", '~') AS part_carm, "run_date" FROM base) d
  GROUP BY part_sys, part_cty, part_carm
)""", f"""SELECT DISTINCT b.* FROM base b
JOIN snapshots s ON s.part_sys = COALESCE(b."source_system_name", '~') AND s.part_cty = COALESCE(b."country_code", '~')
                AND s.part_carm = COALESCE(b."carm_instance", '~') AND s.latest_date = b."run_date"
-- Keep (a) applications effective at the snapshot (CRR context) and
--      (b) any application approved within the approval lookback (SIG02 credit approval dates).
WHERE ((TRY(date_parse(NULLIF(TRIM(b."record_start_dt"), ''), '%Y%m%d')) IS NULL OR b."record_start_dt" <= b."run_date")
       AND (TRY(date_parse(NULLIF(TRIM(b."record_end_dt"), ''), '%Y%m%d')) IS NULL OR b."record_end_dt" = '99991231' OR b."record_end_dt" >= b."run_date"))
   OR TRY(date_parse(NULLIF(TRIM(b."approval_dt"), ''), '%Y%m%d')) >= DATE '{p['appr_start_iso']}'""", 'b."country_code"'
    raise ValueError(source)


def output_columns(source):
    """Native column names in download order (helper columns such as group_key are not exported)."""
    return [c.split(' AS ')[1].strip() if ' AS ' in c else c for c in COLUMNS[source]]


def extract_sql(source, p, n, b, save_as):
    ctes, select, _ = body(source, p)
    # The selection is wrapped so the bucket filter applies to the finished selection,
    # never inside its OR/AND logic, and helper columns are dropped from the CSV.
    projection = ',\n  '.join(f'x."{c}"' for c in output_columns(source))
    bucket = bucket_clause(BUCKET_KEY[source].replace('b.', 'x.'), n, b)
    return (HEADER.format(title=f'{source} · part {b + 1} of {n}', save_as=save_as, **p) + f'-- Purpose: {SIGNALS[source]}\n'
            + ctes + f',\nselected AS (\n{select}\n)\nSELECT\n  {projection}\nFROM selected x\nWHERE {bucket};\n')


def profile_sql(source, p):
    ctes, inner, part = body(source, p)
    key = BUCKET_KEY[source].replace('b.', 'x.')
    part_x = part.replace('b.', 'x.')
    return (HEADER.format(title=f'{source} · PROFILE (run first)', save_as=f'profiles/{source}_profile.csv', **p)
            + '-- Row counts the extract would return, by snapshot/partition. Use them to choose the number of parts\n'
            + '-- (rows per part should stay below your Starburst download limit).\n'
            + ctes + f',\nselected AS (\n{inner}\n)\n'
            + f'SELECT {part_x} AS partition_value, COUNT(*) AS rows_selected, COUNT(DISTINCT {key}) AS distinct_bucket_keys\n'
            + 'FROM selected x\nGROUP BY 1\nORDER BY rows_selected DESC;\n')


def fx_sql(p):
    return (HEADER.format(title='CLO FX reference (optional, for the SIG01 EUR 50m test)', save_as='reference/clo_fx_reference.csv', **p)
            + """-- Median of CLO instrument_currency_fx_to_usd by currency and snapshot. UNVALIDATED as an FX source:
-- the field is known to be dirty, which is why the median (not max) is used and min/max/count are kept.
SELECT t."run_date", t."facility_currency" AS currency, COUNT(*) AS rows_with_rate,
       approx_percentile(TRY_CAST(t."instrument_currency_fx_to_usd" AS double), 0.5) AS fx_to_usd_median,
       MIN(TRY_CAST(t."instrument_currency_fx_to_usd" AS double)) AS fx_to_usd_min,
       MAX(TRY_CAST(t."instrument_currency_fx_to_usd" AS double)) AS fx_to_usd_max
FROM "hive"."clo_prod"."clo_cda_contract_lvl" t
WHERE t."run_date" BETWEEN '{s}' AND '{a}'
  AND TRY_CAST(t."instrument_currency_fx_to_usd" AS double) > 0
GROUP BY t."run_date", t."facility_currency"
ORDER BY t."run_date" DESC, currency;
""".format(s=p['start'], a=p['as_of']))


DISCOVERY = """-- Bond Radar · DISCOVERY of sources still missing for SIG03A, SIG03B, SIG06, SIG07 and SIG01 (LoanIQ).
-- READ ONLY, metadata only. Run each statement separately and save each result as discovery/<file>.csv.
-- No row can mean "not found" OR "no metadata permission", it never proves absence.

-- 1. Tables by name (save as discovery/tables_by_name.csv)
SELECT table_catalog, table_schema, table_name, table_type FROM "delta".information_schema.tables
WHERE table_schema <> 'information_schema' AND ({preds})
UNION ALL
SELECT table_catalog, table_schema, table_name, table_type FROM "hive".information_schema.tables
WHERE table_schema <> 'information_schema' AND ({preds})
ORDER BY 1, 2, 3;

-- 2. Columns by name (save as discovery/columns_by_name.csv)
SELECT table_catalog, table_schema, table_name, column_name, data_type FROM "delta".information_schema.columns
WHERE table_schema <> 'information_schema' AND ({cpreds})
UNION ALL
SELECT table_catalog, table_schema, table_name, column_name, data_type FROM "hive".information_schema.columns
WHERE table_schema <> 'information_schema' AND ({cpreds})
ORDER BY 1, 2, 3, 4;
"""
TABLE_TERMS = ['%swap%', '%deriv%', '%otc%', '%fx%trade%', '%hedge%', '%pricing%request%', '%rfq%', '%enquir%', '%inquir%',
               '%covenant%', '%loaniq%', '%loan_iq%', '%liq%drawdown%', '%drawdown%', '%participation%', '%syndicat%',
               '%call%report%', '%cme%', '%call%note%', '%rating%advis%']
COLUMN_TERMS = ['%notional%', '%swap%', '%hedge%', '%trade_date%', '%maturity_date%', '%net_debt%', '%ebitda%', '%leverage%',
                '%participation%', '%share_pct%', '%hsbc_share%', '%drawdown%', '%call_report%', '%meeting_note%']


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--as-of', required=True, help='assessment date YYYY-MM-DD (latest snapshot allowed)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--window-days', type=int, default=120, help='how far back a lagging partition may sit')
    ap.add_argument('--clo-prior-gap-days', type=int, default=1, help='minimum days between the CLO latest and prior snapshot')
    ap.add_argument('--kyc-lookback-days', type=int, default=365)
    ap.add_argument('--covenant-lookback-days', type=int, default=400)
    ap.add_argument('--approval-lookback-days', type=int, default=400)
    ap.add_argument('--clo-all-products', action='store_true', help='keep every CLO product, not only REV/TERM/blank')
    ap.add_argument('--cp-business-lines', default='', help='optional comma list of mastergroup_business_line_code to scope counterparty')
    ap.add_argument('--buckets', default='clo=8,facilities=2,drr=2,counterparty=4',
                    help='parts per source, e.g. clo=8,facilities=2 (others default to 1). Choose from the profile counts.')
    a = ap.parse_args()
    as_of = date.fromisoformat(a.as_of)
    start = as_of - timedelta(days=a.window_days)
    p = dict(as_of=as_of.strftime('%Y%m%d'), as_of_iso=as_of.isoformat(), start=start.strftime('%Y%m%d'), start_iso=start.isoformat(),
             gap=a.clo_prior_gap_days, kyc_start_iso=(as_of - timedelta(days=a.kyc_lookback_days)).isoformat(),
             cov_start_iso=(as_of - timedelta(days=a.covenant_lookback_days)).isoformat(),
             appr_start_iso=(as_of - timedelta(days=a.approval_lookback_days)).isoformat(),
             clo_scope='' if a.clo_all_products else
             "\n    -- Any bank facility type Jerome described: revolving and term loans. Blank product kept (unknown, not excluded).\n"
             "    AND (UPPER(TRIM(t.\"local_product_type_lbs\")) IN ('REV', 'TERM') OR NULLIF(TRIM(t.\"local_product_type_lbs\"), '') IS NULL)",
             cp_scope='' if not a.cp_business_lines else
             "\n    AND UPPER(TRIM(t.\"mastergroup_business_line_code\")) IN (" + ', '.join(f"'{x.strip().upper()}'" for x in a.cp_business_lines.split(',') if x.strip()) + ')')
    buckets = {s: 1 for s in SOURCES}
    for item in filter(None, a.buckets.split(',')):
        k, v = item.split('=')
        if k not in buckets:
            raise SystemExit(f'Unknown source in --buckets: {k}')
        buckets[k] = max(1, int(v))
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f'{out} exists; choose a new folder')
    (out / '01_profiles').mkdir(parents=True)
    checklist = []
    step = 0
    for s in SOURCES:
        step += 1
        f = out / '01_profiles' / f'{step:02d}_{s}_profile.sql'
        f.write_text(profile_sql(s, p))
        checklist.append(dict(step=f'1.{step}', stage='profile', source=s, sql_file=str(f.relative_to(out)), save_as=f'profiles/{s}_profile.csv', parts=1, purpose='row counts to size the extract'))
    for s in SOURCES:
        n = buckets[s]
        folder = out / '02_extracts' / s
        folder.mkdir(parents=True)
        for b in range(n):
            save_as = f'{s}/part_{b + 1:02d}_of_{n:02d}.csv'
            f = folder / f'{s}_part_{b + 1:02d}_of_{n:02d}.sql'
            f.write_text(extract_sql(s, p, n, b, save_as))
            checklist.append(dict(step=f'2.{SOURCES.index(s) + 1}.{b + 1}', stage='extract', source=s, sql_file=str(f.relative_to(out)), save_as=save_as, parts=n, purpose=SIGNALS[s]))
    (out / '03_reference').mkdir()
    (out / '03_reference' / 'clo_fx_reference.sql').write_text(fx_sql(p))
    checklist.append(dict(step='3.1', stage='reference', source='clo', sql_file='03_reference/clo_fx_reference.sql', save_as='reference/clo_fx_reference.csv', parts=1, purpose='optional unvalidated FX for the EUR 50m test'))
    (out / '04_discovery').mkdir()
    preds = ' OR '.join(f"lower(table_name) LIKE '{x}'" for x in TABLE_TERMS)
    cpreds = ' OR '.join(f"lower(column_name) LIKE '{x}'" for x in COLUMN_TERMS)
    (out / '04_discovery' / 'missing_sources_discovery.sql').write_text(DISCOVERY.format(preds=preds, cpreds=cpreds))
    checklist.append(dict(step='4.1', stage='discovery', source='(metadata)', sql_file='04_discovery/missing_sources_discovery.sql', save_as='discovery/tables_by_name.csv + discovery/columns_by_name.csv', parts=1, purpose='find derivatives, covenant, LoanIQ, call-report sources'))
    with (out / 'EXTRACTION_CHECKLIST.csv').open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['step', 'stage', 'source', 'sql_file', 'save_as', 'parts', 'purpose', 'rows_downloaded', 'status'])
        w.writeheader()
        w.writerows(dict(r, rows_downloaded='', status='') for r in checklist)
    manifest = dict(generated_by='portfolio_sql.py', parameters=vars(a), resolved=p, buckets=buckets, columns=COLUMNS, tables=TABLES,
                    save_root='data/portfolio_' + p['as_of'] + '/')
    (out / 'pack_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    root = 'data/portfolio_' + p['as_of']
    (out / 'README.md').write_text(f"""# Portfolio extraction pack — as of {p['as_of_iso']}

All clients, all sources, no client filter. Generated by `portfolio_sql.py`; full instructions in
`docs/PORTFOLIO_EXTRACTION_GUIDE.md` at the repository root.

1. Run every query in `01_profiles/` and save each result as `{root}/profiles/<source>_profile.csv`.
   Sum `rows_selected` per source and choose the number of parts so each part stays below your
   Starburst download limit. If the defaults below are not enough, regenerate this pack with
   `--buckets` (the parts of one source must all come from the same generation).
2. Run every query in `02_extracts/<source>/` and save each result under `{root}/` with the exact
   `save_as` name in `EXTRACTION_CHECKLIST.csv` (e.g. `{root}/clo/part_01_of_08.csv`).
3. Optional: `03_reference/clo_fx_reference.sql` -> `{root}/reference/clo_fx_reference.csv`.
4. Optional: `04_discovery/missing_sources_discovery.sql` -> `{root}/discovery/`.
5. Build the signals: `python3 -B run_portfolio.py --input {root} --as-of {p['as_of_iso']} --out runs/portfolio_{p['as_of']}_001`.

Parts per source in this pack: {', '.join(f'{k}={v}' for k, v in buckets.items())}.
Window {p['start_iso']} .. {p['as_of_iso']}; CLO prior snapshot gap {p['gap']} day(s); KYC lookback from {p['kyc_start_iso']};
covenant lookback from {p['cov_start_iso']}; approval lookback from {p['appr_start_iso']}.
""")
    print(f'Wrote {len(checklist)} SQL steps to {out}')


if __name__ == '__main__':
    main()
