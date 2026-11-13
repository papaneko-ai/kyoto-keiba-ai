"""R08 acceptance: P1 three original bytes -> full 16-runner P4 EV; synthetic only."""
import copy
import unittest
from itertools import combinations
from diagnostics.jra_p1_offline_handoff import export_bundle
from diagnostics.p4_source_bound_model_ev_research import compare_source_market_to_frozen_model
from diagnostics.p4_temporal_market_controls import TemporalMarketRejected
import test_p1_three_original_content_binding as binding

class R08FullMarketAcceptance(unittest.TestCase):
    def setUp(self):
        f=binding.StrictThreeOriginalContentTests(methodName='test_all_three_originals_match')
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.fixture=f
        runners=[{'number':i,'horse_id':f'horse{i:04d}','name':f'H{i:02d}',
            'bracket':(i+1)//2,'status':'ACTIVE'} for i in range(1,17)]
        f.snapshot['runners']=runners
        horse_pairs=list(combinations(range(1,17),2))
        frame_pairs=[(i,j) for i in range(1,9) for j in range(i,9)]
        f.snapshot['odds']=[{'first':i,'second':j,'decimal':float(2+i+j)} for i,j in horse_pairs]
        f.snapshot['bracket_odds']=[{'first':i,'second':j,'decimal':float(3+i+j)} for i,j in frame_pairs]
        roster='<html><body>2026年11月14日 1レース<table><tr><th class="horse"></th><th class="num"></th><th class="waku"></th></tr>'
        for i in range(1,17):
            roster+=(f'<tr><td class="horse"><a href="/JRADB/accessU.html?CNAME=h{i}">H{i:02d}</a></td>'
                     f'<td class="num">{i}</td><td class="waku"><img alt="枠{(i+1)//2}"></td></tr>')
        f.set_original(0,(roster+'</table></body></html>').encode('cp932'))
        q=[' '.join([str(i)]+[f'{j} {2+i+j:.1f}' for j in range(i+1,17)]) for i in range(1,16)]
        b=[' '.join(f'{j} {3+i+j:.1f}' for j in range(i,9)) for i in range(1,9)]
        f.set_original(1,binding.market_html('馬連オッズ','umaren',q))
        f.set_original(2,binding.market_html('枠連オッズ','waku',b))
        self.model={'provenance':'LAB_SYNTHETIC_ONLY','race_date':'2026-11-14',
            'race_number':1,'venue':'京都','frozen_utc':'2026-11-13T04:00:00Z',
            'cutoff_utc':'2026-11-14T04:50:00Z',
            'strengths':{str(i):float(i) for i in range(1,17)},
            'source_feature_sha256':'a'*64,'model_version':'LAB-R08-FULL'}
    def check(self,mutate=None,model_mutate=None,**opts):
        s=copy.deepcopy(self.fixture.snapshot)
        m=copy.deepcopy(self.model)
        if mutate:mutate(s)
        if model_mutate:model_mutate(m)
        bundle=export_bundle(self.fixture.manifest,self.fixture.root,observed_utc=binding.NOW)
        return compare_source_market_to_frozen_model(bundle=bundle,snapshot=s,
            observed_utc=binding.NOW,channel='PC',frozen_model=m,**opts)
    def reject(self,mutate=None,model_mutate=None,**opts):
        with self.assertRaises(ValueError):self.check(mutate,model_mutate,**opts)
    def test_full_16_horse_120_pair_and_36_bracket_pair_ev(self):
        r=self.check()
        self.assertEqual(r['markets']['QUINELLA']['full_pair_count'],120)
        self.assertEqual(r['markets']['BRACKET']['full_pair_count'],36)
        self.assertFalse(r['source_official_origin_authenticated'])
        self.assertFalse(r['real_race_prediction_ready'])
        self.assertFalse(r['actual_purchase_authorized'])
        self.assertEqual(r['network_requests'],0)
    def test_eight_same_bracket_pairs(self):
        pairs=self.check()['markets']['BRACKET']['research_model_expected_net']
        self.assertEqual(sum(row['pair'][0]==row['pair'][1] for row in pairs),8)
    def test_same_fixture_repeats(self):self.assertEqual(self.check(),self.check())
    def test_stressed_ev_not_above_nominal(self):
        for market in self.check()['markets'].values():
            for row in market['research_model_expected_net']:
                self.assertLessEqual(row['stressed_net_lower'],row['expected_net_per_unit'])
    def test_model_change_changes_receipt(self):
        before=self.check()['comparison_sha256']
        after=self.check(model_mutate=lambda m:m['strengths'].update({'1':99.}))['comparison_sha256']
        self.assertNotEqual(before,after)
    def test_missing_horse_pair(self):self.reject(mutate=lambda s:s['odds'].pop())
    def test_missing_same_bracket_pair(self):self.reject(mutate=lambda s:s['bracket_odds'].pop(0))
    def test_duplicate_horse_pair(self):
        self.reject(mutate=lambda s:s['odds'].append(copy.deepcopy(s['odds'][0])))
    def test_duplicate_frame_pair(self):
        self.reject(mutate=lambda s:s['bracket_odds'].append(copy.deepcopy(s['bracket_odds'][0])))
    def test_fake_horse_price(self):
        self.reject(mutate=lambda s:s['odds'][0].update(decimal=999.))
    def test_fake_frame_price(self):
        self.reject(mutate=lambda s:s['bracket_odds'][0].update(decimal=999.))
    def test_suspended_quinella(self):
        self.reject(mutate=lambda s:s['market_states']['quinella'].update(sales='SUSPENDED'))
    def test_suspended_bracket(self):
        self.reject(mutate=lambda s:s['market_states']['bracket'].update(sales='SUSPENDED'))
    def test_withdrawn_horse(self):
        self.reject(mutate=lambda s:s['runners'][0].update(status='WITHDRAWN'))
    def test_market_clock_mismatch(self):
        self.reject(mutate=lambda s:s['market_states']['bracket'].update(observed_utc='2026-11-13T04:04:00Z'))
    def test_late_price_capture(self):
        self.reject(mutate=lambda s:s['sources']['odds'].update(captured_utc='2026-11-14T05:00:00Z'))
    def test_market_freshness(self):self.reject(max_age_seconds=60)
    def test_other_race_model(self):
        self.reject(model_mutate=lambda m:m.update(race_number=2))
    def test_future_frozen_model(self):
        self.reject(model_mutate=lambda m:m.update(frozen_utc='2026-11-15T00:00:00Z'))
    def test_different_roster_model(self):
        self.reject(model_mutate=lambda m:m['strengths'].update({'19':1.}))
    def test_nonfinite_model_weight(self):
        self.reject(model_mutate=lambda m:m['strengths'].update({'1':float('nan')}))
    def test_unbounded_risk_config(self):self.reject(probability_error_bound=1.5)
    def test_snapshot_name_not_in_original(self):
        self.reject(mutate=lambda s:s['runners'][0].update(name='FORGED'))
    def test_uncalibrated_model_cannot_claim_live(self):
        r=self.check()
        self.assertFalse(r['model_externally_calibrated'])
        self.assertFalse(r['official_sales_withdrawals_authenticated'])
        self.assertEqual(r['real_paper_trades_written'],0)

if __name__=='__main__':unittest.main()
