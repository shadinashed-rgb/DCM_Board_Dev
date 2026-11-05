"""Execute metadata and returned sample SQL locally with Trino function adapters."""
import json
from pathlib import Path
import re
import sqlite3
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from application_ratings_samples import GROUPS, TABLE, metadata_query


class ArrayAgg:
    def __init__(self):self.values=[]
    def step(self,value):self.values.append(value)
    def finalize(self):return json.dumps(self.values)


class ApplicationRatingsTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.create_function('CHR',1,chr)
        self.db.create_function('CONCAT',-1,lambda *args:None if any(v is None for v in args) else ''.join(str(v) for v in args))
        self.db.create_function('REGEXP_LIKE',2,lambda v,p:bool(re.search(p,v or '')))
        self.db.create_function('ARRAY_JOIN',2,lambda v,d:None if v is None else d.join(str(x) for x in json.loads(v) if x is not None))
        self.db.create_aggregate('ARRAY_AGG',1,ArrayAgg)
        self.db.execute('CREATE TABLE columns_meta(column_name TEXT,data_type TEXT,ordinal_position INT,table_schema TEXT,table_name TEXT)')
        self.seeds=[dict(mastergroup_id=g,identifier_kind='MASTERGROUP_ID',identifier_value=g) for g in GROUPS]
        self.seeds += [dict(mastergroup_id='MG001356',identifier_kind='CIN',identifier_value='000001')]

    def schema(self,columns):
        self.db.executemany('INSERT INTO columns_meta VALUES (?,?,?,?,?)',[(c,t,i,'prod_credit_and_lending_gda','application_ratings') for i,(c,t) in enumerate(columns,1)])

    def plan(self,per_type=25):
        sql=metadata_query(self.seeds,per_type=per_type).replace('"delta".information_schema.columns','columns_meta')
        return [dict(r) for r in self.db.execute(sql)]

    def test_all_clients_and_types_are_sampled_with_date_boundaries(self):
        self.schema([('mastergroup_id','varchar'),('cin','varchar'),('run_date','varchar'),('rating_type','varchar'),('rating_agency','varchar'),('rating_value','varchar')])
        self.db.execute('CREATE TABLE ratings(mastergroup_id TEXT,cin TEXT,run_date TEXT,rating_type TEXT,rating_agency TEXT,rating_value TEXT)')
        rows=[]
        for group in GROUPS:
            for kind,agency in [('External','S&P'),('Internal','CRR')]:
                rows += [(group,'000001' if group=='MG001356' else 'OTHER',d,kind,agency,'TEST') for d in ['2026-11-04','20261103','20261030','20261105','20260101']]
        self.db.executemany('INSERT INTO ratings VALUES (?,?,?,?,?,?)',rows)
        plans=self.plan(per_type=2)
        self.assertEqual(len(plans),3)
        for plan in plans:
            self.assertEqual(plan['plan_status'],'candidate_sample_sql_ready')
            selected=list(self.db.execute(plan['sample_sql'].replace(TABLE,'ratings')))
            self.assertEqual(len(selected),4)
            self.assertEqual({r['rating_agency'] for r in selected},{'S&P','CRR'})
            self.assertEqual({r['mastergroup_id'] for r in selected},{plan['mastergroup_id']})
            self.assertTrue(all('20260707'<=r['_sig07_observation_date']<='20261104' for r in selected))
            prof=list(self.db.execute(plan['profile_sql'].replace(TABLE,'ratings')))
            self.assertEqual(sum(r['raw_rows'] for r in prof),6)

    def test_missing_schema_or_identifier_or_snapshot_emits_no_data_query(self):
        self.assertTrue(all(p['plan_status']=='schema_not_visible' and p['sample_sql'] is None for p in self.plan()))
        self.schema([('customer_id','varchar'),('run_date','varchar')])
        self.assertTrue(all(p['plan_status']=='identifier_bridge_required' and p['sample_sql'] is None for p in self.plan()))
        self.db.execute('DELETE FROM columns_meta')
        self.schema([('mastergroup_id','varchar'),('rating_date','varchar')])
        self.assertTrue(all(p['plan_status']=='snapshot_date_column_required' and p['sample_sql'] is None for p in self.plan()))

    def test_wide_rating_schema_keeps_all_columns_without_type_filter(self):
        self.schema([('mastergroup_id','varchar'),('run_date','date'),('sp_rating','varchar'),('crr','varchar')])
        plan=self.plan()[0]
        self.assertEqual(plan['sample_dimensions'],'')
        self.assertIn('t.*',plan['sample_sql'])
        self.assertIn('_sig07_sample_rank <= 100',plan['sample_sql'])
        self.assertNotIn('PARTITION BY',plan['sample_sql'])
        self.assertIn('sp_rating',plan['rating_related_columns'])
        self.assertIn('crr',plan['rating_related_columns'])

    def test_array_identifier_is_not_cast_to_scalar_or_guessed(self):
        self.schema([('mastergroup_id','array(varchar)'),('run_date','varchar')])
        self.assertTrue(all(p['sample_sql'] is None for p in self.plan()))

    def test_application_serial_routes_only_used_without_primary_ids(self):
        self.seeds.append(dict(mastergroup_id='MG001356',identifier_kind='CREDIT_PROPOSAL_SERIAL_NO',identifier_value='123'))
        self.schema([('mastergroup_id','varchar'),('credit_proposal_serial_no','varchar'),('run_date','varchar')])
        plan=next(p for p in self.plan() if p['mastergroup_id']=='MG001356')
        self.assertNotIn('credit_proposal_serial_no',plan['sample_sql'])
        self.db.execute("DELETE FROM columns_meta WHERE column_name='mastergroup_id'")
        plans=self.plan();plan=next(p for p in plans if p['mastergroup_id']=='MG001356')
        self.assertIn('credit_proposal_serial_no',plan['sample_sql'])
        self.assertTrue(all(p['sample_sql'] is None for p in plans if p['mastergroup_id']!='MG001356'))

    def test_identifier_literals_are_escaped_and_other_groups_remain_visible(self):
        self.schema([('cin','varchar'),('run_date','varchar'),('mastergroup_id','varchar')])
        self.seeds.append(dict(mastergroup_id='MG001356',identifier_kind='CIN',identifier_value="X' OR 1=1 --"))
        plan=next(p for p in self.plan() if p['mastergroup_id']=='MG001356')
        self.db.execute('CREATE TABLE ratings(cin TEXT,run_date TEXT,mastergroup_id TEXT)')
        self.db.executemany('INSERT INTO ratings VALUES (?,?,?)',[('000001','20261103','MG_OTHER'),('UNRELATED','20261103','MG_OTHER')])
        rows=list(self.db.execute(plan['sample_sql'].replace(TABLE,'ratings')))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['mastergroup_id'],'MG_OTHER')  # preserve contradiction, never overwrite


if __name__=='__main__':unittest.main()
