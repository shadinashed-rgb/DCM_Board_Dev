"""Snapshot reduction, version validity and development-link boundaries."""
import csv
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from refresh import select_current, sql_pack, test_links, process
from refresh import write_csv
from cohort import config, ROOT, engine


class RefreshTests(unittest.TestCase):
    def test_clo_retains_two_group_dates_not_latest_row_per_old_facility(self):
        rows = [dict(run_date=d, rct_mastergroup_id='MG001356', facility_id=f) for d, f in [('20261001','OLD'), ('20261028','BASE'), ('20261030','NEW')]]
        selected, stats, dates = select_current('clo', rows + [rows[-1]], '2026-11-03')
        self.assertEqual([r['facility_id'] for r in selected], ['BASE','NEW'])
        self.assertEqual(stats['exact_duplicates_removed'], 1)
        self.assertEqual(dates['MG001356'], ['2026-10-28','2026-10-30'])

    def test_facilities_effective_dates_keep_open_historical_flag_and_overlaps(self):
        common = dict(run_date='20261030', facility_id='F1', latest_record='HISTORICAL')
        rows = [dict(common, record_start_dt='20250101', record_end_dt='20260601'),
                dict(common, record_start_dt='20260602', record_end_dt='99991231'),
                dict(common, record_start_dt='20260701', record_end_dt='99991231'),
                dict(common, record_start_dt='20261101', record_end_dt='99991231')]
        selected, stats, _ = select_current('facilities', rows, '2026-11-03')
        self.assertEqual(len(selected), 2)  # overlapping valid versions remain for conflict checks
        self.assertEqual(stats['out_of_effective_period_removed'], 2)

    def test_future_load_and_latest_snapshot_do_not_resurrect_old_facility(self):
        rows = [dict(reporting_date='20261029', run_date='20261030', drr_mastergroup_id='MG001356',facility_id='OLD'),
                dict(reporting_date='20261030', run_date='20261031', drr_mastergroup_id='MG001356',facility_id='CURRENT'),
                dict(reporting_date='20261102', run_date='20261104', drr_mastergroup_id='MG001356',facility_id='FUTURE')]
        selected, stats, _ = select_current('drr', rows, '2026-11-03')
        self.assertEqual([r['facility_id'] for r in selected], ['CURRENT'])
        self.assertEqual(stats['invalid_or_future_rows_removed'], 1)

    def test_counterparty_keeps_point_in_time_and_current_snapshots(self):
        rows = [dict(run_date=d,mastergroup_esr_identifier='MG001356') for d in ['20260901','20261028','20261030','20261102']]
        selected, _, _ = select_current('counterparty', rows, '2026-11-03', ['2026-10-29','2026-10-30'])
        self.assertEqual([r['run_date'] for r in selected], ['20261028','20261030','20261102'])

    def test_test_links_exclude_conflicting_cin_and_names(self):
        cfg = config(ROOT/'config.json')
        data = {'clo':[dict(rct_mastergroup_id=g,obligor_cin='SHARED') for g in ['MG001356','MG101624']],
                'facilities':[dict(run_date='20261030',cin='SHARED')],
                'pvd':[dict(joi_date='2026-09-30',joi_relationship_id='MG001356'),dict(joi_date='2026-09-30',joi_relationship_id='UNKNOWN',joi_relationship_name='Vodafone')]}
        links = test_links(data,'2026-11-03',cfg)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]['target_source'], 'pvd')
        self.assertEqual(links[0]['valid_from'], '2026-09-30')

    def test_generated_latest_sql_runs_against_synthetic_source_tables(self):
        # Execute window/selection SQL in SQLite; source-specific functions are not used here.
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            evidence=tmp/'ids.csv'
            evidence.write_text('mastergroup_id,proposed_type,identifier_value,origin_source,origin_column\nMG001356,CIN,000001,clo,obligor_cin\n')
            sql_pack(tmp/'pack', [evidence], '2026-11-03')
            db = sqlite3.connect(':memory:')
            self.addCleanup(db.close)
            db.execute('CREATE TABLE clo (run_date TEXT,rct_mastergroup_id TEXT,facility_id TEXT,obligor_cin TEXT)')
            db.executemany('INSERT INTO clo VALUES (?,?,?,?)', [('20261001','MG001356','OLD','000001'),('20261029','MG001356','BASE','000001'),('20261030','MG001356','NEW','000001'),('20261030','MG_OTHER','OUTSIDE','OTHER_CIN')])
            text = (tmp/'pack/clo_extract.sql').read_text().replace('"hive"."clo_prod"."clo_cda_contract_lvl"','clo')
            self.assertEqual([r[2] for r in db.execute(text)], ['NEW','BASE'])
            cp = (tmp/'pack/counterparty_extract.sql').read_text()
            self.assertIn('"delta"."prod_party_gda"."counterparty_core"', cp)
            self.assertIn('mapping_dates', cp)
            self.assertNotIn('lifecycle_status_code =', cp)
            self.assertIn('record_end_dt', (tmp/'pack/facilities_extract.sql').read_text())
            self.assertNotIn("latest_record = 'CURRENT'", (tmp/'pack/facilities_extract.sql').read_text())

    def test_clo_enrichment_uses_combined_prior_mapping_and_does_not_resurrect_inactive(self):
        cfg = config(ROOT/'config.json')
        clo = dict(run_date='20261030',rct_mastergroup_id='NO MSG',obligor_cin='C1',rct_gid='G1',sub_lim_id='F1')
        cp = dict(run_date='20261029',customer_relationship_cin_identifier='C1',customer_relationship_gid_identifier='G1',mastergroup_esr_identifier='MG001356',customer_relationship_lifecycle_status_code='A')
        data = {'clo':[clo],'counterparty':[cp]}
        links = test_links(data,'2026-11-03',cfg)
        self.assertEqual(links[0]['mastergroup_id'],'MG001356')
        self.assertEqual(json.loads(links[0]['scope_json'])['rct_gid'],'G1')
        data['counterparty'].append(dict(cp,run_date='20261030',customer_relationship_lifecycle_status_code='INACTIVE'))
        self.assertEqual(test_links(data,'2026-11-03',cfg),[])
        data['counterparty']=[cp,dict(cp,customer_relationship_cin_identifier='OTHER',mastergroup_esr_identifier='MG101624')]
        self.assertEqual(test_links(data,'2026-11-03',cfg),[])

    def test_complete_refresh_enriches_missing_clo_group_and_preserves_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            incoming=tmp/'exports'
            clo = dict(run_date='20261029',obligor_cin='C1',rct_gid='G1',rct_mastergroup_id='NO MSG',source_system='TEST',mapping_system='TEST',hsbc_booking_legal_entity='TEST',sub_lim_id='F1',rct_facility_ref='',facility_id='F1',local_product_type_lbs='REV',facility_currency='GBP',facility_drawn_amount='10',facility_limit_amount='100')
            write_csv(incoming/'clo.csv', list(clo), [clo,dict(clo,run_date='20261030',facility_drawn_amount='20')])
            cp = dict(run_date='20261029',customer_relationship_cin_identifier='C1',customer_relationship_gid_identifier='G1',mastergroup_esr_identifier='MG001356',customer_relationship_lifecycle_status_code='A')
            write_csv(incoming/'counterparty.csv',list(cp),[cp])
            original=(incoming/'clo.csv').read_bytes()
            out=process(incoming,tmp/'run','2026-11-03',use_test_links=True)
            self.assertEqual((incoming/'clo.csv').read_bytes(),original)
            db=sqlite3.connect(out/'cohort/cohort.sqlite');self.addCleanup(db.close)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM matches WHERE source='clo' AND status='matched'").fetchone()[0],2)
            signal=sqlite3.connect(out/'signals/results/bond_radar.sqlite');self.addCleanup(signal.close)
            self.assertEqual(signal.execute("SELECT COUNT(*) FROM clo_enriched WHERE match_status='matched_unique' AND final_mastergroup='MG001356'").fetchone()[0],2)
            self.assertEqual(signal.execute("SELECT value FROM signal_evidence WHERE signal_id='SIG01'").fetchone()[0],'10')


if __name__ == '__main__':
    unittest.main()
