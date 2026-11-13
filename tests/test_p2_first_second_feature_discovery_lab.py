"""LAB first/second/unplaced classification and chronological leakage tests."""
import copy, unittest
from diagnostics.p2_first_second_feature_discovery_lab import (
    discover_first_second,PlaceDiscoveryRejected)
from test_p2_p3_p5_offline_feature_bridge import snapshot,stamp

def row(i):
    return {"snapshot":snapshot(i),"forecast_frozen_utc":stamp(i*4+1),
        "outcome_utc":stamp(i*4+3),"first_second":[4,3]}
class FirstSecondTests(unittest.TestCase):
 def setUp(self):
    self.rows=[row(i) for i in range(1,17)]
 def audit(self):
    return discover_first_second(self.rows,train_count=6,selection_count=3)
 def test_three_disjoint_periods_and_first_second_unplaced(self):
    r=self.audit()
    self.assertEqual(len(r["selected"]),3)
    self.assertEqual(r["feature_family_size"],10)
    self.assertEqual(len(r["race_ids"]["training"]),6)
    self.assertEqual(len(r["race_ids"]["validation"]),5)
    self.assertEqual(len(r["race_ids"]["holdout"]),5)
    self.assertEqual(r["selected"][0]["training"]["first_samples"],6)
    self.assertEqual(r["selected"][0]["training"]["second_samples"],6)
    self.assertEqual(r["selected"][0]["training"]["unplaced_samples"],12)
 def test_replay_deterministic(self):
    self.assertEqual(self.audit(),self.audit())
 def test_rejects_duplicate_race(self):
    self.rows[2]["snapshot"]["race_id"]=self.rows[1]["snapshot"]["race_id"]
    with self.assertRaisesRegex(PlaceDiscoveryRejected,"duplicate"):self.audit()
 def test_refuses_future_outcome_column(self):
    self.rows[1]["snapshot"]["runners"][0]["features"]["result"]=1
    with self.assertRaisesRegex(PlaceDiscoveryRejected,"feature_snapshot_invalid"):self.audit()
 def test_refuses_postrace_freeze(self):
    self.rows[1]["forecast_frozen_utc"]=self.rows[1]["outcome_utc"]
    with self.assertRaisesRegex(PlaceDiscoveryRejected,"outcome_or_cutoff_leakage"):self.audit()
 def test_refuses_tampered_order(self):
    self.rows[1],self.rows[2]=self.rows[2],self.rows[1]
    with self.assertRaisesRegex(PlaceDiscoveryRejected,"outcome_or_cutoff_leakage"):self.audit()
 def test_refuses_duplicate_first_second(self):
    self.rows[1]["first_second"]=[4,4]
    with self.assertRaisesRegex(PlaceDiscoveryRejected,"first_second_invalid"):self.audit()
 def test_refuses_missing_second(self):
    self.rows[1]["first_second"]=[4,5]
    with self.assertRaisesRegex(PlaceDiscoveryRejected,"first_second_invalid"):self.audit()
 def test_refuses_insufficient_windows(self):
    with self.assertRaisesRegex(PlaceDiscoveryRejected,"three_windows_required"):
        discover_first_second(self.rows,train_count=12)
 def test_refuses_short_sample(self):
    with self.assertRaisesRegex(PlaceDiscoveryRejected,"at_least_twelve_races_required"):
        discover_first_second(self.rows[:11],train_count=4)
 def test_refuses_nonlab_source(self):
    self.rows[1]["snapshot"]["source_scope"]="JRA_LIVE"
    with self.assertRaises(PlaceDiscoveryRejected):self.audit()
 def test_no_live_or_holdout_selection_claim(self):
    r=self.audit()
    self.assertFalse(r["holdout_selection_authorized"])
    self.assertFalse(r["real_JRA_evidence_authenticated"])
    self.assertFalse(r["real_bet_authorized"])
if __name__=="__main__":unittest.main()
