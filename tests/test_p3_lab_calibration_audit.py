"""ALG07 calibration audit: safety, reliability, chronological holdout tests."""
import copy, unittest
from diagnostics.p3_lab_calibration_audit import audit_calibration
from diagnostics.p3_offline_model_tournament import TournamentRejected,CANDIDATES
from test_p3_offline_model_tournament import fixture,utc

class CalibrationTests(unittest.TestCase):
 def setUp(self):
    self.training=[fixture(i) for i in range(1,7)]
    self.holdout=[fixture(i) for i in range(10,20)]
 def audit(self,**kwargs):
    return audit_calibration(self.training,self.holdout,
       plan_locked_utc=utc(30),**kwargs)
 def test_all_five_models_calibration_and_proper_scores(self):
    r=self.audit()
    self.assertEqual(set(r["calibration"]),set(CANDIDATES))
    self.assertEqual(r["fixed_hypothesis_count"],5)
    for model,data in r["calibration"].items():
        self.assertEqual(sum(b["count"] for b in data["bins"]),10)
        self.assertEqual(len(data["race_receipts"]),10)
        self.assertGreaterEqual(data["top_pair_ece"],0)
        self.assertLessEqual(data["top_pair_ece"],1)
        self.assertEqual(r["paired_comparison"][model]["paired_races"],10)
 def test_stable_replay_same_evidence(self):
    self.assertEqual(self.audit(),self.audit())
 def test_no_live_promotion_or_holdout_selection(self):
    r=self.audit()
    self.assertFalse(r["holdout_based_model_selection_authorized"])
    self.assertFalse(r["real_bet_authorized"])
    self.assertFalse(r["calibration_certified"])
 def test_bin_counts_preserved_with_twenty_bins(self):
    r=self.audit(bins=20)
    self.assertEqual(sum(x["count"] for x in r["calibration"]["PL_BASE"]["bins"]),10)
 def test_empty_bins_not_fake_zero_frequency(self):
    r=self.audit()
    self.assertTrue(any(x["empirical_frequency"] is None for x in r["calibration"]["PL_BASE"]["bins"]))
 def test_bin_one_invalid(self):
    with self.assertRaisesRegex(TournamentRejected,"calibration_bins_invalid"):
        self.audit(bins=1)
 def test_boolean_bins_invalid(self):
    with self.assertRaises(TournamentRejected):self.audit(bins=True)
 def test_holdout_less_than_minimum(self):
    with self.assertRaisesRegex(TournamentRejected,"calibration_holdout_too_short"):
        self.audit(min_holdout=11)
 def test_holdout_reuse_training_race_fails(self):
    self.holdout[0]["snapshot"]["race_id"]=self.training[0]["snapshot"]["race_id"]
    with self.assertRaisesRegex(TournamentRejected,"leakage"):
        self.audit()
 def test_future_outcome_in_features_fails(self):
    self.holdout[0]["snapshot"]["winning_pair"]=[1,2]
    with self.assertRaisesRegex(TournamentRejected,"snapshot_schema"):
        self.audit()
 def test_late_frozen_prediction_fails(self):
    self.holdout[0]["forecast_frozen_utc"]=self.holdout[0]["outcome_utc"]
    with self.assertRaisesRegex(TournamentRejected,"leakage"):
        self.audit()
 def test_training_result_after_plan_lock_fails(self):
    self.training[-1]["outcome_utc"]=utc(31)
    with self.assertRaisesRegex(TournamentRejected,"leakage"):
        self.audit()
if __name__=="__main__":unittest.main()
