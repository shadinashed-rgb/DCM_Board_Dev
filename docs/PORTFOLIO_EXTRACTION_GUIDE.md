# Portfolio extraction guide — all clients, all sources

This guide explains how to extract the data for **every client** from the internal sources that the Bond Radar signals use, so that the signals can be built across the portfolio rather than for the three development clients. Each step says what to do, which file to save, and why.

- **SQL pack:** `development/pvd_client_cohort_lab/sql_templates/portfolio_20261106/`
- **Generator:** `development/pvd_client_cohort_lab/portfolio_sql.py`, which writes a fresh pack for any date or split
- **Next step:** after extraction, follow `docs/PORTFOLIO_SIGNAL_BUILD_GUIDE.md`

---

## 1. What changed from the three-client SQL

| Earlier pack (`current_20261103`, `sig07_crr_20261104`) | Portfolio pack (`portfolio_20261106`) | Why it matters |
|---|---|---|
| Every query filtered to Vodafone, Siemens Energy and SoftBank by hard-coded mastergroup, CIN and GID lists | **No client filter.** Every client in each source is extracted | Signals can be built for the whole portfolio, without knowing the clients in advance |
| `SELECT t.*` (100–400 columns) | **Only the columns the rules, identity and lineage need** (20–45 per source) | Smaller files. CLO in particular is an *exploded* contract × account table (up to ~90,000 rows per facility); keeping only sub-limit-level columns collapses it to one row per sub-limit × snapshot × borrower |
| Facilities and KYC used one *global* latest date | **Latest snapshot per publishing partition** (source system × country, group, or relationship) | A global latest date silently drops countries that publish later; this was seen with Siemens DE |
| One file per source | **Parts** (`part_01_of_08.csv` …) using a stable hash split | Each download stays under the Starburst export limit; the pipeline re-combines the parts and checks none is missing |
| Application Ratings: all versions for chosen CINs | Applications **effective at the snapshot** (CRR context) **plus any approved within 400 days** (SIG02 approval dates) | Covers both uses without downloading full history |
| No route for covenants to groups | Facilities `relationship_id` + `cin` are extracted together | Gives covenants (keyed by relationship) a route to a mastergroup |

Unchanged:
- The SQL is **read-only**.
- `DISTINCT` removes **identical rows only**. Nothing is summed, and no conflicting value is picked. Conflicts are detected downstream and the metric is withheld.

## 2. The sources and what each one feeds

| # | Source (Starburst table) | Feeds | Snapshot rule in the SQL | Default parts |
|---|---|---|---|---|
| 1 | `delta.prod_party_gda.counterparty_core` | **Identity backbone** for all signals: CIN/GID → mastergroup, group name, business line, country | Latest **two** snapshots per `source_system_instance_country` | 4 |
| 2 | `hive.clo_prod.clo_cda_contract_lvl` | **SIG01** drawings (REV + TERM + blank product), utilisation context, maturity windows | Per group: latest snapshot **and** the newest one at least 1 day earlier (the comparison side) | 8 |
| 3 | `delta.prod_credit_and_lending_gda.facilities_limits` | **SIG02** new facilities, **SIG01** Cat A lookup (`limit_cat`), credit context, maturity windows, relationship → CIN route | Latest snapshot per source system × country; versions effective at that date | 2 |
| 4 | `delta.prod_credit_and_lending_mda.drr_facility_limits` | Utilisation context; `covenaint_waiver_date` as a lead for SIG06 | Latest `reporting_date` per group | 2 |
| 5 | `hive.pvd_prod_wave.pvd_omnia_drr` | Utilisation and credit context (relationship grain; no mastergroup ID) | Latest `joi_date` per relationship | 1 |
| 6 | `delta.prod_party_gda.kyc` | **SIG04** KYC cases | Latest snapshot per source system; cases requested in the last 365 days | 1 |
| 7 | `delta.prod_credit_and_lending_gda.covenants` | **SIG06** covenant breach / pressure | Latest snapshot per source system × country; tests reported or due in the last 400 days | 1 |
| 8 | `delta.prod_credit_and_lending_gda.application_ratings` | **SIG02** credit approval dates; CRR credit context | Latest snapshot per source / country / CARM instance; effective or approved in the last 400 days | 1 |
| ref | CLO `instrument_currency_fx_to_usd` | Optional FX for the SIG01 EUR 50m test (**unvalidated**) | Median per currency and snapshot | 1 |
| disc | `information_schema` (delta, hive) | Finding the **missing** sources: derivatives/swaps (SIG03A/B), covenants, LoanIQ drawings and participation (SIG01), call reports (SIG07) | Metadata only | 1 |

