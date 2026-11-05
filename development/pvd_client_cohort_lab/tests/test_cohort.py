import csv
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cohort import ROOT, REVIEW_COLUMNS, analyse, config, read_approvals, run_signals, seed_sql, source_sql, write_csv
from demo import make_inputs, read_review

class CohortTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name);self.input=self.folder/'inputs';make_inputs(self.input);self.cfg=ROOT/'config.json'
    def tearDown(self):self.temp.cleanup()
    def run_analysis(self,name='run',approval=None):
        out=analyse(self.input,self.folder/name,'2026-10-30',self.cfg,approval);db=sqlite3.connect(out/'cohort.sqlite');db.row_factory=sqlite3.Row;self.addCleanup(db.close);return db,out
    def approve(self,path,filter_fn):
        rows=read_review(path)
        for row in rows:
            if filter_fn(row):row.update(decision='approve',evidence='Verified synthetic test fixture')
        out=self.folder/('approval-'+str(len(list(self.folder.glob('approval-*'))))+'.csv');write_csv(out,REVIEW_COLUMNS,([r[c] for c in REVIEW_COLUMNS] for r in rows));return out
    def test_pvd_ids_names_are_candidates_without_namespace_inference(self):
        db,out=self.run_analysis()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM matches WHERE source='pvd' AND status='matched'").fetchone()[0],0)
        self.assertGreater(db.execute("SELECT COUNT(*) FROM matches WHERE source='pvd' AND status='candidate'").fetchone()[0],0)
        proposals=read_review(out/'identifier_review.csv')
        self.assertTrue(any(r['identifier_value']=='00000999' and r['proposed_type']=='PVD_KEY' for r in proposals))
        self.assertFalse(any(r['origin_source']=='pvd' and r['proposed_type'] in ('CIN','GID') for r in proposals))

    def test_counterparty_non_target_mapping_survives_signal_handoff(self):
        cp=dict(run_date='20261028',customer_relationship_cin_identifier='00000001',customer_relationship_gid_identifier='G_DEMO_1',mastergroup_esr_identifier='MG_OUTSIDE',customer_relationship_lifecycle_status_code='A')
        write_csv(self.input/'counterparty.csv',list(cp),[list(cp.values())])
        _,out=self.run_analysis()
        signals=run_signals(out,self.folder/'cp_reference_signals')
        db=sqlite3.connect(signals/'results/bond_radar.sqlite');self.addCleanup(db.close)
        self.assertEqual(db.execute('SELECT mastergroup_esr_identifier FROM raw_counterparty').fetchone()[0],'MG_OUTSIDE')
        self.assertGreater(db.execute("SELECT COUNT(*) FROM clo_enriched WHERE match_status='source_conflict'").fetchone()[0],0)
    def test_all_groups_sources_appear_and_missing_differs_from_zero(self):
        pvd=self.folder/'pvd_only';pvd.mkdir();(pvd/'pvd.csv').write_bytes((self.input/'pvd.csv').read_bytes())
        out=analyse(pvd,self.folder/'pvd_report','2026-10-30',self.cfg)
        db=sqlite3.connect(out/'cohort.sqlite');self.addCleanup(db.close)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM coverage').fetchone()[0],21)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM coverage WHERE source!='pvd' AND status='missing_file'").fetchone()[0],18)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM signal_readiness').fetchone()[0],27)
    def test_review_unlocks_routes_but_never_expands_shared_supergroup(self):
        _,out=self.run_analysis();approval=self.approve(out/'identifier_review.csv',lambda r:r['proposed_type']=='PVD_RELATIONSHIP_ID' and r['identifier_value']==r['mastergroup_id'])
        db,_=self.run_analysis('reviewed',approval)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM matches WHERE source='pvd' AND status='matched'").fetchone()[0],4)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM approved_links WHERE identifier_type='PVD_SUPERGROUP_ID'").fetchone()[0],0)
        self.assertGreater(db.execute("SELECT COUNT(*) FROM matches m JOIN raw_rows r USING(source,raw_id) WHERE source='pvd' AND r.payload LIKE '%PVD_SUB_DEMO%' AND status='candidate'").fetchone()[0],0)
    def test_same_identifier_approved_to_two_groups_is_quarantined(self):
        _,out=self.run_analysis();approval=self.approve(out/'identifier_review.csv',lambda r:r['proposed_type']=='PVD_RELATIONSHIP_ID' and r['identifier_value']=='PVD_AMBIGUOUS')
        db,_=self.run_analysis('ambiguous',approval)
        rows=db.execute("SELECT status FROM matches m JOIN raw_rows r USING(source,raw_id) WHERE source='pvd' AND r.payload LIKE '%PVD_AMBIGUOUS%'").fetchall()
        self.assertEqual([r[0] for r in rows],['conflict','conflict'])
    def test_leading_zeros_preserved_and_facility_scope_required(self):
        _,out=self.run_analysis();approval=self.approve(out/'identifier_review.csv',lambda r:r['proposed_type']=='CIN')
        rows=read_approvals(approval,config(self.cfg));self.assertTrue(any(r['identifier_value']=='00000001' for r in rows))
        review=read_review(out/'identifier_review.csv');facility=next(r for r in review if r['proposed_type']=='FACILITY_ID');facility.update(decision='approve',evidence='test',scope_json='{}')
        bad=self.folder/'bad.csv';write_csv(bad,REVIEW_COLUMNS,[[facility[c] for c in REVIEW_COLUMNS]])
        with self.assertRaises(ValueError):read_approvals(bad,config(self.cfg))
    def test_sql_contains_only_reviewed_identifiers_and_uses_exists(self):
        _,out=self.run_analysis();approval=self.approve(out/'identifier_review.csv',lambda r:r['proposed_type']=='CIN')
        planned=self.folder/'sql';source_sql(planned,self.cfg,'2026-10-01','2026-10-30',approval)
        text=(planned/'kyc/02_extract.sql').read_text();self.assertIn('EXISTS',text);self.assertIn('00000001',text)
        self.assertNotIn('PVD_AMBIGUOUS',text);self.assertFalse((planned/'counterparty/02_extract.sql').exists())
        self.assertFalse((planned/'covenants/02_extract.sql').exists())
        source_sql(self.folder/'unreviewed',self.cfg,'2026-10-01','2026-10-30')
        self.assertFalse((self.folder/'unreviewed/kyc/02_extract.sql').exists())
    def test_seed_sql_has_bounded_discovery_and_known_name_columns(self):
        out=self.folder/'seed';seed_sql(out,self.cfg,'2026-10-01','2026-10-30')
        text=(out/'02_pvd_discovery.sql').read_text()
        for value in ('MG001356','MG102229','MG101624','joi_relationship_id','drr_supergroup_id','omn_mastergroup_name',"'2026-10-01'",'SOFT BANK'):self.assertIn(value,text)
        self.assertNotIn('LIMIT',text)
    def test_counterparty_window_precedes_clo_for_historical_mapping(self):
        from cohort import bounds
        cfg=config(self.cfg)
        self.assertEqual(bounds('counterparty',cfg,'2026-10-01','2026-10-30'),('20260603','20261030'))
        cfg['source_windows']={'counterparty':{'start':'2026-09-01','end':'2026-10-29'}}
        self.assertEqual(bounds('counterparty',cfg,'2026-10-01','2026-10-30'),('20260901','20261029'))
    def test_original_group_conflict_is_not_overwritten(self):
        _,out=self.run_analysis();approval=self.approve(out/'identifier_review.csv',lambda r:r['proposed_type']=='CIN')
        path=self.input/'clo.csv'
        with path.open(newline='') as h:reader=csv.DictReader(h);cols=reader.fieldnames;rows=list(reader)
        for row in rows:
            if row['obligor_cin']=='00000001':row['rct_mastergroup_id']='MG_OTHER'
        write_csv(path,cols,([r[c] for c in cols] for r in rows))
        db,_=self.run_analysis('conflict',approval)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM matches WHERE source='clo' AND mastergroup_id='MG001356' AND status='matched'").fetchone()[0],0)
        self.assertGreater(db.execute("SELECT COUNT(*) FROM matches WHERE source='clo' AND status='conflict'").fetchone()[0],0)
    def test_future_processing_date_excluded_and_raw_preserved(self):
        path=self.input/'pvd.csv'
        with path.open(newline='') as h:reader=csv.DictReader(h);cols=reader.fieldnames;rows=list(reader)
        for row in rows:row['etlmonth']='2026-11-01'
        write_csv(path,cols,([r[c] for c in cols] for r in rows))
        db,_=self.run_analysis()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM matches WHERE source='pvd'").fetchone()[0],0)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM raw_rows WHERE source='pvd'").fetchone()[0],6)
    def test_signal_handoff_keeps_group_links_and_resolvable_lineage(self):
        _,out=self.run_analysis();approval=self.approve(out/'identifier_review.csv',lambda r:r['proposed_type']=='CIN' or r['proposed_type']=='PVD_RELATIONSHIP_ID' and r['identifier_value']==r['mastergroup_id'])
        _,final=self.run_analysis('final',approval);signals=run_signals(final,self.folder/'signals')
        db=sqlite3.connect(signals/'results/bond_radar.sqlite');self.addCleanup(db.close)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM signal_evidence WHERE triggered IS NOT NULL').fetchone()[0],0)
        self.assertGreater(db.execute('SELECT COUNT(*) FROM cohort_signal_evidence WHERE cohort_mastergroup_id IS NOT NULL').fetchone()[0],0)
        for (filename,) in db.execute('SELECT DISTINCT input_file FROM evidence_lineage'):self.assertTrue(Path(filename).exists(),filename)
        with (signals/'results/exports/cohort_signal_summary.csv').open() as handle:
            self.assertEqual(len(list(csv.DictReader(handle))),27)
    def test_existing_outputs_and_inputs_are_preserved(self):
        original=(self.input/'pvd.csv').read_bytes();_,out=self.run_analysis()
        with self.assertRaises(ValueError):analyse(self.input,out,'2026-10-30',self.cfg)
        self.assertEqual((self.input/'pvd.csv').read_bytes(),original)
    def test_approval_validity_dates_are_applied(self):
        _,out=self.run_analysis();approval=self.approve(out/'identifier_review.csv',lambda r:r['proposed_type']=='PVD_RELATIONSHIP_ID' and r['identifier_value']==r['mastergroup_id'])
        rows=read_review(approval)
        for r in rows:
            if r['decision']=='approve':r['valid_from']='2026-11-01'
        write_csv(approval,REVIEW_COLUMNS,([r[c] for c in REVIEW_COLUMNS] for r in rows))
        db,_=self.run_analysis('dated',approval)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM matches WHERE source='pvd' AND status='matched'").fetchone()[0],0)
    def test_manual_bridge_approval_survives_next_review_export(self):
        _,out=self.run_analysis();rows=read_review(out/'identifier_review.csv')
        row=dict(next(r for r in rows if r['proposed_type']=='CIN'))
        row.update(review_id='manual-example-cin',decision='approve',evidence='Synthetic manually verified mapping')
        approval=self.folder/'manual.csv';write_csv(approval,REVIEW_COLUMNS,[[row[c] for c in REVIEW_COLUMNS]])
        _,next_run=self.run_analysis('next',approval)
        retained={r['review_id']:r for r in read_review(next_run/'identifier_review.csv')}
        self.assertEqual(retained['manual-example-cin']['decision'],'approve')
        self.assertEqual(retained['manual-example-cin']['observed_rows'],'0')
    def test_shared_facility_is_not_allocated_to_two_groups_in_signal_output(self):
        path=self.input/'clo.csv'
        with path.open(newline='') as h:reader=csv.DictReader(h);columns=reader.fieldnames;rows=list(reader)
        for r in rows:
            if r['rct_mastergroup_id'] in ('MG001356','MG102229'):r['sub_lim_id']='SHARED_FACILITY_DEMO'
        write_csv(path,columns,([r[c] for c in columns] for r in rows))
        _,out=self.run_analysis();approval=self.approve(out/'identifier_review.csv',lambda r:r['proposed_type']=='CIN')
        _,reviewed=self.run_analysis('reviewed_shared',approval);signals=run_signals(reviewed,self.folder/'shared_signals')
        db=sqlite3.connect(signals/'results/bond_radar.sqlite');self.addCleanup(db.close)
        record=db.execute("SELECT cohort_mastergroup_id,cohort_group_status FROM cohort_signal_evidence WHERE source='clo' AND component='utilisation' AND record_key LIKE '%SHARED_FACILITY_DEMO%'").fetchone()
        self.assertEqual(record,(None,'shared_or_unresolved_group'))
    def test_complete_synthetic_iteration_reaches_all_sources(self):
        from demo import demo
        out=demo(self.folder/'complete_demo');db=sqlite3.connect(out/'04_reviewed_coverage/cohort.sqlite');self.addCleanup(db.close)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM coverage WHERE matched_rows>0').fetchone()[0],21)
        signal=sqlite3.connect(out/'05_signal_tests/results/bond_radar.sqlite');self.addCleanup(signal.close)
        self.assertEqual(signal.execute('SELECT COUNT(*) FROM signal_evidence WHERE triggered IS NOT NULL').fetchone()[0],0)
    def test_generated_identifier_queries_select_expected_synthetic_rows(self):
        import re
        import bond_radar as engine
        from demo import demo
        out=demo(self.folder/'sql_demo')
        cfg=config(self.cfg);cfg['counterparty_catalog_confirmed']=True
        cfg_path=self.folder/'sql_config.json';cfg_path.write_text(json.dumps(cfg))
        pack=self.folder/'executable_sql';source_sql(pack,cfg_path,'2026-10-01','2026-10-30',out/'approved_final.csv')
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.create_function('REGEXP_REPLACE',3,lambda value,pattern,replacement:re.sub(pattern,replacement,value) if value is not None else None)
        db.create_function('STRPOS',2,lambda value,part:value.find(part)+1)
        expected={'pvd':5,'clo':5,'counterparty':3,'drr':3,'facilities':3,'kyc':3,'covenants':3}
        for source,count in expected.items():
            with (out/'inputs_all'/(source+'.csv')).open(newline='') as handle:
                reader=csv.reader(handle);header=next(reader);rows=list(reader)
            db.execute('CREATE TABLE '+engine.ident(source)+' ('+','.join(engine.ident(c)+' TEXT' for c in header)+')')
            db.executemany('INSERT INTO '+engine.ident(source)+' VALUES ('+','.join('?' for _ in header)+')',rows)
            query=(pack/source/'02_extract.sql').read_text()
            table='.'.join(engine.ident(p) for p in engine.SOURCES[source]['table'].split('.'))
            query=query.replace(table,engine.ident(source))
            self.assertEqual(len(db.execute(query).fetchall()),count,source)
    def test_verified_pvd_gid_bridge_discovers_cin_without_drr_group_id(self):
        for source in ('pvd','drr'):
            path=self.input/(source+'.csv')
            with path.open(newline='') as h:reader=csv.DictReader(h);columns=reader.fieldnames;rows=list(reader)
            if source=='pvd':rows[0]['joi_relationship_id']='G_DEMO_1'
            else:rows[0]['drr_mastergroup_id']=''
            write_csv(path,columns,([r[c] for c in columns] for r in rows))
        _,discovery=self.run_analysis()
        native=next(r for r in read_review(discovery/'identifier_review.csv') if r['origin_source']=='pvd' and r['proposed_type']=='PVD_RELATIONSHIP_ID' and r['identifier_value']=='G_DEMO_1')
        native.update(decision='approve',evidence='Synthetic verified PVD relationship/group link')
        converted=dict(native);converted.update(review_id=native['review_id']+'-gid',approved_type='GID',target_source='*',evidence='Synthetic dictionary verifies this PVD value is a shared GID')
        approval=self.folder/'pvd_gid.csv';write_csv(approval,REVIEW_COLUMNS,[[r[c] for c in REVIEW_COLUMNS] for r in (native,converted)])
        db,out=self.run_analysis('gid_bridge',approval)
        self.assertEqual(db.execute("SELECT matched_rows FROM coverage WHERE mastergroup_id='MG001356' AND source='drr'").fetchone()[0],1)
        proposed=read_review(out/'identifier_review.csv')
        self.assertTrue(any(r['origin_source']=='drr' and r['mastergroup_id']=='MG001356' and r['proposed_type']=='CIN' and r['identifier_value']=='00000001' for r in proposed))

if __name__=='__main__':unittest.main()
