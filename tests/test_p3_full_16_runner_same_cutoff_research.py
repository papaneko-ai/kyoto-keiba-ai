"""P3-02 fixed-rubric research acceptance: full 16-runner, 120/36 market.

Builds THREE independent synthetic HTML byte originals (not real JRA files),
binds all prices and frames via existing PC parsing and SHA chains, and
compares two frozen LAB model versions at exactly the same snapshot cutoff.

This covers the missing full-sized model-vs-market research comparison.
Even if accepted by the FIXED rubric's 'real data OR research tests' rule,
it does NOT establish a real-world JRA pre-race quote, true performance,
official data license, or operational market readiness.
"""
import copy
import hashlib
import unittest
from diagnostics.jra_p1_offline_handoff import export_bundle
from diagnostics.p3_same_cutoff_market_model_bridge import (
    compare_two_frozen_models_same_market, PairedMarketRejected)
from diagnostics.p1_three_original_dual_intake import ThreeOriginalRejected
from test_p4_source_bound_model_ev_research import SourceBoundMarketResearch
from test_p1_three_original_content_binding import market_html, NOW


class FullSizeSameMarketResearchTests(unittest.TestCase):
    def setUp(self):
        self.fx=SourceBoundMarketResearch(
            methodName="test_both_markets_original_bound_same_model_comparison")
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.runners=list(range(1,17))
        self.brackets={i:(i+1)//2 for i in self.runners}
        self.fx.fixture.snapshot["runners"]=[
            {"number":i,"horse_id":"horse%04d"%i,"name":"HORSE%02d"%i,
             "bracket":self.brackets[i],"status":"ACTIVE"}
            for i in self.runners]
        # Genuine 16-entrant PC parser shape, but synthetic HTML bytes.
        cells=[]
        for i in self.runners:
            cells.append('<tr><td class="horse"><a href="/JRADB/accessU.html?CNAME=s%02d">HORSE%02d</a></td><td class="num">%d</td><td class="waku"><img alt="枠%d"></td></tr>' %
                         (i,i,i,self.brackets[i]))
        html=('<html><body>2026年11月14日 1レース'
              '<table><tr><th class="horse"></th><th class="num"></th><th class="waku"></th></tr>'
              +''.join(cells)+'</table></body></html>').encode("cp932")
        self.fx.fixture.set_original(0,html)
        qp=[]
        for i in range(1,16):
            tokens=[str(i)]
            for j in range(i+1,17):
                tokens += [str(j),str(1.1+i+j/10)]
                qp.append({"first":i,"second":j,"decimal":float(1.1+i+j/10)})
        # Rewrite quinella HTML as 15 strictly ordered matrix tables.
        qrows=[]
        for i in range(1,16):
            cells=[str(i)]
            for j in range(i+1,17):
                cells += [str(j),"%.2f"%(1.1+i+j/10)]
            qrows.append(" ".join(cells))
        self.fx.fixture.set_original(1,market_html("馬連オッズ","umaren",qrows))
        self.fx.fixture.snapshot["odds"]=[
          {"first":i,"second":j,"decimal":float("%.2f"%(1.1+i+j/10))}
          for i in range(1,16) for j in range(i+1,17)]
        brows=[]
        for i in range(1,9):
            cells=[]
            for j in range(i,9):
                cells += [str(j),"%.2f"%(2.0+i+j/10)]
            brows.append(" ".join(cells))
        self.fx.fixture.set_original(2,market_html("枠連オッズ","waku",brows))
        self.fx.fixture.snapshot["bracket_odds"]=[
          {"first":i,"second":j,"decimal":float("%.2f"%(2.0+i+j/10))}
          for i in range(1,9) for j in range(i,9)]
        self.baseline=copy.deepcopy(self.fx.model)
        self.baseline["strengths"]={str(i):float(i+1) for i in self.runners}
        self.candidate=copy.deepcopy(self.baseline)
        self.candidate["model_version"]="LAB-FULL-16-v2"
        self.candidate["strengths"]={str(i):float(18-i) for i in self.runners}
        self.model_feature="a"*64

    def compare(self,**kwargs):
        params={
            "bundle":export_bundle(self.fx.fixture.manifest,self.fx.fixture.root,
                                  observed_utc=NOW),
            "snapshot":copy.deepcopy(self.fx.fixture.snapshot),
            "observed_utc":NOW,"channel":"PC",
            "baseline":copy.deepcopy(self.baseline),
            "candidate":copy.deepcopy(self.candidate),
            "common_feature_sha256":self.model_feature}
        params.update(kwargs)
        return compare_two_frozen_models_same_market(**params)

    def test_16_horses_full120_and36_market_comparison(self):
        a=self.compare()
        self.assertEqual(a["markets"]["QUINELLA"]["pair_count"],120)
        self.assertEqual(a["markets"]["BRACKET"]["pair_count"],36)
        self.assertEqual(len(a["markets"]["QUINELLA"]["pairwise_same_market_comparison"]),120)
        self.assertEqual(len(a["markets"]["BRACKET"]["pairwise_same_market_comparison"]),36)
        self.assertEqual(a,self.compare())
        self.assertFalse(a["independently_authenticated_jra_origin"])
        self.assertFalse(a["actual_released_model_compared"])
        self.assertFalse(a["unused_real_race_outcomes_evaluated"])
        self.assertFalse(a["real_model_promotion_authorized"])
        self.assertFalse(a["actual_purchase_authorized"])
        self.assertEqual(a["network_requests"],0)

    def test_divergent_models_produce_nonzero_changes_in_both_markets(self):
        a=self.compare()
        for market in ("QUINELLA","BRACKET"):
            changes=[x["candidate_minus_baseline_ev_per_unit"] for x in
                     a["markets"][market]["pairwise_same_market_comparison"]]
            self.assertTrue(any(abs(v)>1e-6 for v in changes))
            self.assertTrue(any(v>0 for v in changes))
            self.assertTrue(any(v<0 for v in changes))

    def test_reverse_baseline_and_candidate_reverses_all_156_differences(self):
        forward=self.compare()
        backward=self.compare(baseline=self.candidate,candidate=self.baseline)
        for market in ("QUINELLA","BRACKET"):
            x=forward["markets"][market]["pairwise_same_market_comparison"]
            y=backward["markets"][market]["pairwise_same_market_comparison"]
            self.assertEqual([z["pair"] for z in x],[z["pair"] for z in y])
            for a,b in zip(x,y):
                self.assertAlmostEqual(a["candidate_minus_baseline_ev_per_unit"],
                                       -b["candidate_minus_baseline_ev_per_unit"])
                self.assertAlmostEqual(a["candidate_minus_baseline_stressed"],
                                       -b["candidate_minus_baseline_stressed"])

    def test_both_market_prices_frozen_under_model_swaps(self):
        a=self.compare()
        alt=copy.deepcopy(self.candidate)
        alt["strengths"]={str(i):1.0 for i in self.runners}
        b=self.compare(candidate=alt)
        self.assertEqual(a["source_bundle_sha256"],b["source_bundle_sha256"])
        self.assertEqual(a["source_snapshot_sha256"],b["source_snapshot_sha256"])
        self.assertEqual(a["market_audit_sha256"],b["market_audit_sha256"])
        self.assertNotEqual(a["comparison_sha256"],b["comparison_sha256"])

    def test_quinella_original_byte_tamper_rejected(self):
        changed=copy.deepcopy(self.fx.fixture.snapshot)
        changed["odds"][0]["decimal"]+=0.11
        with self.assertRaises(ThreeOriginalRejected):
            self.compare(snapshot=changed)

    def test_bracket_same_frame_original_tamper_rejected(self):
        changed=copy.deepcopy(self.fx.fixture.snapshot)
        same=next(row for row in changed["bracket_odds"] if row["first"]==row["second"])
        same["decimal"]+=0.3
        with self.assertRaises(ThreeOriginalRejected):
            self.compare(snapshot=changed)

    def test_15_out_of_16_runner_strengths_rejected(self):
        candidate=copy.deepcopy(self.candidate)
        candidate["strengths"].pop("16")
        with self.assertRaises(ValueError):
            self.compare(candidate=candidate)

    def test_future_freeze_is_a_hard_stop(self):
        candidate=copy.deepcopy(self.candidate)
        candidate["frozen_utc"]="2026-11-14T05:00:00Z"
        with self.assertRaisesRegex(PairedMarketRejected,"model_freeze_after_observation"):
            self.compare(candidate=candidate)

    def test_feature_set_mismatch_is_a_hard_stop(self):
        candidate=copy.deepcopy(self.candidate)
        candidate["source_feature_sha256"]="b"*64
        with self.assertRaisesRegex(PairedMarketRejected,"features_differ_between_models"):
            self.compare(candidate=candidate)

    def test_duplicate_model_version_rejected(self):
        candidate=copy.deepcopy(self.candidate)
        candidate["model_version"]=self.baseline["model_version"]
        with self.assertRaisesRegex(PairedMarketRejected,"distinct_model_versions_required"):
            self.compare(candidate=candidate)

    def test_market_not_open_rejected(self):
        s=copy.deepcopy(self.fx.fixture.snapshot)
        s["market_states"]["bracket"]["sales"]="SUSPENDED"
        with self.assertRaises(ValueError):
            self.compare(snapshot=s)

    def test_historical_final_odds_blocked(self):
        original=(self.fx.fixture.root/"quinella.html").read_bytes()
        self.fx.fixture.set_original(1,original.replace(
            b"<body>",b"<body>"+"最終オッズ".encode("cp932")))
        with self.assertRaises(ThreeOriginalRejected):
            self.compare()

    def test_no_real_predictions_or_paid_orders(self):
        a=self.compare()
        for k in ("independently_authenticated_jra_origin",
                  "independently_authenticated_feature_observation",
                  "actual_released_model_compared",
                  "unused_real_race_outcomes_evaluated",
                  "real_model_promotion_authorized","actual_purchase_authorized"):
            self.assertIs(a[k],False)


if __name__=="__main__":
    unittest.main()
