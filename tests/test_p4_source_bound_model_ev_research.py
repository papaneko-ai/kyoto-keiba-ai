"""P4-02 anchored P1-original / P3 synthetic prediction / P4 risk integration."""
import copy
import unittest
from diagnostics.jra_p1_offline_handoff import export_bundle
from diagnostics.p4_source_bound_model_ev_research import (
    compare_source_market_to_frozen_model,OriginalEvRejected)
from diagnostics.p4_temporal_market_controls import TemporalMarketRejected
from diagnostics.p1_three_original_dual_intake import ThreeOriginalRejected
from test_p1_three_original_content_binding import StrictThreeOriginalContentTests,NOW

class SourceBoundMarketResearch(unittest.TestCase):
    def setUp(self):
        self.fixture=StrictThreeOriginalContentTests(methodName="test_all_three_originals_match")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.model={"provenance":"LAB_SYNTHETIC_ONLY",
            "race_date":"2026-11-14","race_number":1,"venue":"京都",
            "frozen_utc":"2026-11-13T04:00:00Z",
            "cutoff_utc":"2026-11-14T04:50:00Z",
            "strengths":{"1":2.0,"2":1.0},
            "source_feature_sha256":"a"*64,"model_version":"LAB-CANDIDATE-v1"}
    def args(self,**kw):
        d={"bundle":export_bundle(self.fixture.manifest,self.fixture.root,observed_utc=NOW),
           "snapshot":copy.deepcopy(self.fixture.snapshot),
           "observed_utc":NOW,"channel":"PC","frozen_model":copy.deepcopy(self.model)}
        d.update(kw)
        return d
    def audit(self,**kw):return compare_source_market_to_frozen_model(**self.args(**kw))
    def test_both_markets_original_bound_same_model_comparison(self):
        a=self.audit()
        self.assertEqual(a["markets"]["QUINELLA"]["full_pair_count"],1)
        self.assertEqual(a["markets"]["BRACKET"]["full_pair_count"],1)
        self.assertTrue(a["full_model_probabilities_sum_to_one"])
        self.assertEqual(a,self.audit())
        self.assertFalse(a["real_race_prediction_ready"])
        self.assertFalse(a["source_official_origin_authenticated"])
        self.assertFalse(a["model_externally_calibrated"])
        self.assertEqual(a["real_paper_trades_written"],0)
    def test_change_model_strengths_changes_receipt(self):
        alt=copy.deepcopy(self.model);alt["strengths"]={"1":4.0,"2":1.0}
        self.assertNotEqual(self.audit()["comparison_sha256"],
                            self.audit(frozen_model=alt)["comparison_sha256"])
    def test_roster_change_without_new_model_rejected(self):
        alt=copy.deepcopy(self.model);alt["strengths"]={"1":2.0,"3":1.0}
        with self.assertRaisesRegex(OriginalEvRejected,"model_roster_or_strength_invalid"):
            self.audit(frozen_model=alt)
    def test_future_model_freeze_rejected(self):
        alt=copy.deepcopy(self.model);alt["frozen_utc"]="2026-11-14T06:00:00Z"
        with self.assertRaisesRegex(OriginalEvRejected,"model_freeze_or_cutoff_invalid"):
            self.audit(frozen_model=alt)
    def test_alleged_official_model_never_promoted(self):
        alt=copy.deepcopy(self.model);alt["provenance"]="OFFICIAL_LIVE"
        with self.assertRaisesRegex(OriginalEvRejected,"model_race_or_provenance_mismatch"):
            self.audit(frozen_model=alt)
    def test_quinella_odds_tampering_rejected(self):
        s=copy.deepcopy(self.fixture.snapshot);s["odds"][0]["decimal"]=99
        with self.assertRaises(ThreeOriginalRejected):self.audit(snapshot=s)
    def test_bracket_odds_tampering_rejected(self):
        s=copy.deepcopy(self.fixture.snapshot);s["bracket_odds"][0]["decimal"]=99
        with self.assertRaises(ThreeOriginalRejected):self.audit(snapshot=s)
    def test_market_stale_rejected(self):
        with self.assertRaisesRegex(TemporalMarketRejected,"market_freshness_rejected"):
            self.audit(max_age_seconds=120)
    def test_missing_bracket_quote_rejected(self):
        s=copy.deepcopy(self.fixture.snapshot);s["bracket_odds"]=[]
        with self.assertRaises(ThreeOriginalRejected):self.audit(snapshot=s)
    def test_market_sale_suspension_rejected(self):
        s=copy.deepcopy(self.fixture.snapshot);s["market_states"]["bracket"]["sales"]="SUSPENDED"
        with self.assertRaises(ThreeOriginalRejected):self.audit(snapshot=s)
    def test_bad_prediction_before_race_guard_rejected(self):
        alt=copy.deepcopy(self.model);alt["cutoff_utc"]="2026-11-13T04:00:00Z"
        with self.assertRaises(OriginalEvRejected):self.audit(frozen_model=alt)
    def test_nonfinite_model_strength_rejected(self):
        alt=copy.deepcopy(self.model);alt["strengths"]["2"]=float("nan")
        with self.assertRaisesRegex(OriginalEvRejected,"model_roster_or_strength_invalid"):
            self.audit(frozen_model=alt)
    def test_invalid_stress_bound_rejected(self):
        with self.assertRaises(ValueError):
            self.audit(probability_error_bound=1.5)
    def test_original_bundle_corrupt_rejected(self):
        with self.assertRaises(ValueError):
            self.audit(bundle=b"corrupt")
    def test_real_betting_never_enabled_even_when_ev_positive(self):
        x=self.audit(probability_error_bound=0.0,odds_drift_fraction=0.0)
        self.assertGreater(x["markets"]["QUINELLA"]["research_model_expected_net"][0]["expected_net_per_unit"],0)
        self.assertFalse(x["actual_purchase_authorized"])
        self.assertEqual(x["network_requests"],0)
if __name__=="__main__":unittest.main()
