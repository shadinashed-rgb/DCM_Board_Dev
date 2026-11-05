-- ============================================================================
-- extract_clo_rev_universe.sql   (RCF board — v2, REV-first, DEDUPED)
--
-- Identify the whole revolving universe from the CLO asset and download as CSV.
-- No name filter — the client name list becomes an *in-dashboard* filter
-- (upload-and-match), not an extraction filter.
--
-- IMPORTANT — the table is an EXPLODED join (one row per sub-limit × contract ×
-- account; up to ~90,000 rows for a single facility). Facility-level fields
-- (limit, pre-aggregated drawn) repeat on every row, so this query DEDUPES to
-- ONE ROW PER FACILITY (sub_lim_id) — otherwise summed commitment/drawn blow up
-- ~136×. See CLO_DUPLICATION_REVIEW.md. It also CARRIES a currency→USD FX rate,
-- because REV rows frequently lack their own fx (it lives on the account rows).
--
-- SNAPSHOT RULE — LATEST PER FACILITY, NOT A GLOBAL LATEST.
-- This query used to pin itself to one snapshot, `max(run_date)` over the whole
-- table, and inner-join on it. That silently dropped every row in any other
-- partition. It is only safe if the asset publishes atomically — one run_date
-- per publication, covering every leg — and the evidence says it does not:
-- clo_sample_data.csv is 100 rows of ONE mapping_system and ONE entity and still
-- carries THREE run_dates (20251217 / 20251218 / 20251201), with 18 of its 20 REV
-- rows outside the max. run_date there tracks obs_run_date_act row-for-row, which
-- reads as a per-record refresh stamp rather than a publication date.
--
-- So each facility now contributes rows from ITS OWN newest run_date. Nothing is
-- lost because a neighbouring leg published a day later, and every facility is
-- still internally consistent (one snapshot per facility, never a blend).
-- Consequence to expect: the output legitimately spans several run_dates, so
-- clo_dq_report.py will print "⚠ mixed snapshots". That is now the correct
-- state, and it is informational — it is not a blocking failure.
--
-- Run diagnose_run_date.sql first to measure what the old global-max filter was
-- actually costing on the real table.
--
-- ZOMBIE-FACILITY GUARD. Reaching back to older partitions could in principle
-- resurrect a facility that a newer snapshot dropped. Two things prevent that:
-- the live-RCF predicate (positive limit + future maturity) is applied inside
-- `candidates` before the per-facility max, so an expired or zeroed facility can
-- never qualify from any snapshot; and LOOKBACK_DAYS bounds how far back we look.
--
--   Table  : hive.clo_prod.clo_cda_contract_lvl   (contract / sub-limit grain)
--   Engine : Trino / Presto (adjust for Hive/Spark SQL if needed)
--   Output : ONE row per revolving facility → save as CSV, then feed to
--            build_clo_signals.py --all --out clo_rcf_universe
-- ============================================================================

