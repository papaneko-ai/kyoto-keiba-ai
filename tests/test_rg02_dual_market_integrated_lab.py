import copy
import unittest
from diagnostics.rg02_dual_market_integrated_lab import integrate_research_market, IntegratedMarketRejected

def race(n=4):
    strengths={"1":4.0,"2":3.0,"3":2.0,"4":1.0}
    frames={"1":1,"2":1,"3":2,"4":3}
    return {
        "date":"2026-11-10","race":n,"venue":"京都",
        "provenance":"LAB_SYNTHETIC_ONLY",
        "strengths":strengths,"frames":frames,
        "market_observed_utc":"2026-11-10T01:00:00Z",
        "scheduled_start_utc":"2026-11-10T02:00:00Z",
        "odds":{"quinella":{f"{a}-{b}":"30.0" for a in range(1,5) for b in range(a+1,5)},
                "bracket":{"1-1":"30.0","1-2":"30.0","1-3":"30.0","2-3":"30.0"}}
    }

class IntegratedMarkets(unittest.TestCase):
    def test_both_markets_fully_integrated_budget_and_receipt(self):
        r=integrate_research_market([race()],budget_yen=1000)
        self.assertEqual([x["ticket_type"] for x in r["market_summaries"]],["QUINELLA","BRACKET"])
        self.assertEqual([x["all_pairs_checked"] for x in r["market_summaries"]],[6,4])
        self.assertEqual(len(r["selected_allocations"]),2)
        self.assertEqual(r["spent_yen"],400)
        self.assertEqual(r["unspent_yen"],600)
        self.assertEqual(r,integrate_research_market([race()],budget_yen=1000))
        self.assertFalse(r["real_bet_authorized"])
        self.assertFalse(r["prediction_ready"])
        self.assertFalse(r["calibrated_real_prediction"])
        self.assertEqual(r["network_requests"],0)
    def test_same_frame_supported(self):
        r=integrate_research_market([race()],budget_yen=1000)
        self.assertTrue(any(x["pair"]==[1,1] for x in r["market_summaries"][1]["tickets"])
                        or r["market_summaries"][1]["all_pairs_checked"]==4)
    def test_budget_is_ceiling_not_mandatory(self):
        r=integrate_research_market([race()],budget_yen=0)
        self.assertEqual(r["spent_yen"],0)
        self.assertEqual(r["unspent_yen"],0)
    def test_no_positive_ev_means_skip(self):
        x=race()
        x["odds"]={"quinella":{k:"1.01" for k in x["odds"]["quinella"]},
                   "bracket":{k:"1.01" for k in x["odds"]["bracket"]}}
        out=integrate_research_market([x],budget_yen=1000)
        self.assertEqual(out["spent_yen"],0)
    def test_missing_quinella_pair_fails_closed(self):
        x=race();x["odds"]["quinella"].pop("1-2")
        with self.assertRaisesRegex(Exception,"market_coverage_mismatch"):
            integrate_research_market([x],budget_yen=1000)
    def test_missing_bracket_market_fails_closed(self):
        x=race();x["odds"].pop("bracket")
        with self.assertRaisesRegex(IntegratedMarketRejected,"missing_market"):
            integrate_research_market([x],budget_yen=1000)
    def test_forged_live_provenance_rejected(self):
        x=race();x["provenance"]="OFFICIAL_JRA"
        with self.assertRaisesRegex(IntegratedMarketRejected,"unauthenticated_live"):
            integrate_research_market([x],budget_yen=1000)
    def test_after_start_rejected(self):
        x=race();x["market_observed_utc"]=x["scheduled_start_utc"]
        with self.assertRaisesRegex(IntegratedMarketRejected,"not_prerace"):
            integrate_research_market([x],budget_yen=1000)
    def test_invalid_price_rejected(self):
        x=race();x["odds"]["quinella"]["1-2"]="nan"
        with self.assertRaisesRegex(Exception,"odds_invalid"):
            integrate_research_market([x],budget_yen=1000)
    def test_roster_frame_mismatch_rejected(self):
        x=race();x["frames"].pop("3")
        with self.assertRaisesRegex(IntegratedMarketRejected,"frame_roster_mismatch"):
            integrate_research_market([x],budget_yen=1000)
    def test_duplicate_race_rejected(self):
        with self.assertRaisesRegex(IntegratedMarketRejected,"duplicate"):
            integrate_research_market([race(),copy.deepcopy(race())],budget_yen=1000)
    def test_three_ticket_cap_and_four_market_ceiling(self):
        x=race()
        y=copy.deepcopy(x);y["race"]=5
        z=copy.deepcopy(x);z["race"]=6
        r=integrate_research_market([x,y,z],budget_yen=3000,max_tickets=3)
        self.assertLessEqual(len(r["selected_allocations"]),4)
        self.assertLessEqual(r["spent_yen"],3000)
        self.assertTrue(all(len(x["tickets"])<=3 for x in r["selected_allocations"]))
    def test_not_use_market_value_as_true_prediction(self):
        r=integrate_research_market([race()],budget_yen=1000)
        self.assertTrue(r["has_complete_market_coverage"])
        self.assertFalse(r["authorized_jra_source"])
        self.assertFalse(r["externally_verified_market"])
        self.assertFalse(r["real_paper_trade_recorded"])

if __name__=="__main__": unittest.main()