All column names in the pack are checked automatically against the real schemas seen in the earlier extracts (`profiles/source_columns_observed.json`). The pack is also parsed as Trino SQL, and checked to contain no client-specific filter (`tests/test_portfolio_sql.py`).

## 3. Before you start

1. **Pick the as-of date.** The pack in the repository uses **2026-11-06**. For another date, regenerate it (from `development/`):

   ```sh
   python3 -B pvd_client_cohort_lab/portfolio_sql.py --as-of 2026-11-20 \
       --out pvd_client_cohort_lab/sql_templates/portfolio_20261120
   ```

2. **Create the landing folder** on your machine, with one sub-folder per source. The name must match the as-of date in the pack:

   ```
   development/data/portfolio_20261106/
     profiles/  counterparty/  clo/  facilities/  drr/  pvd/  kyc/  covenants/  application_ratings/  reference/  discovery/
   ```

   `development/data/` is git-ignored. Client data never goes into the repository.

3. **Open `EXTRACTION_CHECKLIST.csv`** from the pack. It lists every step, the SQL file and the exact save-as name, and has empty `rows_downloaded` and `status` columns for you to fill in as you go.

## 4. Step-by-step

### Step 1 — Profile each source (8 small queries)

Run each file in `01_profiles/` and save the result as `profiles/<source>_profile.csv`.

Each profile returns **how many rows the extract would download**, by partition or snapshot, plus the number of distinct bucket keys. Use it to:

- **Check the source is reachable and has data in the window.** An empty profile means one of three things: wrong date window, no access, or the table has moved. It does *not* mean the clients have no activity.
- **Choose the number of parts.** Add up `rows_selected`, then divide by your download limit. If the default parts are too few, for example CLO needs 20 parts instead of 8, regenerate the pack with `--buckets clo=20,counterparty=6`. Every part of one source must come from the same generation; the pipeline refuses mixed splits.

### Step 2 — Extract each source in parts (default 21 queries)

For each file in `02_extracts/<source>/`:

1. Copy the SQL into Starburst and run it.
2. Download the full result as **CSV with headers**.
3. Save it as `<source>/part_XX_of_NN.csv`, exactly as in the header comment of the SQL file and in the checklist.
4. Record the row count in the checklist.

Rules that keep the data trustworthy:

- **Do not open or re-save the CSV in Excel.** Excel turns long IDs into scientific notation and drops leading zeros, and those IDs cannot be recovered.
- **Keep a header-only file** if a part returns no rows. An empty part is valid; a *missing* part means lost clients.
- **Run every part.** The pipeline stops with `missing parts [..] of N` if one is absent.
- **Use the same pack for every part of a source.** A different `--buckets` or date produces different splits, and the pipeline stops with `parts come from different splits`.
- If Starburst **times out** on a part, regenerate with more parts for that source; smaller parts are faster. Do not add `LIMIT`, because it silently truncates.
- Note the export time and any error in the checklist. Do not use file modification times as export times.

What each extract does, in plain terms:

| Source | What the query selects |
|---|---|
| **counterparty** | Every CIN and GID with its mastergroup, group name, business line, designation, country, sector and lifecycle status, from the latest two snapshots. This is how the pipeline knows which client group every other record belongs to |
| **clo** | For every revolving, term and blank-product sub-limit: identity (CIN, GID, native mastergroup), drawn amounts (`facility_drawn_amount` and the populated `ag_acc_bal_drawn_sub_lim_usd`), limit, currency, sole-lender flag, maturity, two snapshots per group. Account-level columns are left out on purpose |
| **facilities** | Every effective facility version: CIN, relationship, product, Cat A/B/S (`limit_cat`), creation date, approval placeholder (`loan_approva_dt`), credit proposal serial (the link to the approval date), proposed limit, maturity and cancellation flags |
| **drr** | Every exposure at its latest reporting date: limits and utilisation with their currencies, committed/cancellable/parent flags, and the covenant-waiver date |
| **pvd** | Latest month-end per relationship: utilisation, limits, CRR and category (context only) |
| **kyc** | KYC cases requested in the last 365 days, with purpose code, status and dates; `cdd_topco_legal_name` is joined to text |
| **covenants** | Covenant tests reported or due in the last 400 days: type, actual/final value, threshold, operator, approval status and result |
| **application_ratings** | Applications effective at the snapshot (CRR) and applications approved in the last 400 days (approval dates for SIG02) |

