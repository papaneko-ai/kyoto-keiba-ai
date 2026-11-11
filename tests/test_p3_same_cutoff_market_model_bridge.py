"""P3 same-source/cutoff comparator: tested without fake real-data claims."""
import copy
import unittest
from diagnostics.p3_same_cutoff_market_model_bridge import (
    compare_two_frozen_models_same_market, PairedMarketRejected)
from test_p4_source_bound_model_ev_research import SourceBoundMarketResearch
from diagnostics.p1_three_original_dual_intake import ThreeOriginalRejected


class PairedSameMarketTests(unittest.TestCase):
    def setUp(self):
        self.fx=SourceBoundMarketResearch(
            methodName="test_both_markets_original_bound_same_model_comparison")
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.args=self.fx.args()
        self.baseline=copy.deepcopy(self.args["frozen_model"])
        self.candidate=copy.deepcopy(self.baseline)
        self.candidate["model_version"]="LAB-CANDIDATE-v2"
        self.candidate["strengths"]={"1":4.0,"2":1.0}

    def compare(self,**overrides):
        arg={k:v for k,v in self.args.items() if k!="frozen_model"}
        arg.update({"baseline":copy.deepcopy(self.baseline),
                    "candidate":copy.deepcopy(self.candidate),
                    "common_feature_sha256":"a"*64})
        arg.update(overrides)
        return compare_two_frozen_models_same_market(**arg)

    def test_same_snapshot_both_markets_deterministic(self):
        r=self.compare()
        self.assertEqual(r,self.compare())
        self.assertEqual(set(r["markets"]),{"QUINELLA","BRACKET"})
        self.assertEqual(r["markets"]["QUINELLA"]["pair_count"],1)
        self.assertEqual(r["markets"]["BRACKET"]["pair_count"],1)
        self.assertNotEqual(r["baseline_model_sha256"],r["candidate_model_sha256"])
        self.assertNotEqual(r["baseline_p4_receipt_sha256"],
                            r["candidate_p4_receipt_sha256"])
        self.assertTrue(r["paired_prices_and_cutoff_verified_from_supplied_bytes"])
        self.assertFalse(r["independently_authenticated_jra_origin"])
        self.assertFalse(r["unused_real_race_outcomes_evaluated"])
        self.assertFalse(r["actual_released_model_compared"])
        self.assertFalse(r["actual_purchase_authorized"])
        self.assertEqual(r["network_requests"],0)

    def test_reverse_models_reverses_signed_difference(self):
        a=self.compare()
        b=self.compare(baseline=self.candidate,candidate=self.baseline)
        for market in ("QUINELLA","BRACKET"):
            x=a["markets"][market]["pairwise_same_market_comparison"][0]
            y=b["markets"][market]["pairwise_same_market_comparison"][0]
            self.assertAlmostEqual(x["candidate_minus_baseline_ev_per_unit"],
                                   -y["candidate_minus_baseline_ev_per_unit"])
            self.assertAlmostEqual(x["candidate_minus_baseline_stressed"],
                                   -y["candidate_minus_baseline_stressed"])

    def test_same_model_versions_rejected(self):
        m=copy.deepcopy(self.candidate)
        m["model_version"]=self.baseline["model_version"]
        with self.assertRaisesRegex(PairedMarketRejected,"distinct_model_versions_required"):
            self.compare(candidate=m)

    def test_different_features_rejected_before_ev(self):
        m=copy.deepcopy(self.candidate)
        m["source_feature_sha256"]="b"*64
        with self.assertRaisesRegex(PairedMarketRejected,"features_differ_between_models"):
            self.compare(candidate=m)

    def test_bad_feature_anchor_rejected(self):
        with self.assertRaisesRegex(PairedMarketRejected,"external_feature_anchor_format_invalid"):
            self.compare(common_feature_sha256="not-a-sha")

    def test_future_model_freeze_rejected(self):
        m=copy.deepcopy(self.candidate)
        m["frozen_utc"]="2026-11-14T05:00:00Z"
        with self.assertRaisesRegex(PairedMarketRejected,"model_freeze_after_observation"):
            self.compare(candidate=m)

    def test_changed_quinella_price_rejected(self):
        s=copy.deepcopy(self.args["snapshot"])
        s["odds"][0]["decimal"]=999
        with self.assertRaises(ThreeOriginalRejected):
            self.compare(snapshot=s)

    def test_changed_bracket_price_rejected(self):
        s=copy.deepcopy(self.args["snapshot"])
        s["bracket_odds"][0]["decimal"]=999
        with self.assertRaises(ThreeOriginalRejected):
            self.compare(snapshot=s)

    def test_different_model_runner_roster_rejected(self):
        m=copy.deepcopy(self.candidate)
        m["strengths"]={"1":4.0,"3":1.0}
        with self.assertRaises(ValueError):
            self.compare(candidate=m)

    def test_candidate_claim_of_official_provenance_rejected(self):
        m=copy.deepcopy(self.candidate)
        m["provenance"]="OFFICIAL"
        with self.assertRaises(ValueError):
            self.compare(candidate=m)

    def test_observation_after_cutoff_rejected(self):
        with self.assertRaises(ValueError):
            self.compare(observed_utc="2026-11-14T05:05:00Z")

    def test_incorrect_race_metadata_rejected(self):
        m=copy.deepcopy(self.candidate)
        m["race_number"]=2
        with self.assertRaises(ValueError):
            self.compare(candidate=m)

    def test_model_only_change_preserves_source_audit(self):
        a=self.compare()
        m=copy.deepcopy(self.candidate)
        m["strengths"]={"1":9.0,"2":1.0}
        b=self.compare(candidate=m)
        for k in ("source_bundle_sha256","source_snapshot_sha256",
                  "market_audit_sha256"):
            self.assertEqual(a[k],b[k])
        self.assertNotEqual(a["comparison_sha256"],b["comparison_sha256"])


if __name__=="__main__":
    unittest.main()
