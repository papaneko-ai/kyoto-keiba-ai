"""P3/P5/P6 synthetic research pipeline and destructive integration tests."""
import copy,unittest
from diagnostics.p3_p5_p6_synthetic_pipeline_lab import (
    freeze_lab_market_scenario,replay_lab_settlement,LabBridgeRejected)
from diagnostics.p3_offline_model_tournament import predict
from diagnostics.p6_virtual_settlement_fixture_lab import LabRejected
from test_p3_offline_model_tournament import fixture,utc

def prepare(*,market="QUINELLA",odds=30.0):
    s=fixture(10)["snapshot"]
    pred=predict(s,"PL_BASE")
    prices=[{"pair":r["pair"],"decimal_odds":odds}
            for r in pred["quinella" if market=="QUINELLA" else "bracket"]]
    m={"race_id":s["race_id"],"market_type":market,
       "scope":"LAB_SYNTHETIC_ODDS_ONLY","prices":prices}
    return s,m
def freeze(s,m,**kw):
    return freeze_lab_market_scenario(s,model_id="PL_BASE",synthetic_market=m,
        observed_utc=utc(41),frozen_utc=utc(41.5),daily_budget_yen=10000,**kw)
class PipelineTests(unittest.TestCase):
 def test_quinella_freeze_budget_cap_and_replay(self):
    s,m=prepare()
    x=freeze(s,m)
    self.assertEqual(x["receipt"]["status"],"LAB_FIXTURE_FROZEN")
    self.assertLessEqual(x["receipt"]["spent_yen"],2000)
    self.assertEqual(x["receipt"]["spent_yen"]+x["receipt"]["unspent_yen"],10000)
    self.assertLessEqual(x["receipt"]["ticket_count"],2)
    self.assertIsNone(replay_lab_settlement(x,[])["profit_yen"])
    self.assertFalse(x["receipt"]["real_market_verified"])
 def test_bracket_same_frame_and_model_probability(self):
    s,m=prepare(market="BRACKET")
    x=freeze(s,m,ticket_type="BRACKET")
    self.assertTrue(x["frozen"])
    self.assertEqual(x["receipt"]["ticket_type"],"BRACKET")
 def test_final_payout_and_correction_replace_not_add(self):
    s,m=prepare();x=freeze(s,m)
    pair=x["frozen"]["frozen"]["tickets"][0]["pair"]
    label="-".join(map(str,pair))
    scenario=x["frozen"]["frozen"]["scenario_id"]
    def evt(v,amount,state="PAYOUT_FINAL"):
        return {"scenario_id":scenario,"source_kind":"FIXTURE","version":v,
            "state":state,"payout_per_100":{label:amount},"refunded_pairs":[]}
    a=replay_lab_settlement(x,[evt(1,500)])
    b=replay_lab_settlement(x,[evt(1,500),evt(2,900)])
    self.assertGreater(b["profit_yen"],a["profit_yen"])
    self.assertEqual(b["event_version"],2)
    self.assertTrue(b["not_official"])
 def test_preliminary_does_not_settle(self):
    s,m=prepare();x=freeze(s,m)
    scenario=x["frozen"]["frozen"]["scenario_id"]
    e={"scenario_id":scenario,"source_kind":"FIXTURE","version":1,
        "state":"RESULT_PRELIMINARY","payout_per_100":{},"refunded_pairs":[]}
    self.assertIsNone(replay_lab_settlement(x,[e])["profit_yen"])
 def test_low_ev_is_full_skip(self):
    s,m=prepare(odds=1.01);x=freeze(s,m)
    self.assertEqual(x["receipt"]["spent_yen"],0)
    self.assertIsNone(x["frozen"])
    self.assertEqual(replay_lab_settlement(x,[])["status"],"SKIPPED_LAB_NO_POSITION")
 def test_coverage_mismatch_rejected(self):
    s,m=prepare();m["prices"].pop()
    with self.assertRaisesRegex(LabBridgeRejected,"market_incomplete"):freeze(s,m)
 def test_duplicate_pair_rejected(self):
    s,m=prepare();m["prices"][1]["pair"]=m["prices"][0]["pair"]
    with self.assertRaisesRegex(LabBridgeRejected,"price_duplicate"):freeze(s,m)
 def test_unverified_real_market_claim_rejected(self):
    s,m=prepare();m["scope"]="JRA_REAL_PRERACE"
    with self.assertRaisesRegex(LabBridgeRejected,"synthetic_market_identity"):freeze(s,m)
 def test_wrong_race_rejected(self):
    s,m=prepare();m["race_id"]="LAB-OTHER"
    with self.assertRaises(LabBridgeRejected):freeze(s,m)
 def test_frozen_before_observation_rejected(self):
    s,m=prepare()
    with self.assertRaisesRegex(LabBridgeRejected,"market_not_observed"):
        freeze_lab_market_scenario(s,model_id="PL_BASE",synthetic_market=m,
            observed_utc=utc(41),frozen_utc=utc(40.5),daily_budget_yen=10000)
 def test_postrace_freeze_rejected(self):
    s,m=prepare()
    with self.assertRaisesRegex(LabBridgeRejected,"market_not_observed"):
        freeze_lab_market_scenario(s,model_id="PL_BASE",synthetic_market=m,
            observed_utc=utc(41),frozen_utc=utc(42),daily_budget_yen=10000)
 def test_late_features_rejected(self):
    s,m=prepare();s["feature_cutoff_utc"]=utc(42)
    with self.assertRaises(LabBridgeRejected):freeze(s,m)
 def test_fractional_stake_budget_rejected(self):
    s,m=prepare()
    with self.assertRaisesRegex(LabBridgeRejected,"policy_invalid"):
        freeze_lab_market_scenario(s,model_id="PL_BASE",synthetic_market=m,
            observed_utc=utc(41),frozen_utc=utc(41.5),daily_budget_yen=155)
 def test_replay_receipt_tamper_rejected(self):
    s,m=prepare();x=freeze(s,m);x["receipt"]["spent_yen"]=9000
    with self.assertRaisesRegex(LabBridgeRejected,"pipeline_receipt_modified"):
        replay_lab_settlement(x,[])
 def test_replay_freeze_tamper_rejected(self):
    s,m=prepare();x=freeze(s,m)
    x["frozen"]["frozen"]["tickets"][0]["stake_yen"]=9999
    with self.assertRaises(LabRejected):replay_lab_settlement(x,[])
 def test_skip_cannot_settle(self):
    s,m=prepare(odds=1.01);x=freeze(s,m)
    with self.assertRaisesRegex(LabBridgeRejected,"skipped_scenario"):
        replay_lab_settlement(x,[{}])
 def test_deterministic_same_input(self):
    s,m=prepare();self.assertEqual(freeze(s,m),freeze(s,m))
if __name__=="__main__":unittest.main()
