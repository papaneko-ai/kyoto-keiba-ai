"""Integrated P2 discovery -> P3 proper scores -> P5 no-odds skip."""
import copy,hashlib,unittest
from datetime import datetime,timedelta,timezone
from diagnostics.p2_p3_p5_offline_feature_bridge import (
    frozen_discovery,feature_forecast_snapshot,evaluate_feature_bridge,FeatureBridgeRejected)
from diagnostics.p3_offline_model_tournament import predict,TournamentRejected

def stamp(hours):
    return (datetime(2026,9,1,tzinfo=timezone.utc)+timedelta(hours=hours)).isoformat().replace("+00:00","Z")
FEATURES=("course_fit","distance_fit","pace_fit","recent_form")
def snapshot(i):
    return {"race_id":f"LAB-FEATURE-{i:03d}",
        "feature_source_sha256":hashlib.sha256(str(i).encode()).hexdigest(),
        "feature_cutoff_utc":stamp(i*4),"race_start_utc":stamp(i*4+2),
        "source_scope":"LAB_OFFLINE_ONLY",
        "runners":[{"number":n,"frame":1 if n<=2 else n-1,
          "features":{name:round(.12+n*.11+(i%3)*.015,3) for name in FEATURES}}
                    for n in range(1,5)]}
def labeled(i):
    return {"snapshot":snapshot(i),"forecast_frozen_utc":stamp(i*4+1),
        "outcome_utc":stamp(i*4+3),"winning_pair":[3,4]}
def p2_source():
    out=[]
    for i in range(1,13):
        s=snapshot(i)
        out.append({"race_id":s["race_id"],"cutoff_utc":s["feature_cutoff_utc"],
            "pre_result_frozen":True,
            "horses":[{"number":h["number"],"features":h["features"]} for h in s["runners"]],
            "winner":4})
    return out
class FeatureBridgeTests(unittest.TestCase):
 def setUp(self):
    self.discovery=p2_source()
    self.plan=frozen_discovery(self.discovery,train_count=4,selection_count=2)
    self.training=[labeled(i) for i in range(20,26)]
    self.holdout=[labeled(i) for i in range(30,40)]
 def runbridge(self):
    return evaluate_feature_bridge(self.plan,self.training,self.holdout,
        plan_locked_utc=stamp(109),daily_budget_yen=10000)
 def test_discovery_freezes_feature_selection(self):
    self.assertEqual(len(self.plan["selected_keys"]),2)
    self.assertFalse(self.plan["production_eligible"])
 def test_bridge_runs_all_five_and_abstains(self):
    r=self.runbridge()
    self.assertEqual(len(r["candidate_family"]),5)
    self.assertEqual(r["evaluation_count"],10)
    self.assertEqual(r["virtual_exposure_yen"],0)
    self.assertEqual(r["unspent_yen"],10000)
    self.assertFalse(r["official_settlement_performed"])
 def test_derived_prediction_both_markets(self):
    p=predict(feature_forecast_snapshot(self.plan,snapshot(30)),"PL_BASE")
    self.assertAlmostEqual(sum(x["probability"] for x in p["quinella"]),1)
    self.assertAlmostEqual(sum(x["probability"] for x in p["bracket"]),1)
    self.assertTrue(any(x["pair"]==[1,1] for x in p["bracket"]))
 def test_determinism(self):
    self.assertEqual(self.runbridge(),self.runbridge())
 def test_plan_hash_mutation_refused(self):
    self.plan["selected_keys"]=[["pace_fit"]]
    with self.assertRaisesRegex(FeatureBridgeRejected,"feature_plan_tampered"):
        self.runbridge()
 def test_future_result_as_feature_refused(self):
    self.holdout[0]["snapshot"]["runners"][0]["features"]["winning_pair"]=1
    with self.assertRaisesRegex(FeatureBridgeRejected,"feature_missing_or_future_column"):
        self.runbridge()
 def test_missing_feature_refused(self):
    del self.holdout[0]["snapshot"]["runners"][0]["features"]["distance_fit"]
    with self.assertRaises(FeatureBridgeRejected):self.runbridge()
 def test_future_feature_cutoff_refused(self):
    self.holdout[0]["snapshot"]["feature_cutoff_utc"]=self.holdout[0]["snapshot"]["race_start_utc"]
    with self.assertRaisesRegex(FeatureBridgeRejected,"feature_time_invalid"):self.runbridge()
 def test_duplicate_holdout_refused(self):
    self.holdout[1]["snapshot"]["race_id"]=self.holdout[0]["snapshot"]["race_id"]
    with self.assertRaisesRegex(TournamentRejected,"leakage"):self.runbridge()
 def test_outcome_before_race_refused(self):
    self.holdout[0]["outcome_utc"]=stamp(120)
    with self.assertRaisesRegex(TournamentRejected,"leakage"):self.runbridge()
 def test_train_and_holdout_reuse_refused(self):
    self.holdout[0]["snapshot"]["race_id"]=self.training[0]["snapshot"]["race_id"]
    with self.assertRaisesRegex(TournamentRejected,"leakage"):self.runbridge()
 def test_postrace_freeze_refused(self):
    self.holdout[0]["forecast_frozen_utc"]=self.holdout[0]["outcome_utc"]
    with self.assertRaisesRegex(TournamentRejected,"leakage"):self.runbridge()
 def test_invalid_budget_refused(self):
    with self.assertRaises(FeatureBridgeRejected):
        evaluate_feature_bridge(self.plan,self.training,self.holdout,
            plan_locked_utc=stamp(109),daily_budget_yen=105)
 def test_p2_selected_validation_cannot_be_in_training(self):
    self.training[0]["snapshot"]["race_id"]=self.plan["validation_race_ids"][0]
    with self.assertRaisesRegex(FeatureBridgeRejected,"training_or_validation_reuse"):
        self.runbridge()
 def test_no_claim_of_official_data(self):
    self.assertFalse(self.runbridge()["independent_jra_evidence"])
if __name__=="__main__":unittest.main()
