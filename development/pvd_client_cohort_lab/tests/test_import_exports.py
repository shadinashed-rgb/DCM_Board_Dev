import csv
import json
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cohort import ROOT, analyse, candidate_sql, seed_sql, source_sql, write_csv
from import_exports import import_exports, inspect_export

class ManualExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name);self.incoming=self.folder/'drive_exports';self.incoming.mkdir()
        self.columns=['joi_date','joi_relationship_id','joi_key','joi_relationship_name','omn_mastergroup_name','drr_supergroup_id','drr_supergroup_name']
    def tearDown(self):self.temp.cleanup()
    def pvd(self,name,rows):
        path=self.incoming/name;write_csv(path,self.columns,rows);return path
    def test_header_only_export_is_empty_data(self):
        result=inspect_export(self.pvd('02_discovery.csv',[]))
        self.assertEqual((result['kind'],result['source'],result['rows']),('data','pvd',0))
    def test_query_error_is_not_kyc_data(self):
        path=self.incoming/'04_name_candidates_kyc.csv';path.write_text('fail error\tline 11:47: Cannot cast array(varchar) to varchar\n')
        result=inspect_export(path);self.assertEqual((result['kind'],result['source']),('error','kyc'))
    def test_reordered_duplicate_exports_are_loaded_once(self):
        rows=[['2026-09-30','MG001356','KEY1','VODAFONE','','',''],['2026-09-30','MG101624','KEY2','SOFTBANK','','','']]
        self.pvd('one.csv',rows);self.pvd('two.csv',list(reversed(rows)))
        output=import_exports(self.incoming,self.folder/'prepared')
        self.assertEqual(len(list((output/'pvd').glob('*.csv'))),1)
        manifest=json.loads((output/'import_manifest.json').read_text())
        self.assertEqual(sum(r.get('import_status')=='duplicate_export_skipped' for r in manifest['files']),1)
    def test_error_schema_profile_are_recorded_but_not_ingested(self):
        self.pvd('pvd_data.csv',[['2026-09-30','MG001356','K','VODAFONE','','','']])
        self.pvd('empty.csv',[])
        (self.incoming/'04_kyc.csv').write_text('fail error\tCannot cast array(varchar) to varchar\n')
        write_csv(self.incoming/'schema.csv',['Create Table'],[['CREATE TABLE hive.pvd_prod_wave.pvd_omnia_drr (joi_date varchar)']])
        write_csv(self.incoming/'03_pvd_date_coverage.csv',['joi_date','raw_rows'],[])
        originals={p.name:p.read_bytes() for p in self.incoming.iterdir()}
        output=import_exports(self.incoming,self.folder/'prepared')
        report=analyse(output,self.folder/'analysis','2026-11-02',ROOT/'config.json')
        db=sqlite3.connect(report/'cohort.sqlite');self.addCleanup(db.close)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM coverage WHERE source='kyc' AND status='extraction_failed'").fetchone()[0],3)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM raw_rows').fetchone()[0],1)
        self.assertTrue(all((self.incoming/name).read_bytes()==value for name,value in originals.items()))
    def test_kyc_array_name_sql_is_evaluable_without_scalar_array_cast(self):
        output=self.folder/'sql';source_sql(output,ROOT/'config.json','2026-10-01','2026-10-30')
        query=(output/'kyc/04_name_candidates.sql').read_text()
        self.assertIn('ARRAY_JOIN(t."cdd_topco_legal_name",',query)
        self.assertNotIn('CAST(t."cdd_topco_legal_name" AS VARCHAR)',query)
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.create_function('ARRAY_JOIN',2,lambda value,delimiter:delimiter.join(v for v in json.loads(value) if v is not None) if value else None)
        db.create_function('REGEXP_REPLACE',3,lambda value,pattern,replacement:re.sub(pattern,replacement,value) if value is not None else None)
        db.create_function('STRPOS',2,lambda value,part:value.find(part)+1)
        db.execute('CREATE TABLE kyc(run_date TEXT,legal_name TEXT,cdd_topco_legal_name TEXT,mg_parent_legal_name TEXT)')
        db.execute('INSERT INTO kyc VALUES (?,?,?,?)',('20261028','DEMO SUBSIDIARY',json.dumps(['VODAFONE GROUP PLC',None]),None))
        query=query.replace('"delta"."prod_party_gda"."kyc"','kyc')
        self.assertEqual(len(db.execute(query).fetchall()),1)
    def test_id_first_pvd_query_contains_no_name_filter(self):
        output=self.folder/'sql';seed_sql(output,ROOT/'config.json','2026-07-01','2026-10-30')
        query=(output/'04_pvd_mastergroup_ids.sql').read_text()
        self.assertIn('MG001356',query);self.assertIn('joi_relationship_id',query);self.assertNotIn('STRPOS',query)
        self.assertTrue((output/'00_pvd_partitions.sql').exists())
    def test_existing_import_output_is_not_overwritten(self):
        self.pvd('source.csv',[['2026-09-30','MG001356','K','VODAFONE','','','']])
        output=import_exports(self.incoming,self.folder/'prepared')
        with self.assertRaises(ValueError):import_exports(self.incoming,output)
    def test_observed_cin_lookup_does_not_approve_mappings(self):
        self.pvd('pvd.csv',[['2026-09-30','MG001356','K','VODAFONE','','','']])
        write_csv(self.incoming/'clo.csv',['run_date','obligor_cin','rct_gid','rct_mastergroup_id','sub_lim_id'],[['20261028','000123','G_DEMO','MG001356','F1']])
        prepared=import_exports(self.incoming,self.folder/'prepared')
        run=analyse(prepared,self.folder/'analysis','2026-11-02',ROOT/'config.json')
        before=(prepared/'approved_identifiers.csv').read_bytes()
        output=self.folder/'lookup';candidate_sql(run,output,'2026-10-01','2026-10-30')
        query=(output/'kyc/02_extract.sql').read_text();self.assertIn('000123',query);self.assertIn('CANDIDATE LOOKUP',query)
        self.assertEqual((prepared/'approved_identifiers.csv').read_bytes(),before)
        db=sqlite3.connect(run/'cohort.sqlite');self.addCleanup(db.close)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM approved_links WHERE identifier_type='CIN'").fetchone()[0],0)

if __name__=='__main__':unittest.main()
