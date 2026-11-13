"""P3 truly untouched chronological model-selection LAB tests."""
import copy,unittest
from diagnostics.p3_three_window_selection_lab import three_window_selection
from diagnostics.p3_offline_model_tournament import TournamentRejected
from test_p3_offline_model_tournament import fixture,utc

class ThreeWindowTests(unittest.TestCase):
 def setUp(self):
    self.train=[fixture(i) for i in range(1,7)]
    self.valid=[fixture(i) for i in range(10,16)]
    self.final=[fixture(i) for i in range(20,30)]
 def audit(self):
    return three_window_selection(self.train,self.valid,self.final,
        selection_locked_utc=utc(30),final_locked_utc=utc(70))
 def test_select_validation_then_untouched_evaluation(self):
    r=self.audit()
    self.assertEqual(r["selection_count"],5)
    self.assertEqual(r["training_count"],6)
    self.assertEqual(r["validation_count"],6)
    self.assertEqual(r["untouched_count"],10)
    self.assertEqual(set(r["final_metrics"]),{"PL_BASE",r["selected_on_validation"]})
    self.assertFalse(r["live_model_certified"])
 def test_deterministic(self):
    self.assertEqual(self.audit(),self.audit())
 def test_final_labels_cannot_change_selected_model(self):
    a=self.audit()
    for row in self.final:row["winning_pair"]=[3,4]
    b=self.audit()
    self.assertEqual(a["selected_on_validation"],b["selected_on_validation"])
    self.assertNotEqual(a["untouched_input_sha256"],b["untouched_input_sha256"])
 def test_duplicate_train_validation_identity_refused(self):
    self.valid[0]["snapshot"]["race_id"]=self.train[0]["snapshot"]["race_id"]
    with self.assertRaisesRegex(TournamentRejected,"overlap_or_leakage"):self.audit()
 def test_duplicate_validation_final_identity_refused(self):
    self.final[0]["snapshot"]["race_id"]=self.valid[0]["snapshot"]["race_id"]
    with self.assertRaisesRegex(TournamentRejected,"overlap_or_leakage"):self.audit()
 def test_future_validation_result_refused(self):
    self.valid[-1]["outcome_utc"]=utc(71)
    with self.assertRaisesRegex(TournamentRejected,"overlap_or_leakage"):self.audit()
 def test_training_result_after_selection_lock_refused(self):
    self.train[-1]["outcome_utc"]=utc(35)
    with self.assertRaisesRegex(TournamentRejected,"overlap_or_leakage"):self.audit()
 def test_preselection_validation_cutoff_refused(self):
    self.valid[0]["snapshot"]["feature_cutoff_utc"]=utc(30)
    with self.assertRaisesRegex(TournamentRejected,"overlap_or_leakage"):self.audit()
 def test_postrace_freeze_refused(self):
    self.final[0]["forecast_frozen_utc"]=self.final[0]["outcome_utc"]
    with self.assertRaisesRegex(TournamentRejected,"overlap_or_leakage"):self.audit()
 def test_future_feature_column_refused(self):
    self.final[0]["snapshot"]["result"]="WIN"
    with self.assertRaisesRegex(TournamentRejected,"snapshot_schema"):self.audit()
 def test_short_final_refused(self):
    self.final.pop()
    with self.assertRaisesRegex(TournamentRejected,"minimum_sample"):self.audit()
 def test_reversed_locks_refused(self):
    with self.assertRaisesRegex(TournamentRejected,"incorrect_lock_order"):
        three_window_selection(self.train,self.valid,self.final,
            selection_locked_utc=utc(70),final_locked_utc=utc(30))
 def test_real_source_claim_refused(self):
    self.valid[0]["snapshot"]["source_scope"]="JRA_LIVE"
    with self.assertRaisesRegex(TournamentRejected,"nonlab"):self.audit()
if __name__=="__main__":unittest.main()
