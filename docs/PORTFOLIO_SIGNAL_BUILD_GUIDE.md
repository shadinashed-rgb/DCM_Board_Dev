# Portfolio signal build guide — from the extracts to signals for every client

This guide explains how the Bond Radar signals are built for the **whole portfolio** from the extracts described in `docs/PORTFOLIO_EXTRACTION_GUIDE.md`: what runs, how each signal is computed from which columns, how client groups are found without a target list, what the outputs mean, and how to review them.

- **Code:**
  - `development/run_portfolio.py` (entry point)
  - `development/pvd_client_cohort_lab/portfolio.py` (pipeline)
  - `development/pvd_client_cohort_lab/engine/bond_radar.py` (signal rules, development-2, unchanged in meaning)
- **Tests:**
  - `tests/test_portfolio.py`: synthetic multi-group portfolio, every path
  - `tests/test_portfolio_regression.py`: real three-client data reproduces the targeted results without being told the clients
  - `tests/test_portfolio_sql.py`: the SQL pack

---

## 1. Run it

From `development/`:

```sh
# 1. Make sure the code and rules are healthy
python3 -B -m unittest discover -s pvd_client_cohort_lab/tests -q
python3 -B -m unittest discover -s pvd_client_cohort_lab/engine/tests -q

# 2. Build the signals for every client (use the same as-of date as the SQL pack)
python3 -B run_portfolio.py --input data/portfolio_20261106 --as-of 2026-11-06 --out runs/portfolio_20261106_001
```

**Options:**

| Option | Use |
|---|---|
| `--fx-from-clo` | Convert drawings to EUR with the CLO FX reference so the SIG01 EUR 50m test can be evaluated. Unvalidated; for exploration until an FX source is agreed. The rates used are written to `FX_USED.csv` |
| `--business-lines GBM,CMB` | Limit the group matrix and candidate list to these Counterparty Core business lines. The evidence file keeps every client |
| `--extra-links reviewed_links.csv` | Add reviewed identity mappings in `identity_links` format, e.g. PVD relationship → mastergroup, which has no ID route otherwise |

Every run writes a **new folder**, and the raw files are never modified. The run stops before processing if a part is missing, headers differ between parts, or required columns are absent (`INPUT_CHECK.json`).

**Try it without real data:**

```sh
python3 -B pvd_client_cohort_lab/portfolio_demo.py --out data/portfolio_demo
python3 -B run_portfolio.py --input data/portfolio_demo --as-of 2026-11-06 --out runs/portfolio_demo_001 --extra-links data/portfolio_demo/reviewed_links.csv
```

## 2. What happens, step by step

| Step | What it does | Why |
|---|---|---|
| **1. Input check** | Every source folder: all `part_XX_of_NN` present, identical headers, required columns, row counts and file hashes | A missing part silently loses clients; header drift means parts came from different SQL |
| **2. Group discovery (identity links)** | Builds `identity_links_portfolio.csv` for every client (see section 3) | No target list. Groups come from the data |
| **3. Signal engine** | Runs the development-2 rules over all rows of all sources. Each source is reduced to observations (one per record key and snapshot); conflicts withhold metrics | Same rules as the three-client run, so results are comparable |
| **4. Evidence export** | One row per signal or context record, with group name, identifiers, measures, the reason it is unvalidated, and `source/part_XX:record N` lineage | Every number traces back to its CSV record |
| **5. CRR context** | Application Ratings: latest snapshot per source/country/CARM, effective periods, CRR per CIN → group | Same CRR rules as the targeted run (shared `crr_row`) |
| **6. SIG02 approval dates** | Links each facility's `credit_proposal_serial_no` (+ CIN) to Application Ratings `approval_dt`; re-tests the 90 days on the approval date | Meeting decision: the event date is the credit approval date |
| **7. Summaries** | Group × signal matrix, candidate list, maturity windows, source coverage, workbook, review | What a reviewer or the dashboard needs |

## 3. How client groups are found (no target list)

Every record must be attributed to a **mastergroup** to be useful. The routes, in order of precedence:

| Route | Basis label in `mapping_status` | Used for |
|---|---|---|
| Source's own valid mastergroup (CLO `rct_mastergroup_id`, DRR `drr_mastergroup_id`) | `original_preserved` / `source_mastergroup_unverified` | CLO, DRR |
| **Counterparty Core**, latest snapshot on or before the as-of date, active lifecycle status: CIN → mastergroup and GID → mastergroup | `counterparty_core_latest` | All sources with a CIN or GID |
| **Native source association**, only where Counterparty Core has no mapping for a CIN: the CIN → mastergroup that CLO or DRR records, if unambiguous | `native_source_cin_mastergroup` | Facilities, KYC, Application Ratings, CLO rows with a blank group |
| Facilities `relationship_id` → CIN → mastergroup | `facilities_relationship_to_cin+counterparty_core_latest` | Covenants only (they carry no CIN) |
| Reviewed links you supply (`--extra-links`) | your label, e.g. `reviewed_pvd_link` | PVD (relationship grain, no mastergroup ID) and any correction |