### Step 3 — Optional FX reference

Run `03_reference/clo_fx_reference.sql` and save the result as `reference/clo_fx_reference.csv`.

It lets the pipeline convert drawings to EUR for the SIG01 EUR 50m test, using the median CLO rate per currency. **This is not an agreed FX source.** Use it for exploration only, with `--fx-from-clo`, until the credit team names an FX source and date.

### Step 4 — Optional discovery of missing sources

Run each statement in `04_discovery/missing_sources_discovery.sql` and save the results as `discovery/tables_by_name.csv` and `discovery/columns_by_name.csv`.

The searches look for tables and columns that could supply:

| Signal | What to look for |
|---|---|
| SIG03A / SIG03B | Swaps, derivatives, OTC, FX trades, hedges, pricing requests or RFQs |
| SIG06 | Covenants, net debt, EBITDA, leverage |
| SIG01 | LoanIQ, drawdowns, participation share |
| SIG07 | Call reports, CME |

An empty result can mean "no metadata permission". It never proves a source doesn't exist.

### Step 5 — Check what you have

From `development/`, before building:

```sh
python3 -B -c "import sys; sys.path.insert(0,'pvd_client_cohort_lab'); import portfolio, json; r,p=portfolio.check_inputs('data/portfolio_20261106'); print(json.dumps(p, indent=1)); print({k:(v['parts'],v['rows']) for k,v in r.items()})"
```

An empty problem list means every part is present, the headers agree and the required columns exist. The build in `docs/PORTFOLIO_SIGNAL_BUILD_GUIDE.md` runs the same check and stops if anything is wrong.

## 5. Expected folder at the end

```
development/data/portfolio_20261106/
  profiles/      counterparty_profile.csv … application_ratings_profile.csv
  counterparty/  part_01_of_04.csv … part_04_of_04.csv
  clo/           part_01_of_08.csv … part_08_of_08.csv
  facilities/    part_01_of_02.csv  part_02_of_02.csv
  drr/           part_01_of_02.csv  part_02_of_02.csv
  pvd/           part_01_of_01.csv
  kyc/           part_01_of_01.csv
  covenants/     part_01_of_01.csv
  application_ratings/  part_01_of_01.csv
  reference/     clo_fx_reference.csv          (optional)
  discovery/     tables_by_name.csv  columns_by_name.csv   (optional)
```

## 6. Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `Column 'x' cannot be resolved` | The live schema differs from the schema seen in earlier extracts | Run `SHOW COLUMNS FROM <table>`, update the column list in `portfolio_sql.py` (`COLUMNS`) and regenerate. Keep `profiles/source_columns_observed.json` in step |
| Function not registered (`xxhash64`, `from_big_endian_64`) | Older Trino | In the last `WHERE` line of each part, replace `MOD(ABS(from_big_endian_64(xxhash64(to_utf8(COALESCE(<key>, '~'))))), N)` with `MOD(from_base(substr(to_hex(md5(to_utf8(COALESCE(<key>, '~')))), 1, 8), 16), N)`, keeping `<key>`, `N` and the bucket number. Do this for every part of the source |
| Profile is empty for a source | Wrong window, no access, or a moved table | Widen `--window-days`; check access; check the table with discovery |
| A part is much larger than the others | One very large group (bucketing keeps a group together) | Acceptable. If it exceeds the limit, increase the number of parts for that source |
| Download stops at a round number of rows | UI download cap | Use more parts; never accept a capped file |
| KYC returns many routine cases | 365-day window over all purposes | Expected. SIG04 rules decide what counts; shorten with `--kyc-lookback-days` if the files are too large |
