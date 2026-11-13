"""Offline P3 candidate family destructive and temporal contract tests."""
import copy,hashlib,unittest
from datetime import datetime,timedelta,timezone
from diagnostics.p3_offline_model_tournament import (
    predict,audit_chronological_holdout,CANDIDATES,TournamentRejected)
def utc(h):
    return (datetime(2026,10,1,tzinfo=timezone.utc)+timedelta(hours=h)).isoformat().replace("+00:00","Z")
def fixture(i):
    s={"race_id":f"LAB-TOURNAMENT-{i:03d}",
       "source_scope":"LAB_OFFLINE_ONLY",
       "feature_source_sha256":hashlib.sha256(str(i).encode()).hexdigest(),
       "feature_cutoff_utc":utc(i*4),"race_start_utc":utc(i*4+2),
       "runners":[{"number":1,"frame":1,"prior_strength":4.0},
                  {"number":2,"frame":1,"prior_strength":3.0},
                  {"number":3,"frame":2,"prior_strength":2.0},
                  {"number":4,"frame":3,"prior_strength":1.0}]}
    return {"snapshot":s,"forecast_frozen_utc":utc(i*4+1),
            "outcome_utc":utc(i*4+3),"winning_pair":[1,2]}
class TournamentTests(unittest.TestCase):
 def setUp(self):
    self.train=[fixture(i) for i in range(1,7)]
    self.hold=[fixture(i) for i in range(10,20)]
 def audit(self):
    return audit_chronological_holdout(self.train,self.hold,plan_locked_utc=utc(30))
 def test_five_candidates_both_markets_same_frame(self):
    for model in CANDIDATES:
        p=predict(fixture(10)["snapshot"],model)
        self.assertAlmostEqual(sum(x["probability"] for x in p["quinella"]),1)
        self.assertAlmostEqual(sum(x["probability"] for x in p["bracket"]),1)
        self.assertTrue(any(x["pair"]==[1,1] for x in p["bracket"]))
        self.assertFalse(p["production_eligible"])
 def test_chronological_holdout_deterministic(self):
    self.assertEqual(self.audit(),self.audit())
    self.assertEqual(self.audit()["comparison_count"],5)
    self.assertFalse(self.audit()["independent_real_JRA_validation"])
 def test_future_feature_refused(self):
    s=fixture(1)["snapshot"];s["feature_cutoff_utc"]=s["race_start_utc"]
    with self.assertRaisesRegex(TournamentRejected,"future_features"):predict(s,"PL_BASE")
 def test_result_in_features_refused(self):
    s=fixture(1)["snapshot"];s["winning_pair"]=[1,2]
    with self.assertRaisesRegex(TournamentRejected,"snapshot_schema"):predict(s,"PL_BASE")
 def test_missing_strength_refused(self):
    s=fixture(1)["snapshot"];s["runners"][2]["prior_strength"]=None
    with self.assertRaisesRegex(TournamentRejected,"runner_value"):predict(s,"PL_BASE")
 def test_nan_strength_refused(self):
    s=fixture(1)["snapshot"];s["runners"][2]["prior_strength"]=float("nan")
    with self.assertRaises(TournamentRejected):predict(s,"PL_BASE")
 def test_duplicate_runner_refused(self):
    s=fixture(1)["snapshot"];s["runners"][2]["number"]=2
    with self.assertRaises(TournamentRejected):predict(s,"PL_BASE")
 def test_training_label_after_lock_refused(self):
    self.train[-1]["outcome_utc"]=utc(34)
    with self.assertRaisesRegex(TournamentRejected,"leakage"):self.audit()
 def test_holdout_before_lock_refused(self):
    self.hold[0]["snapshot"]["feature_cutoff_utc"]=utc(30)
    with self.assertRaisesRegex(TournamentRejected,"leakage"):self.audit()
 def test_duplicate_holdout_refused(self):
    self.hold[1]["snapshot"]["race_id"]=self.hold[0]["snapshot"]["race_id"]
    with self.assertRaisesRegex(TournamentRejected,"leakage"):self.audit()
 def test_postrace_freeze_refused(self):
    self.hold[0]["forecast_frozen_utc"]=utc(43)
    with self.assertRaisesRegex(TournamentRejected,"leakage"):self.audit()
 def test_insufficient_holdout_refused(self):
    self.hold.pop()
    with self.assertRaisesRegex(TournamentRejected,"insufficient"):self.audit()
 def test_real_source_mislabel_refused(self):
    s=fixture(1)["snapshot"];s["source_scope"]="JRA_LIVE"
    with self.assertRaisesRegex(TournamentRejected,"nonlab"):predict(s,"PL_BASE")
 def test_no_betting(self):
    self.assertFalse(self.audit()["real_betting_authorized"])
if __name__=="__main__":unittest.main()