**Safeguards:**
- A CIN that maps to **two groups** is ambiguous, and its records get no group. Invalid groups such as `NO MSG` are never treated as groups.
- Closed or inactive mappings and older snapshots are not used.
- A CLO row whose group is blank can take its group from an unambiguous identity link of its CIN. It is labelled `group_from_identity_link` in `cohort_mapping_status`.
- **All of these are development links, not reviewed approvals.** The labels make that visible on every row. Before production, the mapping must be reviewed (see section 7).

## 4. How each signal is built

All rules are the development-2 rules agreed with DCM. Thresholds and options live in `pvd_client_cohort_lab/profiles/portfolio_dev2.json`. Nothing becomes a `business_trigger` until a rule's `definitions_verified` flag is switched on after owner sign-off; until then, the *test* flags below identify **candidates**.

### SIG01 — Material drawing on a Cat A bank facility

| | |
|---|---|
| **Source columns** | CLO `sub_lim_id`, `local_product_type_lbs`, `facility_drawn_amount` (default, blank today), `ag_acc_bal_drawn_sub_lim_usd` (populated, compared separately), `facility_currency`, `deal_indicator_sole_lender`; Facilities `facility_id`, `limit_cat` |
| **Computation** | 1. For each REV/TERM sub-limit, drawing = drawn at the latest snapshot − drawn at the prior snapshot (same sub-limit, gap recorded).<br>2. Convert to EUR only with a configured FX rate.<br>3. HSBC's drawing ≥ EUR 50m → material (HSBC's share can never exceed the whole facility). Otherwise, if a participation share is known (sole lender = 100%), the inferred total = drawing ÷ share is tested.<br>4. Cat A comes from Facilities where `facility_id` = CLO `sub_lim_id` |
| **Candidate when** | `material_drawing_for_testing = True` **and** `cat_a_eligible = True` (`review_type = material_drawing_for_testing`) |
| **Not assessed when** | Blank drawn imputed to zero (`imputed_values_not_assessable`), no prior snapshot, no FX rate (`fx_rate_not_configured`), share below the threshold with no participation (`hsbc_share_below_threshold_participation_unknown`) |
| **Summary columns** | `sig01_comparisons`, `sig01_material`, `sig01_material_cat_a`, `sig01_largest_drawn_without_prior` |

### SIG02 — New RCF, term loan or bridge (credit approval date)

| | |
|---|---|
| **Source columns** | Facilities `facility_id`, `product_code`, `facility_creation_date`, `loan_approva_dt`, `credit_proposal_serial_no`, `cin`, `proposed_limit`, `facility_ccy`; Application Ratings `credit_proposal_serial_no`, `cin`, `approval_dt` |
| **Computation** | 1. Event date = Application Ratings `approval_dt`, linked by serial (same CIN preferred).<br>2. If there is no link, `loan_approva_dt` is used when valid, else `facility_creation_date`, labelled as a candidate approval date.<br>3. Age = as-of − event date. Contexts with conflicting products or dates are withheld |
| **Candidate when** | Age ≤ 90 days (`recent_creation_for_testing = True`, `review_type = recent_approval_for_testing`) |
| **Summary columns** | `sig02_contexts`, `sig02_recent_approvals`, `sig02_newest_approval` |

### SIG03A / SIG03B — Swap roll / new pre-hedge enquiry

**No source yet.** Run the discovery SQL. When a derivatives trade or enquiry table is found, add it as a source in `engine/bond_radar.py` `SOURCES`, add its rule, and add it to `portfolio_sql.py`.

### SIG04 — KYC onboarding / signatory refresh

| | |
|---|---|
| **Source columns** | KYC `cin`, `related_case_id`, `review_purpose_code`, `review_request_created_time_stamp`, `related_case_status` |
| **Computation** | Case requested within the 90-day lookback with purpose NTB or TRG (development codes) |
| **Status** | Always `needs_validation` until purpose meanings are agreed. A Trigger case alone is not a financing event |

### SIG06 — Financial covenant breach or pressure

| | |
|---|---|
| **Source columns** | Covenants `covenant_type`, `active_testing_final_value`, `active_testing_testing_threshold_value`, `active_testing_testing_threshold_operator`, `active_testing_approval_status`, `reporting_dt`, `relationship_id` |
| **Computation** | For a financial test with a maximum-type operator (`<`, `<=`): headroom = maximum − actual. Pressure when headroom ≤ 0.5 turns; breach when the compliance condition fails |
| **Candidate when** | `covenant_pressure_for_testing = True` or `covenant_breach_for_testing = True` |
| **Lead to validate** | DRR `covenaint_waiver_date` is extracted; a recent waiver may indicate pressure (owner to confirm) |

### SIG07 — Rating advisory

Requires CME call reports, which are not integrated. No evidence until CME access is decided (with SIG05).

### Context (not signals)

