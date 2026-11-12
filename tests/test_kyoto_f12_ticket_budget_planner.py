"""Independent fixed F12 budget/manual-selection acceptance with no live bets."""
import copy
import unittest
from diagnostics.kyoto_f12_ticket_budget_planner import plan_f12,F12Rejected
def candidates(market="QUINELLA"):
    tickets=[[1,2],[2,3],[3,4]]
    if market=="BRACKET":tickets=[[1,1],[1,2],[2,2]]
    return [{"race":r,"priority":r,"eligible":True,"ticket_type":market,
       "tickets":[{"pair":p,"weight":w} for p,w in zip(tickets,[60,30,10])]}
       for r in range(1,6)]
def params(market="QUINELLA"):
    return dict(day_budget_yen=10000,exposure_target_yen=3500,market=market,
     mode="AUTO",candidates=candidates(market),selected_races=[1,2,3])
class F12IndependentAcceptance(unittest.TestCase):
    def test_auto_determinism_and_unused_budget(self):
        p=params();r=plan_f12(**p)
        self.assertEqual(r,plan_f12(**p))
        self.assertEqual(r["spent_yen"],3500)
        self.assertEqual(r["unspent_yen"],6500)
        self.assertEqual(len(r["selected"]),3)
    def test_concentration_benefits_rank_one(self):
        r=plan_f12(**params())
        amounts=[x["stake_yen"] for x in r["selected"]]
        self.assertGreater(amounts[0],amounts[1])
        self.assertGreater(amounts[1],amounts[2])
    def test_equal_split_when_opted_out(self):
        r=plan_f12(**{**params(),"concentrate":False})
        amounts=[x["stake_yen"] for x in r["selected"]]
        self.assertLessEqual(max(amounts)-min(amounts),100)
    def test_bracket_switch_including_same_frame(self):
        r=plan_f12(**params("BRACKET"))
        self.assertEqual(r["ticket_type"],"BRACKET")
        self.assertEqual(r["selected"][0]["tickets"][0]["pair"],[1,1])
        self.assertFalse(r["real_purchase_authorized"])
    def test_quinella_same_horse_rejected(self):
        p=params();p["candidates"][0]["tickets"][0]["pair"]=[1,1]
        with self.assertRaises(F12Rejected):plan_f12(**p)
    def test_manual_ratio_stakes(self):
        p=params();p.update(mode="MANUAL",manual_race_amounts={1:1500,2:800,3:300})
        r=plan_f12(**p)
        self.assertEqual(r["spent_yen"],2600)
        self.assertEqual(r["unspent_yen"],7400)
        self.assertEqual([x["stake_yen"] for x in r["selected"]],[1500,800,300])
    def test_manual_all_zero_means_skip(self):
        p=params();p.update(mode="MANUAL",manual_race_amounts={1:0,2:0,3:0})
        r=plan_f12(**p)
        self.assertEqual(r["spent_yen"],0)
        self.assertEqual(r["unspent_yen"],10000)
        self.assertEqual(r["selected_race_count"],3)
    def test_all_skip_zero_selected(self):
        p=params();p["selected_races"]=[]
        r=plan_f12(**p)
        self.assertEqual(r["spent_yen"],0)
        self.assertEqual(r["selected"],[])
    def test_max_four_races(self):
        p=params();p["selected_races"]=[5,3,1,2]
        r=plan_f12(**p)
        self.assertEqual(len(r["selected"]),4)
        self.assertEqual([x["race"] for x in r["selected"]],[1,2,3,5])
    def test_five_selected_rejected(self):
        p=params();p["selected_races"]=[1,2,3,4,5]
        with self.assertRaises(F12Rejected):plan_f12(**p)
    def test_100_yen_units(self):
        for budget in (0,100,200,1000,10500):
            p=params();p["day_budget_yen"]=budget;p["exposure_target_yen"]=min(budget,500)
            r=plan_f12(**p)
            self.assertLessEqual(r["spent_yen"],budget)
            self.assertEqual(r["spent_yen"]%100,0)
            self.assertTrue(all(t["stake_yen"]%100==0 for x in r["selected"] for t in x["tickets"]))
    def test_invalid_budget_inputs(self):
        for bad in (True,-100,150,1_000_100,"1000"):
            p=params();p["day_budget_yen"]=bad
            with self.subTest(bad=bad),self.assertRaises(F12Rejected):plan_f12(**p)
    def test_overspend_refused(self):
        p=params();p["exposure_target_yen"]=10100
        with self.assertRaises(F12Rejected):plan_f12(**p)
        p=params();p.update(mode="MANUAL",manual_race_amounts={1:2000,2:2000,3:2000})
        with self.assertRaises(F12Rejected):plan_f12(**p)
    def test_manual_missing_keys_refused(self):
        p=params();p.update(mode="MANUAL",manual_race_amounts={1:100,2:200})
        with self.assertRaises(F12Rejected):plan_f12(**p)
    def test_market_mismatch_rejected(self):
        p=params();p["market"]="BRACKET"
        with self.assertRaises(F12Rejected):plan_f12(**p)
    def test_duplicate_ticket_rejected(self):
        p=params();p["candidates"][0]["tickets"][1]["pair"]=[1,2]
        with self.assertRaises(F12Rejected):plan_f12(**p)
    def test_fourth_ticket_rejected(self):
        p=params();p["candidates"][0]["tickets"].append({"pair":[4,5],"weight":10})
        with self.assertRaises(F12Rejected):plan_f12(**p)
    def test_excluded_race_rejected(self):
        p=params();p["candidates"][1]["eligible"]=False
        with self.assertRaises(F12Rejected):plan_f12(**p)
    def test_zero_weight_cannot_spend(self):
        p=params()
        for t in p["candidates"][0]["tickets"]:t["weight"]=0
        with self.assertRaises(F12Rejected):plan_f12(**p)
    def test_manual_override_no_hidden_exposure(self):
        p=params();p.update(mode="MANUAL",manual_race_amounts={1:200,2:500,3:1000})
        r=plan_f12(**p)
        self.assertEqual(r["spent_yen"],1700)
        self.assertEqual(r["unspent_yen"],8300)
        self.assertFalse(r["real_source_verified"])
        self.assertFalse(r["model_calibrated"])
    def test_boolean_weight_refused(self):
        p=params();p["candidates"][0]["tickets"][0]["weight"]=True
        with self.assertRaises(F12Rejected):plan_f12(**p)
    def test_no_manual_input_in_auto(self):
        p=params();p["manual_race_amounts"]={1:100}
        with self.assertRaises(F12Rejected):plan_f12(**p)
if __name__=="__main__":unittest.main()
