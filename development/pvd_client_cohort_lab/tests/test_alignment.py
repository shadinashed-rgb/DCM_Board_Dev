"""SIG02 credit approval date linking (development-2)."""
import csv
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from alignment import apply


class AlignmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.ratings=self.root/'ratings';self.ratings.mkdir()

    def write(self,path,rows):
        with path.open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

    def evidence(self,**changes):
        row=dict(signal_id='SIG02',assessment_status='needs_validation',cins='C1',credit_proposal_serial_no='260917',source_creation_dates='20260917',
                 event_date='2026-09-17',event_age_days='47',event_lookback_days='90',recent_creation_for_testing='True',event_basis='facility_creation_date_candidate_approval',
                 validation_reason='event_date_is_candidate_approval_date;event_and_product_meaning_unverified',review_type='recent_approval_for_testing',
                 credit_approval_date='',credit_approval_source='',approval_matches_creation_date='',details_json='{}',evidence_id='E1')
        row.update(changes);return row

    def run_apply(self,evidence,ratings,name='out.csv'):
        self.write(self.root/'combined.csv',evidence);self.write(self.ratings/'application_ratings_x_full.csv',ratings)
        result=apply(self.root/'combined.csv',self.ratings,self.root/name,'2026-11-03')
        with (self.root/name).open(encoding='utf-8-sig',newline='') as f:return result,list(csv.DictReader(f))

    def test_serial_and_cin_link_sets_approval_date(self):
        result,rows=self.run_apply([self.evidence()],[dict(cin='C1',credit_proposal_serial_no='260917',approval_dt='20260917'),dict(cin='C2',credit_proposal_serial_no='260917',approval_dt='20260901')])
        r=rows[0]
        self.assertEqual((r['credit_approval_date'],r['event_basis'],r['approval_matches_creation_date']),('2026-09-17','credit_approval_date','True'))
        self.assertIn('approval_link_by_serial_unverified',r['validation_reason'])
        self.assertNotIn('event_date_is_candidate_approval_date',r['validation_reason'])
        self.assertEqual(result['sig02_approval_linking']['serial_and_cin_match'],1)

    def test_approval_date_drives_recency(self):
        _,rows=self.run_apply([self.evidence(source_creation_dates='20260917')],[dict(cin='C1',credit_proposal_serial_no='260917',approval_dt='20260601')])
        r=rows[0]
        self.assertEqual((r['event_date'],r['event_age_days'],r['recent_creation_for_testing'],r['approval_matches_creation_date']),('2026-06-01','155','False','False'))

    def test_conflicting_or_missing_links_leave_candidate_date(self):
        _,rows=self.run_apply([self.evidence(cins='C9')],[dict(cin='C1',credit_proposal_serial_no='260917',approval_dt='20260917'),dict(cin='C2',credit_proposal_serial_no='260917',approval_dt='20260901')])
        self.assertEqual((rows[0]['credit_approval_date'],rows[0]['credit_approval_source'],rows[0]['event_date']),('','conflicting_approval_dates','2026-09-17'))
        _,rows=self.run_apply([self.evidence(credit_proposal_serial_no='999')],[dict(cin='C1',credit_proposal_serial_no='260917',approval_dt='20260917')],'b.csv')
        self.assertEqual(rows[0]['credit_approval_source'],'serial_not_found_in_application_ratings')

    def test_other_signals_untouched(self):
        other=self.evidence(signal_id='SIG01',evidence_id='E2')
        _,rows=self.run_apply([other],[dict(cin='C1',credit_proposal_serial_no='260917',approval_dt='20260101')])
        self.assertEqual(rows[0]['event_date'],'2026-09-17');self.assertEqual(rows[0]['credit_approval_date'],'')


if __name__=='__main__':unittest.main()
