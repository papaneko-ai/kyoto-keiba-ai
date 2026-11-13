"""R07 independent 24-case fixed LAB acceptance suite."""
import copy,unittest
import test_p3_offline_model_tournament as fixture
from diagnostics.p3_offline_model_tournament import CANDIDATES,TournamentRejected
from diagnostics.p3_r07_calibration_uncertainty_acceptance import audit_calibration_uncertainty,wilson_interval

class R07UncertaintyAcceptance(unittest.TestCase):
    def setUp(self):
        self.train=[fixture.fixture(i) for i in range(1,7)]
        self.hold=[fixture.fixture(i) for i in range(10,50)]
    def result(self,**kw):
        return audit_calibration_uncertainty(self.train,self.hold,plan_locked_utc=fixture.utc(30),**kw)
    def reject(self,message,**kw):
        with self.assertRaisesRegex(TournamentRejected,message):self.result(**kw)
    def test_sufficient_disjoint_unused_holdout(self):
        r=self.result()
        self.assertEqual((r["train_races"],r["unused_holdout_races"]),(6,40))
        self.assertEqual(len(r["models"]),len(CANDIDATES))
        self.assertTrue(r["all_models_bins_adequate"])
    def test_all_five_proper_score_delta_fields(self):
        for m in self.result()["models"].values():
            self.assertEqual(m["proper_scores"]["paired_races"],40)
            self.assertIn("delta_log_loss_vs_pl",m)
            self.assertIn("delta_brier_vs_pl",m)
    def test_each_bin_count_reconciles(self):
        for m in self.result()["models"].values():
            self.assertEqual(sum(x["n"] for x in m["intervals"]),40)
    def test_empty_bins_are_not_fake_zero_hit_confidence(self):
        for m in self.result()["models"].values():
            for b in m["intervals"]:
                if b["n"]==0:
                    self.assertIsNone(b["frequency_interval_95"])
                    self.assertIsNone(b["covered"])
    def test_wilson_no_hits_has_positive_upper(self):
        a,b=wilson_interval(0,40);self.assertEqual(a,0.);self.assertGreater(b,0.)
    def test_wilson_all_hits_has_lower_below_one(self):
        a,b=wilson_interval(40,40);self.assertLess(a,1.);self.assertEqual(b,1.)
    def test_wilson_half_hits_contains_half(self):
        a,b=wilson_interval(20,40);self.assertLess(a,.5);self.assertGreater(b,.5)
    def test_reproducible_receipt(self):self.assertEqual(self.result(),self.result())
    def test_holdout_under_thirty_rejected(self):
        self.hold=self.hold[:29];self.reject("insufficient_unused_holdout")
    def test_min_holdout_below_policy_rejected(self):self.reject("minimum_sample_policy",min_holdout=29)
    def test_min_occupied_bin_below_policy_rejected(self):self.reject("minimum_sample_policy",min_occupied_bin=9)
    def test_boolean_min_occupied_bin_rejected(self):self.reject("minimum_sample_policy",min_occupied_bin=True)
    def test_boolean_min_holdout_rejected(self):self.reject("minimum_sample_policy",min_holdout=True)
    def test_invalid_bins_rejected(self):self.reject("calibration_bins_invalid",bins=1)
    def test_bins_twenty_flags_thin_cells(self):
        self.assertFalse(self.result(bins=20,min_occupied_bin=41)["all_models_bins_adequate"])
    def test_duplicate_race_refused(self):
        self.hold[1]["snapshot"]["race_id"]=self.hold[0]["snapshot"]["race_id"];self.reject("leakage")
    def test_overlapping_train_and_holdout_refused(self):
        self.hold[0]=copy.deepcopy(self.train[0]);self.reject("leakage")
    def test_train_result_after_lock_refused(self):
        self.train[-1]["outcome_utc"]=fixture.utc(31);self.reject("leakage")
    def test_holdout_feature_before_plan_lock_refused(self):
        self.hold[0]["snapshot"]["feature_cutoff_utc"]=fixture.utc(29);self.reject("leakage")
    def test_future_feature_refused(self):
        self.hold[0]["snapshot"]["feature_cutoff_utc"]=self.hold[0]["snapshot"]["race_start_utc"]
        self.reject("future_features")
    def test_outcome_added_to_snapshot_refused(self):
        self.hold[0]["snapshot"]["finish_order"]=[1,2];self.reject("snapshot_schema")
    def test_nonlab_source_refused(self):
        self.hold[0]["snapshot"]["source_scope"]="JRA_REAL";self.reject("nonlab_source")
    def test_no_live_or_auto_selection(self):
        r=self.result()
        for key in ("jra_authenticity_verified","real_world_calibration_certified",
            "pairwise_model_improvement_certified","model_auto_promotion_allowed",
            "live_paper_trade_authorized","real_betting_authorized"):
            self.assertFalse(r[key])
    def test_wilson_invalid_counts_rejected(self):
        for h,n in ((-1,10),(11,10),(1,0),(True,10),(1,True)):
            with self.assertRaises(TournamentRejected):wilson_interval(h,n)
if __name__=="__main__":unittest.main()