| Context | Source | What it shows |
|---|---|---|
| `CTX_UTIL` | CLO, DRR, PVD | Utilisation = utilised ÷ compatible limit (same currency, units and date); > 70% flagged. Not covenant pressure |
| `CTX_CREDIT` | Facilities (`limit_cat`, grades), PVD (CRR, category), Application Ratings (CRR) | Credit category and CRR. Competing CRRs are kept; no numeric direction |
| Maturity windows | Facilities (`loan_maturity_dt` → `final_loan_maturity_dt` → `facility_expiry_dt`), CLO (`facility_maturity_date`) | Facilities maturing in < 12 months and 12–24 months (requirement DASH03). Counts only; no totals across currencies |

## 5. Outputs (in the run folder)

| File | What it is | Use it for |
|---|---|---|
| `GROUP_SIGNAL_MATRIX.csv` | **One row per mastergroup** with group name, business line, country, sector, and per-signal counts, candidates, peak utilisation, CRRs, maturity windows and sources. `development_order` is a transparent ordering (signals firing → candidates → near maturities → evidence volume), **not a score** | The portfolio view: which groups to look at first |
| `CANDIDATES.csv` | Every test candidate (SIG01 material Cat A drawing, SIG02 approved ≤ 90 days, SIG06 pressure/breach) with identifiers and lineage | Owner review and banker conversations |
| `BOND_RADAR_SIGNAL_EVIDENCE.csv` | All records (signals and context), same columns as the three-client output plus `client_id` and `group_name` | Drill-down, the dashboard, audit |
| `MATURITY_WINDOWS.csv` | Facilities maturing within 24 months | Refinancing context |
| `SOURCE_COVERAGE.csv` | Per source: parts, input rows, evidence, share linked to a group, observation dates | Data quality and freshness |
| `GROUPS.csv` | Group dimension from Counterparty Core | Names, business lines, filters |
| `PORTFOLIO_SIGNALS.xlsx` | The matrix, candidates, maturity windows, coverage and groups in one workbook | Sharing |
| `REVIEW.md`, `RUN_SUMMARY.json` | Headline numbers, first groups in order, coverage and link statistics | Quick review |
| `INPUT_CHECK.json`, `identity_links_portfolio.csv`, `config_portfolio.json`, `engine/` | Input checks, the links used, the exact configuration, the engine database with lineage and quality issues | Reproducibility |

## 6. How to review a run

1. **`INPUT_CHECK.json`**: no problems, and row counts match the checklist.
2. **`SOURCE_COVERAGE.csv`**: every source has evidence and a high group-link rate.
   - PVD will be low without `--extra-links`.
   - A low rate elsewhere means CINs are missing from Counterparty Core; check its extract.
3. **`RUN_SUMMARY.json` → `links`**:
   - `cins_ambiguous` should be small.
   - `cins_linked_by_native_source` shows how much depends on the second route.
4. **`GROUP_SIGNAL_MATRIX.csv`**: sort by `development_order`. Check the first groups against what bankers know.
5. **`CANDIDATES.csv`**: for each candidate, open the record in the evidence file and follow `source_record_references` to the source row.
6. Send owner questions on the definitions to the credit team: SIG02 approval meaning and product codes; SIG01 drawn field, FX and participation.

## 7. What is still needed before production

| Need | Why | Owner |
|---|---|---|
| Reviewed identity mapping (Counterparty Core settings, CIN namespaces, PVD relationship → group) | Today's links are development links, labelled on every row | Data owners / Shadi |
| LoanIQ drawn amount by facility, HSBC participation share, agreed FX source | SIG01 cannot be assessed as material without them | Credit team |
| Confirmation that `approval_dt` is the approval of a new facility; RCF / term / bridge product codes | SIG02 trigger definition | Credit team |
| Derivatives trade source (SIG03A); pre-hedge enquiry source (SIG03B) | No data yet | Markets data owners |
| Genuine financial covenant tests; owner view on the DRR waiver date | SIG06 | Credit risk |
| CME call-report decision | SIG07 / SIG05 | Governance |
| Scheduled extracts instead of manual downloads | Daily or weekly refresh | Data engineering / AI Markets |

## 8. Performance

Measured on a synthetic portfolio of 20,000 groups with 135,000 input rows: about 2 minutes and 125,000 records on the development container. The engine is single-threaded SQLite and scales roughly linearly. For several million input rows, expect tens of minutes. If that is too slow:

- raise the number of parts (this does not change processing);
- narrow the CLO products or windows when regenerating the pack;
- run per business line using a scoped Counterparty Core extract (`--cp-business-lines` in `portfolio_sql.py`).

## 9. Extending

| Change | Where |
|---|---|
| New signal source | Add the table to `engine/bond_radar.py` `SOURCES` (required/desired columns), its rule in `build_signals`, its columns and snapshot rule in `portfolio_sql.py` (`COLUMNS`, `TABLES`, `body`), observed columns in `profiles/source_columns_observed.json`, and a scenario in `portfolio_demo.py` with a test |
| Change a threshold or lookback | `profiles/portfolio_dev2.json` (rules) and the `portfolio_sql.py` options (extraction windows) |
| Owner signs off a rule | Set that rule's `definitions_verified: true` in the profile; `business_trigger` is then filled for qualifying records |
