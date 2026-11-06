"""Portfolio mode end to end on the synthetic full-portfolio extract (portfolio_demo.py)."""
import csv
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import portfolio  # noqa: E402
import portfolio_demo  # noqa: E402

CONFIG = ROOT / 'profiles/portfolio_dev2.json'


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


class PortfolioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.input = portfolio_demo.build(cls.root / 'in')
        cls.summary = portfolio.run(cls.input, cls.root / 'run', portfolio_demo.AS_OF, CONFIG, extra_links=cls.input / 'reviewed_links.csv')
        cls.ev = rows(cls.root / 'run' / 'BOND_RADAR_SIGNAL_EVIDENCE.csv')
        cls.matrix = {r['mastergroup_id']: r for r in rows(cls.root / 'run' / 'GROUP_SIGNAL_MATRIX.csv')}
        cls.cand = rows(cls.root / 'run' / 'CANDIDATES.csv')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_groups_are_discovered_without_a_target_list(self):
        self.assertEqual(set(self.matrix), {'MGA0001', 'MGB0002', 'MGC0003', 'MGD0004'})
        self.assertEqual(self.matrix['MGC0003']['business_line'], 'CMB')
        self.assertEqual(self.matrix['MGA0001']['group_name'], 'Alpha Telecom')

    def test_sig01_material_cat_a_drawing_is_a_candidate(self):
        a = [r for r in self.ev if r['mastergroup_id'] == 'MGA0001' and r['signal_id'] == 'SIG01' and r['component'] == 'drawing_change'][0]
        self.assertEqual((a['metric_value'], a['limit_category'], a['materiality_status'], a['review_type']),
                         ('70000000', 'CAT-A', 'hsbc_share_meets_threshold', 'material_drawing_for_testing'))
        self.assertIn('counterparty_core_latest', a['mapping_status'])

    def test_sig01_without_fx_is_not_assessed(self):
        b = [r for r in self.ev if r['mastergroup_id'] == 'MGB0002' and r['signal_id'] == 'SIG01' and r['component'] == 'drawing_change'][0]
        self.assertEqual(b['materiality_status'], 'fx_rate_not_configured')
        self.assertEqual(self.matrix['MGB0002']['signals_with_candidates'], '0')

    def test_fx_from_clo_makes_usd_material_but_cat_b_is_not_a_candidate(self):
        portfolio.run(self.input, self.root / 'run_fx', portfolio_demo.AS_OF, CONFIG, fx_from_clo=True)
        ev = rows(self.root / 'run_fx' / 'BOND_RADAR_SIGNAL_EVIDENCE.csv')
        b = [r for r in ev if r['mastergroup_id'] == 'MGB0002' and r['signal_id'] == 'SIG01' and r['component'] == 'drawing_change'][0]
        self.assertEqual((b['material_drawing_for_testing'], b['cat_a_eligible'], b['review_type']), ('True', 'False', 'material_drawing_not_cat_a'))
        self.assertTrue((self.root / 'run_fx' / 'FX_USED.csv').exists())
        self.assertFalse([c for c in rows(self.root / 'run_fx' / 'CANDIDATES.csv') if c['mastergroup_id'] == 'MGB0002'])

    def test_sig02_credit_approval_date_from_application_ratings(self):
        c = [r for r in self.ev if r['mastergroup_id'] == 'MGC0003' and r['signal_id'] == 'SIG02'][0]
        self.assertEqual((c['credit_approval_date'], c['event_age_days'], c['recent_creation_for_testing']), ('2026-10-17', '20', 'True'))

    def test_sig06_pressure_and_relationship_route(self):
        d = [r for r in self.ev if r['signal_id'] == 'SIG06'][0]
        self.assertEqual((d['mastergroup_id'], d['covenant_pressure_for_testing'], d['covenant_breach_for_testing']), ('MGD0004', 'True', 'False'))
        self.assertIn('facilities_relationship_to_cin', d['mapping_status'])

    def test_ambiguous_cin_and_invalid_group_stay_unlinked(self):
        x = [r for r in self.ev if 'SUBX9' in r['clo_sub_limit_ids']]
        self.assertTrue(x and all(r['mastergroup_id'] == '' for r in x))
        self.assertFalse([r for r in self.ev if r['mastergroup_id'] == 'NO MSG'])

    def test_reviewed_extra_link_maps_pvd(self):
        pvd = [r for r in self.ev if r['source'] == 'pvd']
        self.assertTrue(pvd and all(r['mastergroup_id'] == 'MGD0004' for r in pvd))
        self.assertIn('reviewed_demo_link', pvd[0]['mapping_status'])

    def test_kyc_maturity_crr_and_candidates(self):
        self.assertEqual(self.matrix['MGA0001']['sig04_cases'], '1')
        self.assertEqual(self.matrix['MGA0001']['maturity_lt_12m'], '2')
        self.assertEqual(self.matrix['MGD0004']['crr_values'], '4.1')
        self.assertEqual({c['signal_id'] for c in self.cand}, {'SIG01', 'SIG02', 'SIG06'})
        self.assertEqual(self.summary['groups_with_candidates'], 3)

    def test_older_counterparty_snapshot_and_closed_mapping_are_not_used(self):
        links = rows(self.root / 'run' / 'identity_links_portfolio.csv')
        self.assertFalse([l for l in links if l['mastergroup_id'] in ('MGOLD', 'MGE0005')])

    def test_input_check_catches_missing_part_and_header_drift(self):
        broken = self.root / 'broken'
        shutil.copytree(self.input, broken)
        (broken / 'clo' / 'part_02_of_03.csv').unlink()
        _, problems = portfolio.check_inputs(broken)
        self.assertTrue(any('missing parts [2] of 3' in p for p in problems))
        p = broken / 'facilities' / 'part_02_of_02.csv'
        p.write_text(p.read_text().replace('limit_cat', 'limit_category', 1))
        _, problems = portfolio.check_inputs(broken)
        self.assertTrue(any('header of part_02_of_02.csv differs' in p for p in problems))
        with self.assertRaises(ValueError):
            portfolio.run(broken, self.root / 'run_broken', portfolio_demo.AS_OF, CONFIG)

    def test_outputs_and_no_triggers(self):
        out = self.root / 'run'
        for name in ('GROUP_SIGNAL_MATRIX.csv', 'CANDIDATES.csv', 'MATURITY_WINDOWS.csv', 'SOURCE_COVERAGE.csv', 'GROUPS.csv', 'PORTFOLIO_SIGNALS.xlsx', 'REVIEW.md', 'INPUT_CHECK.json'):
            self.assertTrue((out / name).exists(), name)
        self.assertFalse([r for r in self.ev if r['business_trigger'] not in ('', 'None')])
        self.assertEqual(json.loads((out / 'RUN_SUMMARY.json').read_text())['records'], len(self.ev))


if __name__ == '__main__':
    unittest.main()
