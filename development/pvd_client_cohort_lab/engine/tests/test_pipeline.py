"""Meaningful regression tests for identity, history, deduplication and unavailable data."""
import csv
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bond_radar import ROOT, Lab, day, generate_sql, load_config, norm, run, write_csv
from demo_data import build_demo

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        build_demo(self.root/'demo')
        self.input=self.root/'demo'/'input'
        self.cfg=self.root/'demo'/'demo_config.json'

    def tearDown(self):
        self.temp.cleanup()

    def execute(self, name='results', config=None, as_of='2026-10-29'):
        result=run(self.input,self.root/name,config or self.cfg,as_of)
        connection=sqlite3.connect(result/'bond_radar.sqlite')
        connection.row_factory=sqlite3.Row
        self.addCleanup(connection.close)
        return connection,result

    def edit(self, source, change):
        path=self.input/(source+'.csv')
        with path.open(newline='') as handle:
            reader=csv.DictReader(handle);columns=reader.fieldnames;rows=list(reader)
        change(rows)
        columns=list(dict.fromkeys(columns+[c for row in rows for c in row]))
        write_csv(path,columns,([r.get(c,'') for c in columns] for r in rows))

    def test_normalisation_dates_and_leading_zeros(self):
        self.assertEqual(norm(' 000001 '),'000001')
        self.assertEqual(day('20261029'),'2026-10-29')
        self.assertIsNone(day('99991231'))
        self.assertIsNone(day('20260230'))

    def test_sig01_missing_drawn_zero_policy_does_not_change_sig06_or_raw(self):
        self.edit('clo', lambda rows: [r.update(facility_drawn_amount='') for r in rows if r['obligor_cin']=='000001'])
        db,_=self.execute()
        row=db.execute("SELECT value,details_json FROM signal_evidence WHERE signal_id='SIG01' AND client_id='CIN:000001'").fetchone()
        self.assertEqual(row['value'],'0')
        details=json.loads(row['details_json'])
        self.assertTrue(details['current_missing_imputed_zero'])
        self.assertTrue(details['previous_missing_imputed_zero'])
        util=db.execute("SELECT assessment_status,value FROM signal_evidence WHERE signal_id='CTX_UTIL' AND source='clo' AND client_id='CIN:000001'").fetchone()
        self.assertEqual(tuple(util),('unavailable',None))
        self.assertEqual(db.execute("SELECT COUNT(*) FROM raw_clo WHERE obligor_cin='000001' AND facility_drawn_amount='' ").fetchone()[0],3)

    def test_sig01_invalid_drawn_is_not_zero_and_no_prior_is_not_a_zero_baseline(self):
        self.edit('clo', lambda rows: [r.update(facility_drawn_amount='BROKEN') for r in rows if r['obligor_cin']=='000001'])
        db,_=self.execute()
        row=db.execute("SELECT value,assessment_status,details_json FROM signal_evidence WHERE signal_id='SIG01' AND client_id='CIN:000001'").fetchone()
        self.assertEqual((row['value'],row['assessment_status']),(None,'unavailable'))
        self.assertFalse(json.loads(row['details_json'])['current_missing_imputed_zero'])
        self.assertIn('no_prior_observation',db.execute("SELECT reason FROM signal_evidence WHERE signal_id='SIG01' AND client_id='CIN:000002'").fetchone()[0])

    def test_drr_uid_consolidates_borrower_associations_but_withholds_amount_conflicts(self):
        def change(rows):
            rows[0].update(drr_uid='UID1')
            rows.append(dict(rows[0],cin='000002',gid='G002',source_system_unique_id='another-row'))
        self.edit('drr',change)
        db,_=self.execute()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM observations WHERE source='drr'").fetchone()[0],1)
        self.assertEqual(db.execute("SELECT value FROM signal_evidence WHERE source='drr' AND signal_id='CTX_UTIL'").fetchone()[0],'80.0')
        self.edit('drr',lambda rows:rows[1].update(utilisation='90'))
        db,_=self.execute(name='drr_conflict')
        self.assertEqual(db.execute("SELECT assessment_status FROM signal_evidence WHERE source='drr' AND signal_id='CTX_UTIL'").fetchone()[0],'unavailable')

    def test_current_only_does_not_publish_departed_facility_from_baseline_snapshot(self):
        cfg=json.loads(self.cfg.read_text());cfg['current_snapshot_only']=True
        self.cfg.write_text(json.dumps(cfg))
        db,_=self.execute()
        # F006 has only the older baseline date and must not become a current alert.
        self.assertEqual(db.execute("SELECT COUNT(*) FROM signal_evidence WHERE record_key LIKE '%F006%'").fetchone()[0],0)

    def test_full_workflow_deduplicates_and_combines_signal_evidence(self):
        db,out=self.execute()
        row=db.execute("SELECT value,denominator,triggered FROM signal_evidence WHERE source='clo' AND signal_id='CTX_UTIL' AND client_id='CIN:000001'").fetchone()
        self.assertEqual(tuple(row),('80.0','100',1))
        change=db.execute("SELECT value,previous_value FROM signal_evidence WHERE signal_id='SIG01' AND client_id='CIN:000001'").fetchone()
        self.assertEqual(tuple(change),('40','40'))
        self.assertEqual(db.execute('SELECT COUNT(*) FROM clo_enriched').fetchone()[0],12)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM raw_clo').fetchone()[0],12)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM observations WHERE source='clo'").fetchone()[0],9)
        self.assertEqual(db.execute("SELECT COUNT(DISTINCT source) FROM signal_evidence WHERE client_id='CIN:000001'").fetchone()[0],6)
        self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertTrue((out/'REPORT.md').exists())
        for signal in ('SIG03A','SIG03B','SIG07'):
            self.assertEqual(db.execute("SELECT status FROM signal_assessments WHERE client_id='CIN:000001' AND signal_id=?",(signal,)).fetchone()[0],'unavailable')

    def test_counterparty_combines_routes_preserves_original_and_dates(self):
        db,_=self.execute()
        conflict=db.execute("SELECT * FROM clo_enriched WHERE cin='000005'").fetchone()
        self.assertEqual(conflict['match_status'],'ambiguous')
        self.assertIsNone(conflict['final_mastergroup'])
        original=db.execute("SELECT * FROM clo_enriched WHERE cin='000004'").fetchone()
        self.assertEqual(original['final_mastergroup'],'MG_ORIGINAL')
        self.assertEqual(original['match_status'],'source_conflict')
        historical=db.execute("SELECT * FROM clo_enriched WHERE cin='000006'").fetchone()
        self.assertEqual(historical['match_status'],'unmatched')
        self.assertEqual(json.loads(conflict['combined_candidates']),['MG005','MG_DIFFERENT'])

    def test_latest_inactive_mapping_does_not_resurrect_old_active(self):
        def edit(rows):
            rows.append(dict(rows[0],run_date='20261027',customer_relationship_lifecycle_status_code='INACTIVE'))
        self.edit('counterparty',edit)
        db,_=self.execute()
        recent=db.execute("SELECT match_status,cin_mapping_date FROM clo_enriched WHERE cin='000001' AND observation_date='2026-10-28' LIMIT 1").fetchone()
        self.assertEqual(tuple(recent),('unmatched','2026-10-27'))

    def test_threshold_zero_limit_conflicts_and_multi_borrower(self):
        db,_=self.execute()
        exact=db.execute("SELECT triggered FROM signal_evidence WHERE signal_id='CTX_UTIL' AND client_id='CIN:000002'").fetchone()
        self.assertEqual(exact[0],0)
        zero=db.execute("SELECT triggered,assessment_status FROM signal_evidence WHERE signal_id='CTX_UTIL' AND client_id='CIN:000003'").fetchone()
        self.assertEqual(tuple(zero),(None,'unavailable'))
        conflict=db.execute("SELECT value,assessment_status FROM signal_evidence WHERE source='clo' AND signal_id='CTX_UTIL' AND client_id='CIN:000009'").fetchone()
        self.assertEqual(tuple(conflict),(None,'unavailable'))
        shared=db.execute("SELECT client_id,mastergroup_id FROM observations WHERE source='clo' AND mapping_status LIKE '%multiple_borrowers%'").fetchall()
        self.assertEqual(len(shared),1)
        self.assertIsNone(shared[0]['mastergroup_id'])
        self.assertEqual(db.execute("SELECT COUNT(*) FROM signal_evidence WHERE component='financial_covenant' AND triggered=1").fetchone()[0],2)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM signal_evidence WHERE signal_id='SIG07' AND triggered IS NOT NULL").fetchone()[0],0)

    def test_old_event_in_recent_snapshot_does_not_trigger(self):
        db,_=self.execute()
        old=db.execute("SELECT triggered FROM signal_evidence WHERE signal_id='SIG04' AND event_date='2018-01-01'").fetchone()
        self.assertEqual(old[0],0)

    def test_unverified_real_defaults_never_publish_candidate_triggers(self):
        db,_=self.execute(config=ROOT/'config.json')
        self.assertEqual(db.execute('SELECT COUNT(*) FROM signal_evidence WHERE triggered IS NOT NULL').fetchone()[0],0)
        self.assertGreater(db.execute("SELECT COUNT(*) FROM signal_evidence WHERE assessment_status='needs_validation'").fetchone()[0],0)

    def test_future_observations_and_identity_conflicts(self):
        columns=['source','identifier_type','identifier_value','client_id','mastergroup_id','valid_from','valid_to']
        write_csv(self.input/'identity_links.csv',columns,[['pvd','JOI_RELATIONSHIP_ID','REL_PVD1','CLIENT_A','','',''],['pvd','JOI_RELATIONSHIP_ID','REL_PVD1','CLIENT_B','','','']])
        db,_=self.execute()
        self.assertIn('ambiguous_identity_link',db.execute("SELECT mapping_status FROM observations WHERE source='pvd'").fetchone()[0])
        self.edit('clo',lambda rows:rows.append(dict(rows[0],run_date='20261101')))
        db2,_=self.execute(name='future')
        self.assertEqual(db2.execute('SELECT COUNT(*) FROM raw_clo').fetchone()[0],13)
        self.assertEqual(db2.execute('SELECT COUNT(*) FROM clo_enriched').fetchone()[0],12)

    def test_bad_exports_do_not_replace_successful_runs(self):
        _,out=self.execute()
        original=(out/'bond_radar.sqlite').read_bytes()
        with self.assertRaises(ValueError):run(self.input,out,self.cfg,'2026-10-29')
        self.assertEqual((out/'bond_radar.sqlite').read_bytes(),original)
        with (self.input/'clo.csv').open('a') as handle:handle.write('ragged,row\n')
        with self.assertLogs(level='ERROR'):
            with self.assertRaises(ValueError):run(self.input,self.root/'bad',self.cfg,'2026-10-29')
        self.assertFalse((self.root/'bad').exists())
        self.assertEqual((out/'bond_radar.sqlite').read_bytes(),original)

    def test_header_only_and_missing_sources_remain_unavailable(self):
        for p in self.input.glob('*.csv'):
            if p.name!='identity_links.csv':p.unlink()
        write_csv(self.input/'kyc.csv',['run_date','cin','related_case_id'],[])
        db,_=self.execute()
        self.assertEqual(db.execute('SELECT COUNT(*) FROM signal_evidence').fetchone()[0],0)
        self.assertGreater(db.execute("SELECT COUNT(*) FROM quality_issues WHERE check_name='input_missing'").fetchone()[0],0)

    def test_sql_bounds_and_unconfirmed_counterparty(self):
        out=self.root/'sql'
        generate_sql(out,'2026-10-01','2026-10-29')
        text=(out/'clo'/'02_extract.sql').read_text()
        self.assertIn("t.\"run_date\" >= '20261001'",text)
        self.assertNotIn('LIMIT',text)
        self.assertFalse((out/'counterparty'/'02_extract.sql').exists())
        self.assertTrue((out/'counterparty'/'01_schema.sql').exists())
        generate_sql(self.root/'confirmed','2026-10-01','2026-10-29',True)
        cp=(self.root/'confirmed'/'counterparty'/'02_extract.sql').read_text()
        self.assertIn('20260603',cp)
        self.assertNotIn('agg_sec', ''.join(p.read_text() for p in out.rglob('*.sql')))

    def test_missing_scope_is_retained_and_qualified(self):
        self.edit('clo',lambda rows:[r.update(source_system='') for r in rows])
        db,_=self.execute()
        self.assertEqual(db.execute('SELECT COUNT(*) FROM clo_enriched').fetchone()[0],12)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM observations WHERE source='clo' AND mapping_status LIKE '%incomplete_source_scope%'").fetchone()[0],9)

    def test_currency_mismatch_and_negative_numerator_withhold_ratio(self):
        self.edit('drr',lambda rows:rows[0].update(utilisation_ccy='USD'))
        self.edit('pvd',lambda rows:rows[0].update(drr_utils='-5'))
        db,_=self.execute()
        for source in ('drr','pvd'):
            result=db.execute("SELECT value,triggered,assessment_status FROM signal_evidence WHERE source=? AND component='utilisation'",(source,)).fetchone()
            self.assertEqual(tuple(result),(None,None,'unavailable'))

    def test_chunk_lineage_and_conflicting_input_routes(self):
        original=self.input/'clo.csv'
        with original.open(newline='') as handle:
            reader=csv.reader(handle);columns=next(reader);rows=list(reader)
        original.unlink()
        write_csv(self.input/'clo'/'part-001.csv',columns,rows[:2])
        write_csv(self.input/'clo'/'part-002.csv',columns,rows[2:])
        db,_=self.execute()
        lineage=db.execute("SELECT DISTINCT input_file FROM evidence_lineage WHERE source='clo'").fetchall()
        self.assertEqual(len(lineage),2)  # F001's latest observation spans both chunks
        f002=db.execute("SELECT DISTINCT l.input_file FROM evidence_lineage l JOIN signal_evidence e ON e.evidence_id=l.evidence_id WHERE e.client_id='CIN:000002' AND e.source='clo'").fetchall()
        self.assertEqual(len(f002),1)
        self.assertTrue(f002[0][0].endswith('part-002.csv'))
        write_csv(original,columns,rows)
        with self.assertLogs(level='ERROR'):
            with self.assertRaises(ValueError):run(self.input,self.root/'bad_routes',self.cfg,'2026-10-29')

    def test_later_pvd_processing_date_is_excluded(self):
        path=self.input/'pvd.csv'
        with path.open(newline='') as handle:
            reader=csv.DictReader(handle);columns=reader.fieldnames;rows=list(reader)
        rows[0]['etlmonth']='2026-11-01'
        write_csv(path,columns,([r.get(c,'') for c in columns] for r in rows))
        db,_=self.execute()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM observations WHERE source='pvd'").fetchone()[0],0)

    def test_read_only_query_refuses_mutation(self):
        from bond_radar import query
        _,out=self.execute()
        with self.assertRaises(sqlite3.OperationalError):query(out/'bond_radar.sqlite','DELETE FROM raw_clo')

    def test_increase_threshold_does_not_cross_currency(self):
        self.edit('clo',lambda rows:[r.update(facility_currency='JPY') for r in rows if r['obligor_cin']=='000001'])
        db,_=self.execute()
        row=db.execute("SELECT value,triggered,assessment_status FROM signal_evidence WHERE signal_id='SIG01' AND client_id='CIN:000001'").fetchone()
        self.assertEqual(tuple(row),('40',None,'needs_validation'))

    def test_old_financial_test_is_not_current_breach_evidence(self):
        self.edit('covenants',lambda rows:rows[0].update(reporting_dt='2018-01-01'))
        db,_=self.execute()
        row=db.execute("SELECT triggered,assessment_status,reason FROM signal_evidence WHERE component='financial_covenant' AND event_date='2018-01-01'").fetchone()
        self.assertEqual(tuple(row)[:2],(None,'unavailable'))
        self.assertIn('financial_test_outside_development_event_window',row['reason'])

if __name__=='__main__':unittest.main()
