"""Whole-day synthetic P3/P5/P6 budget and fail-closed tests."""
import copy,hashlib,unittest
from diagnostics.p3_p5_p6_synthetic_day_lab import freeze_lab_day
from diagnostics.p3_p5_p6_synthetic_pipeline_lab import LabBridgeRejected,replay_lab_settlement
from diagnostics.p3_offline_model_tournament import predict
from test_p3_offline_model_tournament import fixture,utc

def race(i,odds=30):
    s=fixture(10)["snapshot"]
    s["race_id"]=f"LAB-PORTFOLIO-{i:02d}"
    s["feature_source_sha256"]=hashlib.sha256(str(i).encode()).hexdigest()
    p=predict(s,"PL_BASE")
    return {"snapshot":s,"observed_utc":utc(41),
        "frozen_utc":utc(41.5),
        "synthetic_market":{"race_id":s["race_id"],
            "market_type":"QUINELLA","scope":"LAB_SYNTHETIC_ODDS_ONLY",
            "prices":[{"pair":r["pair"],"decimal_odds":odds} for r in p["quinella"]]}}
class DayTests(unittest.TestCase):
 def setUp(self):self.rows=[race(i) for i in range(1,6)]
 def day(self,**kw):
    return freeze_lab_day(self.rows,daily_budget_yen=10000,**kw)
 def test_three_races_ranked_capped_and_unspent(self):
    a=self.day()
    self.assertEqual(len(a["selected"]),3)
    self.assertEqual([x["rank"] for x in a["selected"]],[1,2,3])
    self.assertEqual(len(a["skipped"]),2)
    self.assertLessEqual(a["spent_yen"],3500)
    self.assertEqual(a["spent_yen"]+a["unspent_yen"],10000)
    self.assertTrue(all(len(x["pipeline"]["frozen"]["frozen"]["tickets"])<=2 for x in a["selected"]))
 def test_explicit_four_races_three_tickets(self):
    a=self.day(max_races=4,max_tickets=3)
    self.assertLessEqual(len(a["selected"]),4)
    self.assertLessEqual(a["spent_yen"],3500)
 def test_one_race_small_budget_skips_without_fabrication(self):
    result=freeze_lab_day([race(1)],daily_budget_yen=100)
    self.assertEqual(result["spent_yen"],0)
    self.assertFalse(result["selected"])
 def test_no_positive_market_is_skip(self):
    self.rows=[race(1,1.01),race(2,1.01)]
    self.assertEqual(self.day()["spent_yen"],0)
 def test_deterministic_replay(self):
    self.assertEqual(self.day(),self.day())
 def test_reordered_candidates_have_stable_ranking(self):
    a=self.day();self.rows.reverse();b=self.day()
    self.assertEqual(a["day_sha256"],b["day_sha256"])
 def test_duplicate_race_rejected(self):
    self.rows[1]["snapshot"]["race_id"]=self.rows[0]["snapshot"]["race_id"]
    with self.assertRaisesRegex(LabBridgeRejected,"day_duplicate_race"):self.day()
 def test_mixed_dates_rejected(self):
    self.rows[1]["snapshot"]["race_start_utc"]=utc(70)
    with self.assertRaisesRegex(LabBridgeRejected,"day_mixed_utc_dates"):self.day()
 def test_out_of_order_market_rejected(self):
    self.rows[1]["observed_utc"]=utc(42.5)
    with self.assertRaises(LabBridgeRejected):self.day()
 def test_missing_odds_rejected_before_portfolio(self):
    self.rows[1]["synthetic_market"]["prices"].pop()
    with self.assertRaisesRegex(LabBridgeRejected,"market_incomplete"):self.day()
 def test_real_market_claim_refused(self):
    self.rows[1]["synthetic_market"]["scope"]="OFFICIAL_JRA"
    with self.assertRaises(LabBridgeRejected):self.day()
 def test_budget_not_multiple_of_hundred(self):
    with self.assertRaisesRegex(LabBridgeRejected,"daily_policy_invalid"):
        freeze_lab_day(self.rows,daily_budget_yen=10155)
 def test_max_five_races_rejected(self):
    with self.assertRaisesRegex(LabBridgeRejected,"daily_policy_invalid"):
        self.day(max_races=5)
 def test_no_official_settlement_or_purchase(self):
    a=self.day()
    self.assertFalse(a["official_jra_authenticated"])
    self.assertFalse(a["real_purchase_authorized"])
    self.assertFalse(a["real_paper_trade_recorded"])
    for r in a["selected"]:
        self.assertIsNone(replay_lab_settlement(r["pipeline"],[])["profit_yen"])
if __name__=="__main__":unittest.main()
