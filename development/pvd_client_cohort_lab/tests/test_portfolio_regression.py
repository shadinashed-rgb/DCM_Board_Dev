"""Portfolio mode reproduces the targeted three-client results without being told the clients.

Runs only when the real development inputs are restored (python3 -B tools/extract_inputs.py);
raw client data is not in git, so the test skips otherwise.
"""
import csv
from collections import Counter
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

DEV = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DEV / 'pvd_client_cohort_lab'))
import portfolio  # noqa: E402

DATA = DEV / 'data' / 'current_exports'
TARGETS = {'MG001356', 'MG102229', 'MG101624'}


@unittest.skipUnless((DATA / 'clo_current_and_previous.csv').exists(), 'real inputs not restored (tools/extract_inputs.py)')
class PortfolioRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        args = [sys.executable, '-B', str(DEV / 'tools/project_to_portfolio_layout.py'), '--out', str(root / 'in')]
        for s, f in [('counterparty', 'counterparty_current.csv'), ('clo', 'clo_current_and_previous.csv'), ('facilities', 'facilities_current.csv'),
                     ('drr', 'drr_current.csv'), ('pvd', 'pvd_current.csv'), ('kyc', 'kyc_current.csv')]:
            args += ['--source', f'{s}={DATA / f}']
        args += ['--source', f'application_ratings={DEV / "data/application_ratings_full"}/*.csv']
        subprocess.run(args, check=True, capture_output=True)
        portfolio.run(root / 'in', root / 'run', '2026-11-03', DEV / 'pvd_client_cohort_lab/profiles/portfolio_dev2.json')
        with (root / 'run' / 'BOND_RADAR_SIGNAL_EVIDENCE.csv').open(encoding='utf-8-sig') as f:
            cls.ev = list(csv.DictReader(f))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_same_sig02_candidates_as_targeted_run(self):
        got = sorted((r['mastergroup_id'], r['facility_ids']) for r in self.ev if r['signal_id'] == 'SIG02' and r['recent_creation_for_testing'] == 'True')
        self.assertEqual(len(got), 9)
        self.assertEqual(Counter(g for g, _ in got), Counter({'MG001356': 7, 'MG102229': 1, 'MG101624': 1}))

    def test_same_signal_counts_for_the_three_groups(self):
        c = Counter((r['signal_id'], r['mastergroup_id']) for r in self.ev if r['mastergroup_id'] in TARGETS)
        self.assertEqual((c[('SIG02', 'MG001356')], c[('SIG02', 'MG102229')], c[('SIG02', 'MG101624')]), (46, 15, 2))
        self.assertEqual((c[('SIG01', 'MG001356')], c[('SIG01', 'MG102229')]), (4, 2))
        self.assertEqual(sum(r['above_70_for_testing'] == 'True' for r in self.ev), 5)

    def test_softbank_large_drawing_without_prior_is_surfaced(self):
        s = [r for r in self.ev if r['clo_sub_limit_ids'] == '00010341075552511210201' and r['component'] == 'drawing_change_alt_usd']
        self.assertTrue(s and s[0]['mastergroup_id'] == 'MG101624' and s[0]['current_drawn'].startswith('179746223'))


if __name__ == '__main__':
    unittest.main()
