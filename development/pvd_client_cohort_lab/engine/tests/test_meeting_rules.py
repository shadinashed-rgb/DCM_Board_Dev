"""development-2 rules agreed in the DCM meetings (see docs/MEETING_ALIGNMENT_REVIEW.md)."""
import csv
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bond_radar import ROOT, load_config, run, write_csv
from demo_data import build_demo


class MeetingRuleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);build_demo(self.root/'demo')
        self.input=self.root/'demo'/'input';self.cfg_path=self.root/'demo'/'demo_config.json'

    def config(self,change):
        cfg=json.loads(self.cfg_path.read_text());change(cfg);self.cfg_path.write_text(json.dumps(cfg))

    def edit(self,source,change):
        path=self.input/(source+'.csv')
        with path.open(newline='') as handle:
            reader=csv.DictReader(handle);columns=reader.fieldnames;rows=list(reader)
        change(rows);columns=list(dict.fromkeys(columns+[c for row in rows for c in row]))
        write_csv(path,columns,([r.get(c,'') for c in columns] for r in rows))

    def execute(self,name='results'):
        result=run(self.input,self.root/name,self.cfg_path,'2026-10-29')
        db=sqlite3.connect(result/'bond_radar.sqlite');db.row_factory=sqlite3.Row;self.addCleanup(db.close)
        return db

    def sig01(self,db,component='drawing_change'):
        row=db.execute("SELECT * FROM signal_evidence WHERE signal_id='SIG01' AND component=? AND client_id='CIN:000001'",(component,)).fetchone()
        return row,json.loads(row['details_json'])

    def test_material_drawing_on_cat_a_facility_triggers(self):
        # F001 draws 40 -> 80 GBP; demo threshold is GBP 10; Facilities says F001 is CAT-A.
        row,details=self.sig01(self.execute())
        self.assertEqual((row['value'],row['triggered'],row['assessment_status']),('40',1,'assessed'))
        self.assertEqual((details['limit_category'],details['cat_a_eligible']),('CAT-A',True))
        self.assertEqual(details['materiality_status'],'hsbc_share_meets_threshold')

    def test_term_loan_drawings_are_eligible_products(self):
        self.edit('clo',lambda rows:[r.update(local_product_type_lbs='TERM') for r in rows if r['sub_lim_id']=='F001'])
        row,details=self.sig01(self.execute())
        self.assertEqual((row['triggered'],details['product']),(1,'TERM'))

    def test_non_cat_a_facility_is_not_triggered(self):
        self.edit('facilities',lambda rows:[r.update(limit_cat='CAT-B') for r in rows if r['facility_id']=='F001'])
        row,details=self.sig01(self.execute())
        self.assertEqual((row['triggered'],details['cat_a_eligible']),(0,False))
        self.assertIn('limit_category_not_eligible',row['reason'])

    def test_unlinked_category_withholds_trigger(self):
        self.edit('facilities',lambda rows:[r.update(facility_id='OTHER') for r in rows if r['facility_id']=='F001'])
        row,details=self.sig01(self.execute())
        self.assertEqual((row['triggered'],row['assessment_status']),(None,'needs_validation'))
        self.assertIn('limit_category_unlinked',row['reason'])

    def test_inferred_total_uses_hsbc_participation_share(self):
        # HSBC draws 40 GBP at a 25% share -> inferred total 160 >= threshold 100.
        self.config(lambda c:c['sig01']['materiality'].update(threshold_amount=100,participation_share_field='hsbc_share_pct'))
        self.edit('clo',lambda rows:[r.update(hsbc_share_pct='25') for r in rows])
        row,details=self.sig01(self.execute())
        self.assertEqual(details['inferred_total_drawing'],'160')
        self.assertEqual((details['materiality_status'],row['triggered']),('inferred_total_meets_threshold',1))
        self.config(lambda c:c['sig01']['materiality'].update(participation_share_field=None))
        row,details=self.sig01(self.execute('no_share'))
        self.assertEqual((details['materiality_status'],row['triggered']),('hsbc_share_below_threshold_participation_unknown',None))

    def test_sole_lender_means_full_share(self):
        self.config(lambda c:c['sig01']['materiality'].update(threshold_amount=100))
        self.edit('clo',lambda rows:[r.update(deal_indicator_sole_lender='Y') for r in rows])
        row,details=self.sig01(self.execute())
        self.assertEqual((details['inferred_total_drawing'],details['materiality_status']),('40','inferred_total_below_threshold'))
        self.assertEqual(row['triggered'],0)

    def test_fx_is_applied_only_from_configured_rates(self):
        self.edit('clo',lambda rows:[r.update(facility_currency='USD') for r in rows if r['obligor_cin']=='000001'])
        row,details=self.sig01(self.execute())
        self.assertEqual((details['materiality_status'],row['triggered']),('fx_rate_not_configured',None))
        self.config(lambda c:c['sig01']['materiality'].update(fx_to_threshold_currency={'USD':'0.5'}))
        row,details=self.sig01(self.execute('fx'))
        self.assertEqual((details['drawing_in_threshold_currency'],row['triggered']),('20.0',1))

    def test_imputed_zero_is_never_material(self):
        self.edit('clo',lambda rows:[r.update(facility_drawn_amount='') for r in rows if r['obligor_cin']=='000001'])
        row,details=self.sig01(self.execute())
        self.assertEqual((row['value'],details['materiality_status'],row['triggered']),('0','imputed_values_not_assessable',None))

    def test_alternative_drawn_field_is_a_separate_comparison(self):
        self.config(lambda c:c['sig01'].update(alternative_drawn_fields=[{'field':'ag_acc_bal_drawn_sub_lim_usd','currency':'USD','component':'drawing_change_alt_usd'}]))
        self.edit('clo',lambda rows:[r.update(ag_acc_bal_drawn_sub_lim_usd='100' if r['run_date']=='20261001' else '175') for r in rows])
        db=self.execute()
        main,_=self.sig01(db);alt,details=self.sig01(db,'drawing_change_alt_usd')
        self.assertEqual((main['value'],alt['value'],alt['currency']),('40','75','USD'))
        self.assertEqual(details['drawn_field'],'ag_acc_bal_drawn_sub_lim_usd')

    def test_sig02_prefers_credit_approval_date(self):
        self.edit('facilities',lambda rows:[r.update(loan_approva_dt='20261015') for r in rows if r['facility_id']=='DEMO_NEW_FAC'])
        db=self.execute()
        row=db.execute("SELECT * FROM signal_evidence WHERE signal_id='SIG02' AND record_key LIKE '%DEMO_NEW_FAC%'").fetchone()
        details=json.loads(row['details_json'])
        self.assertEqual((row['event_date'],details['event_basis']),('2026-10-15','credit_approval_date'))
        self.edit('facilities',lambda rows:[r.update(loan_approva_dt='0') for r in rows])
        db=self.execute('placeholder')
        row=db.execute("SELECT * FROM signal_evidence WHERE signal_id='SIG02' AND record_key LIKE '%DEMO_NEW_FAC%'").fetchone()
        self.assertEqual((row['event_date'],json.loads(row['details_json'])['event_basis']),('2026-10-20','facility_creation_date_candidate_approval'))

    def test_covenant_pressure_is_within_half_a_turn_of_maximum(self):
        db=self.execute()
        rows={json.loads(r['details_json'])['testing_id']:(r['triggered'],json.loads(r['details_json'])) for r in db.execute("SELECT * FROM signal_evidence WHERE component='financial_covenant' AND assessment_status='assessed'")}
        self.assertEqual((rows['TEST1'][0],rows['TEST1'][1]['breach_for_testing']),(1,True))          # 4.0x vs 3.0x
        self.assertEqual((rows['TEST3'][0],rows['TEST3'][1]['pressure_for_testing'],rows['TEST3'][1]['breach_for_testing']),(1,True,False))  # 2.6x
        self.assertEqual((rows['TEST4'][0],rows['TEST4'][1]['pressure_for_testing']),(0,False))      # 2.4x

    def test_utilisation_and_category_are_context_not_signals(self):
        db=self.execute()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM signal_evidence WHERE signal_id='SIG06' AND component='utilisation'").fetchone()[0],0)
        self.assertGreater(db.execute("SELECT COUNT(*) FROM signal_evidence WHERE signal_id='CTX_UTIL'").fetchone()[0],0)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM signal_evidence WHERE signal_id='SIG07'").fetchone()[0],0)
        self.assertGreater(db.execute("SELECT COUNT(*) FROM signal_evidence WHERE signal_id='CTX_CREDIT'").fetchone()[0],0)

    def test_real_config_encodes_meeting_decisions_without_triggers(self):
        cfg=load_config(ROOT/'config.json')
        self.assertEqual(cfg['rule_version'],'development-2')
        self.assertEqual((cfg['sig01']['materiality']['threshold_amount'],cfg['sig01']['materiality']['threshold_currency']),(50000000,'EUR'))
        self.assertEqual(cfg['sig01']['eligible_limit_categories'],['CAT-A'])
        self.assertIn('TERM',cfg['sig01']['products'])
        self.assertEqual(cfg['sig02']['event_fields'][0]['basis'],'credit_approval_date')
        self.assertEqual(cfg['covenants']['pressure_headroom_turns'],0.5)
        self.assertFalse(cfg['sig01']['definitions_verified'])
        result=run(self.input,self.root/'real',ROOT/'config.json','2026-10-29')
        with sqlite3.connect(result/'bond_radar.sqlite') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM signal_evidence WHERE triggered IS NOT NULL').fetchone()[0],0)


if __name__=='__main__':unittest.main()
