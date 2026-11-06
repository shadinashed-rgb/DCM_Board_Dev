"""The portfolio SQL pack: no client filters, only real columns, valid Trino syntax, complete buckets."""
import csv
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import portfolio_sql as P  # noqa: E402

OBSERVED = json.loads((ROOT / 'profiles/source_columns_observed.json').read_text())['columns']
# Names the SQL creates itself (aliases / helper columns), not source columns.
DERIVED = {'group_key', 'latest_date', 'prior_date', 'part', 'part_sys', 'part_cty', 'part_carm', 'snapshot_rank', 'currency',
           'rows_with_rate', 'fx_to_usd_median', 'fx_to_usd_min', 'fx_to_usd_max', 'partition_value', 'rows_selected', 'distinct_bucket_keys'}


class PortfolioSqlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'pack'
        subprocess.run([sys.executable, '-B', str(ROOT / 'portfolio_sql.py'), '--as-of', '2026-11-06', '--out', str(cls.out),
                        '--buckets', 'clo=3,facilities=2'], check=True, capture_output=True)
        with (cls.out / 'EXTRACTION_CHECKLIST.csv').open() as f:
            cls.checklist = list(csv.DictReader(f))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def sql_files(self):
        return sorted(self.out.rglob('*.sql'))

    def test_every_source_has_profile_and_extract_and_checklist_entries(self):
        for s in P.SOURCES:
            self.assertTrue(any(r['source'] == s and r['stage'] == 'profile' for r in self.checklist), s)
            self.assertTrue(any(r['source'] == s and r['stage'] == 'extract' for r in self.checklist), s)
        self.assertEqual(sum(r['source'] == 'clo' and r['stage'] == 'extract' for r in self.checklist), 3)

    def test_no_client_specific_filters(self):
        for f in self.sql_files():
            text = f.read_text()
            for marker in ('MG001356', 'MG102229', 'MG101624', 'VODAFONE', 'SOFTBANK', 'SIEMENS', '1018544917'):
                self.assertNotIn(marker, text.upper(), f'{f.name} contains a client-specific filter: {marker}')

    def test_only_observed_source_columns_are_referenced(self):
        for s in P.SOURCES:
            known = set(OBSERVED[s])
            for c in P.output_columns(s):
                self.assertIn(c, known, f'{s}: column {c} not observed in the real schema')
        for f in self.sql_files():
            source = next((s for s in P.SOURCES if f.name.startswith(s) or f'_{s}_' in f.name), None)
            if source is None:
                continue
            refs = set(re.findall(r'\b[tbx]\."([a-z0-9_]+)"', f.read_text()))
            unknown = refs - set(OBSERVED[source]) - DERIVED
            self.assertFalse(unknown, f'{f.name}: unknown columns {sorted(unknown)}')

    def test_sql_parses_as_trino(self):
        try:
            import sqlglot
        except ImportError:
            self.skipTest('sqlglot not installed (pip install sqlglot)')
        for f in self.sql_files():
            text = f.read_text()
            comments = [l for l in text.splitlines() if l.strip().startswith('--')]
            self.assertFalse([l for l in comments if ';' in l], f'{f.name}: semicolon inside a comment breaks some SQL clients')
            code = '\n'.join(l for l in text.splitlines() if not l.strip().startswith('--'))
            for statement in [s for s in code.split(';') if s.strip()]:
                sqlglot.parse_one(statement, read='trino')

    def test_buckets_partition_the_selection(self):
        # Parts of one source differ only in the bucket number and together cover 0..n-1.
        parts = sorted((self.out / '02_extracts' / 'clo').glob('*.sql'))
        found = sorted(int(re.search(r'\), 3\) = (\d)', p.read_text()).group(1)) for p in parts)
        self.assertEqual(found, [0, 1, 2])
        bodies = {re.sub(r'part \d of 3|part_\d\d_of_03|\) = \d;', '', p.read_text()) for p in parts}
        self.assertEqual(len(bodies), 1)
        single = (self.out / '02_extracts' / 'kyc' / 'kyc_part_01_of_01.sql').read_text()
        self.assertIn('WHERE TRUE;', single)

    def test_snapshot_rules_are_partitioned_not_global(self):
        fac = (self.out / '02_extracts' / 'facilities' / 'facilities_part_01_of_02.sql').read_text()
        self.assertIn('part_sys, part_cty', fac)
        clo = (self.out / '02_extracts' / 'clo' / 'clo_part_01_of_03.sql').read_text()
        self.assertIn('PARTITION' not in clo and 'GROUP BY group_key', clo)
        self.assertNotIn('SELECT t.*', clo)

    def test_application_ratings_keeps_effective_and_recent_approvals(self):
        ar = (self.out / '02_extracts' / 'application_ratings' / 'application_ratings_part_01_of_01.sql').read_text()
        self.assertIn("OR TRY(date_parse(NULLIF(TRIM(b.\"approval_dt\"), ''), '%Y%m%d')) >= DATE", ar)
        self.assertTrue(ar.rstrip().endswith('WHERE TRUE;'))


if __name__ == '__main__':
    unittest.main()