WITH bounds AS (
    -- ── EDIT HERE: LOOKBACK_DAYS ────────────────────────────────────────────
    -- How far back a facility's freshest snapshot may sit. Widen it if the
    -- diagnostic shows legs publishing on a slower cadence; narrow it if the
    -- scan is expensive. Comparison stays on the raw varchar partition key
    -- (run_date is 'YYYYMMDD', fixed width, so string order = date order) —
    -- casting run_date to a date in the WHERE would defeat partition pruning.
    SELECT format_datetime(
               date_add('day', -90, date_parse(max(t.run_date), '%Y%m%d')),
               'yyyyMMdd') AS min_run_date
    FROM "hive"."clo_prod"."clo_cda_contract_lvl" t
),
candidates AS (
    -- The live revolving universe across every snapshot in the window (still one
    -- row per exploded contract/account line). facility_key is built HERE because
    -- it is the grouping key for latest_per_fac below, and it uses the identical
    -- coalesce chain as the final GROUP BY — a different key at either end would
    -- mix facilities together.
    SELECT t.*,
           coalesce(nullif(trim(t.sub_lim_id), ''),
                    nullif(trim(t.rct_facility_ref), ''),
                    nullif(trim(t.facility_id), '')) AS facility_key
    FROM "hive"."clo_prod"."clo_cda_contract_lvl" t
    WHERE
        t.run_date >= (SELECT b.min_run_date FROM bounds b)
        -- REV-first universe. Keep as an editable list — other legs may add codes.
        AND upper(trim(t.local_product_type_lbs)) IN ('REV')
        -- live RCF: positive commitment + future maturity (strings → parse before
        -- compare). Applied before the per-facility max — this is the zombie guard.
        AND try_cast(t.facility_limit_amount AS double) > 0
        AND try_cast(substr(trim(t.facility_maturity_date), 1, 10) AS date) > current_date
),
latest_per_fac AS (
    -- Each facility's own freshest snapshot — replaces the single global max.
    -- facility_key IS NULL rows are dropped: they cannot be deduped to a facility
    -- anyway (CLO_DQ_FINDINGS.md: sub_lim_id ~0.4% blank).
    SELECT c.facility_key,
           max(c.run_date) AS run_date
    FROM candidates c
    WHERE c.facility_key IS NOT NULL
    GROUP BY c.facility_key
),
fx_by_date AS (
    -- Currency → USD rate PER SNAPSHOT, sourced from whatever rows carry it (REV
    -- facility rows often don't — it lives on the account rows), which is why this
    -- reads the base table rather than `candidates`.
    --
    -- Keyed by run_date as well as currency: the old fx CTE was pinned to the same
    -- single snapshot as the data, so a facility sitting in any other partition lost
    -- its rate, its commitment resolved to NULL, and it fell out of board totals —
    -- the same bug wearing a second hat.
    --
    -- instrument_currency_fx_to_usd is decimal(38,6), NOT varchar: trim/coalesce
    -- against '' fails with "cannot find common type between decimal(38,6) and
    -- varchar(0)". Test for a parseable number instead.
    SELECT t.facility_currency AS ccy,
           t.run_date          AS run_date,
           max(try_cast(t.instrument_currency_fx_to_usd AS double)) AS fx_to_usd
    FROM "hive"."clo_prod"."clo_cda_contract_lvl" t
    WHERE t.run_date >= (SELECT b.min_run_date FROM bounds b)
      AND try_cast(t.instrument_currency_fx_to_usd AS double) IS NOT NULL
    GROUP BY t.facility_currency, t.run_date
),
fx_any AS (
    -- Fallback for a currency whose own snapshot carries no usable rate. Derived
    -- from fx_by_date, so it costs no extra scan.
    --
    -- NOTE — max() here, and in fx_by_date, is a known divergence from
    -- build_clo_signals.shape_facilities and profile_clo_asset.sql, which both take
    -- the MEDIAN because the rate column is dirty (see profile_clo_asset.sql:38-43).
    -- Left as-is deliberately: reconciling it changes reported amounts and belongs
    -- in its own change, not this one.
    SELECT f.ccy,
           max(f.fx_to_usd) AS fx_to_usd
    FROM fx_by_date f
    GROUP BY f.ccy
),
rev AS (
    -- Keep only each facility's freshest rows, then resolve FX.
    --
    -- FX IS RESOLVED HERE, per row, and deliberately not in the outer query. The outer
    -- SELECT aggregates under GROUP BY facility_key, and referencing a LEFT JOINed CTE
    -- column from inside an aggregate there — max(f.fx_to_usd) — is rejected by Trino
    -- with "Column 'f.fx_to_usd' cannot be resolved". Resolving the rate at row level
    -- keeps the fx join in the scope that owns it and leaves the outer query aggregating
    -- nothing but `rev` columns.
    --
    -- Precedence: the row's own rate, else the rate for its OWN snapshot, else any
    -- snapshot's rate for that currency, else 1.0 for USD. (Per-row resolution then
    -- max, rather than max-then-coalesce; per-row is the more defensible of the two
    -- because every row ends up with a rate that is valid for its own currency.)
    SELECT c.*,
           coalesce(try_cast(c.instrument_currency_fx_to_usd AS double),
                    fd.fx_to_usd,
                    fa.fx_to_usd,
                    CASE WHEN c.facility_currency = 'USD' THEN CAST(1.0 AS double) END
           ) AS fx_to_usd_resolved
    FROM candidates c
    JOIN latest_per_fac lf
      ON lf.facility_key = c.facility_key
     AND lf.run_date     = c.run_date
    LEFT JOIN fx_by_date fd
      ON fd.ccy      = c.facility_currency
     AND fd.run_date = c.run_date
    LEFT JOIN fx_any fa
      ON fa.ccy = c.facility_currency
)
-- DEDUP to one row per facility. Amounts are cast to double so max() is numeric (not
-- lexicographic); facility-level fields are constant per facility so max() recovers them.
SELECT
    r.facility_key,
    -- identity / aggregation
    max(r.rct_mastergroup_id)                    AS rct_mastergroup_id,
    max(r.rct_mastergroup_name)                  AS rct_mastergroup_name,
    max(r.rct_group_name)                        AS rct_group_name,
    max(r.obligor_cin)                           AS obligor_cin,
    max(r.rct_local_customer_id)                 AS rct_local_customer_id,
    max(r.obligor_customer_name)                 AS obligor_customer_name,
    max(r.borrower_name)                         AS borrower_name,
    max(r.rct_obligor_name)                      AS rct_obligor_name,
    max(r.rct_gid)                               AS rct_gid,
    -- facility identity
    max(r.lim_id)                                AS lim_id,
    max(r.sub_lim_id)                            AS sub_lim_id,
    max(r.facility_id)                           AS facility_id,
    max(r.facility_name)                         AS facility_name,
    max(r.rct_facility_ref)                      AS rct_facility_ref,
    max(r.local_product_type_lbs)                AS local_product_type_lbs,
    max(r.rct_facility_type_code)                AS rct_facility_type_code,
    -- amounts (facility-level; numeric max)
    max(try_cast(r.facility_limit_amount AS double))            AS facility_limit_amount,
    max(try_cast(r.ag_acc_bal_drawn_sub_lim_usd AS double))     AS ag_acc_bal_drawn_sub_lim_usd,
    max(try_cast(r.account_balance_drawn_amount_usd AS double)) AS account_balance_drawn_amount_usd,
    max(r.facility_currency)                     AS facility_currency,
    -- FX: already resolved per row in `rev` (own rate → currency rate → 1.0 for USD),
    -- so this is a plain max over one of rev's own columns. No fx join out here.
    max(r.fx_to_usd_resolved)                    AS instrument_currency_fx_to_usd,
    -- maturity (ISO strings sort correctly)
    max(r.facility_maturity_date)                AS facility_maturity_date,
    max(r.max_of_fac_maturity_date)              AS max_of_fac_maturity_date,
    -- sector / geography
    max(r.rct_industry_level_1)                  AS rct_industry_level_1,
    max(r.rct_industry_level_2)                  AS rct_industry_level_2,
    max(r.rct_dm_country)                        AS rct_dm_country,
    max(r.rct_dm_region)                         AS rct_dm_region,
    max(r.obligor_country_of_incorporation_name) AS obligor_country_of_incorporation_name,
    -- provenance
    max(r.source_system)                         AS source_system,
    max(r.mapping_system)                        AS mapping_system,
    max(r.hsbc_booking_legal_entity)             AS hsbc_booking_legal_entity,
    max(r.branch)                                AS branch,
    max(r.primary_borrower_indicator)            AS primary_borrower_indicator,
    -- This facility's OWN as-of date. Every row surviving the latest_per_fac join
    -- shares one run_date, so max() just recovers it. Across the file these will
    -- differ between facilities — by design; see the snapshot rule in the header.
    max(r.run_date)                              AS run_date
FROM rev r
GROUP BY r.facility_key
;
