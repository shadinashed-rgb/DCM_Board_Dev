import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sig07_crr import export, select_context


class Sig07CrrTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.input=self.root/'input';self.input.mkdir()
        self.base=self.root/'base.csv';self.write(self.base,[dict(signal_id='SIG01',source='clo',evidence_id='KEEP',metric_value='12')])
        self.inventory=self.root/'ids.csv'
        self.write(self.inventory,[dict(mastergroup_id='MG001356',identifier_kind='CIN',identifier_value='00001')])

    def write(self,path,rows):
        with path.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

    def row(self,**changes):
        row=dict(run_date='20261103',cin='00001',final_crr='3.1',crr_scale='1',record_start_dt='20260901',record_end_dt='99991231',
            source_system_name='cfc',country_code='GB',carm_instance='TEST',credit_proposal_serial_no='APP1',
            latest_record='HISTORICAL',latest_approved_appl_flag='1',previous_crr='3.2',approved_crr='',s_and_p_long_term_rating='AAA')
        row.update(changes);return row

    def run_export(self,rows,name='run'):
        self.write(self.input/'application_ratings_vodafone.csv',rows)
        result=export(self.input,self.base,self.root/name,'2026-11-04',self.inventory)
        with (self.root/name/'SIG07_Application_Ratings_CRR.csv').open(encoding='utf-8-sig',newline='') as f:
            exported=list(csv.DictReader(f))
        return result,exported

    def test_crr_only_addition_preserves_other_evidence_and_text_codes(self):
        original=self.base.read_bytes();result,rows=self.run_export([self.row()])
        self.assertEqual(rows[0]['crr'],'3.1');self.assertEqual(rows[0]['previous_crr'],'3.2')
        self.assertEqual(rows[0]['business_trigger'],'');self.assertEqual(rows[0]['cins'],'00001')
        self.assertNotIn('AAA',json.dumps(rows));self.assertNotIn('s_and_p',json.dumps(rows))
        self.assertEqual(result['combined_rows'],2);self.assertEqual(self.base.read_bytes(),original)

    def test_missing_crr_is_unknown_and_never_uses_approved_fallback(self):
        result,rows=self.run_export([self.row(final_crr='N/A',approved_crr='2.1')])
        self.assertEqual(rows[0]['crr'],'');self.assertEqual(rows[0]['crr_raw'],'N/A')
        self.assertEqual(rows[0]['assessment_status'],'unavailable');self.assertEqual(result['missing_crr'],1)
        self.assertIn('missing_final_crr',rows[0]['validation_reason'])

    def test_latest_snapshot_precedes_validity_and_does_not_resurrect_old_application(self):
        rows=[self.row(run_date='20261102'),self.row(run_date='20261103',record_end_dt='20261102')]
        selected,_=select_context(rows,'2026-11-04');self.assertEqual(selected,[])
        selected,_=select_context([self.row(run_date='20261105')],'2026-11-04');self.assertEqual(selected,[])

    def test_open_historical_and_competing_crrs_remain_visible(self):
        _,rows=self.run_export([self.row(),self.row(final_crr='2.1',credit_proposal_serial_no='APP2')])
        self.assertEqual(len(rows),2);self.assertEqual({r['crr'] for r in rows},{'2.1','3.1'})
        self.assertTrue(all(r['multiple_crrs_for_cin']=='True' for r in rows))
        self.assertTrue(all(r['latest_record']=='HISTORICAL' for r in rows))

    def test_full_file_precedes_sample_and_unknown_group_is_not_assigned(self):
        self.write(self.input/'application_ratings_vodafone_full.csv',[self.row(final_crr='2.2')])
        _,rows=self.run_export([self.row()]);self.assertEqual(rows[0]['crr'],'2.2')
        self.write(self.inventory,[dict(mastergroup_id='MG101624',identifier_kind='CIN',identifier_value='00001')])
        result=export(self.input,self.base,self.root/'unmapped','2026-11-04',self.inventory)
        with (self.root/'unmapped/SIG07_Application_Ratings_CRR.csv').open(encoding='utf-8-sig',newline='') as f:row=next(csv.DictReader(f))
        self.assertEqual(row['mastergroup_id'],'');self.assertEqual(row['assessment_status'],'unavailable')
        self.assertIn('cin_cohort_link_unresolved',row['validation_reason'])

    def test_exact_duplicates_do_not_add_signal_items(self):
        result,rows=self.run_export([self.row(),self.row()])
        self.assertEqual(len(rows),1);self.assertEqual(result['selection'][0]['exact_duplicates'],1)

    def test_rerun_replaces_existing_application_contribution(self):
        self.run_export([self.row()])
        combined=self.root/'run/DCM_Run_003_All_Signal_Evidence_With_CRR.csv'
        result=export(self.input,combined,self.root/'again','2026-11-04',self.inventory)
        self.assertEqual(result['combined_rows'],2)


if __name__=='__main__':unittest.main()
