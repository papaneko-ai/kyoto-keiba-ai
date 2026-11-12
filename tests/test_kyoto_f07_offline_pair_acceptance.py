"""Independent F07 fixed-contract certification tests. No real market prices."""
import copy
import itertools
import json
import math
import unittest
from diagnostics.kyoto_f07_offline_pair_acceptance import calculate_f07,F07Rejected
def fixture(n=16):
    # At 16 runners, every frame has two horses => all 36 frame pairs including same.
    runners=[dict(number=i,frame=(i+1)//2,status="ACTIVE",strength=float(i))
             for i in range(1,n+1)]
    return make_args(runners)
def make_args(runners):
    active=[r for r in runners if r["status"]=="ACTIVE"]
    horse=list(sorted(r["number"] for r in active))
    q=[list(pair) for pair in itertools.combinations(horse,2)]
    b=sorted({tuple(sorted((a["frame"],c["frame"])))
              for a,c in itertools.combinations(active,2)})
    return dict(runners=runners,
        market_status={"QUINELLA":"OPEN","BRACKET":"OPEN"},
        quoted_pairs={"QUINELLA":q,"BRACKET":[list(p) for p in b]})
class F07IndependentAcceptance(unittest.TestCase):
    def test_full16_all120_horse36_frame_pairs(self):
        r=calculate_f07(**fixture())
        self.assertEqual(len(r["quinella"]),120)
        self.assertEqual(len(r["bracket"]),36)
        self.assertEqual(r["ordered_first_second_pairs"],240)
        self.assertEqual(r["same_frame_pairs"],[[i,i] for i in range(1,9)])
        for key in ("ordered_sum","quinella_sum","bracket_sum"):
            self.assertAlmostEqual(r[key],1.0,places=12)
        self.assertEqual(r,calculate_f07(**fixture()))
    def test_hand_calculated_two_horses(self):
        args=make_args([dict(number=1,frame=1,status="ACTIVE",strength=1.0),
                        dict(number=2,frame=2,status="ACTIVE",strength=3.0)])
        r=calculate_f07(**args)
        self.assertEqual(len(r["quinella"]),1)
        self.assertAlmostEqual(r["quinella"][0]["probability"],1.0,places=12)
        self.assertEqual(r["bracket"][0]["pair"],[1,2])
    def test_same_frame_only_possible_with_two_active(self):
        a=make_args([dict(number=1,frame=3,status="ACTIVE",strength=2.0),
                     dict(number=2,frame=3,status="ACTIVE",strength=3.0)])
        r=calculate_f07(**a)
        self.assertEqual(r["same_frame_pairs"],[[3,3]])
        self.assertAlmostEqual(r["bracket"][0]["probability"],1.0,places=12)
        a["runners"][1]["frame"]=4
        with self.assertRaises(F07Rejected):
            calculate_f07(**a)
    def test_scratch_changes_entire_pair_universe(self):
        a=fixture()
        a["runners"][-1]["status"]="SCRATCHED"
        with self.assertRaisesRegex(F07Rejected,"missing_or_extra_offered_pair"):
            calculate_f07(**a)
        fixed=make_args(a["runners"])
        r=calculate_f07(**fixed)
        self.assertEqual(len(r["quinella"]),105)
        self.assertEqual(r["scratched_or_excluded_runners"],[16])
        self.assertEqual(r["same_frame_pairs"],[[i,i] for i in range(1,8)])
    def test_excluded_does_not_contribute(self):
        a=fixture()
        a["runners"][0]["status"]="EXCLUDED"
        r=calculate_f07(**make_args(a["runners"]))
        self.assertNotIn(1,r["active_runners"])
        self.assertEqual(len(r["quinella"]),105)
    def test_market_suspended_fails_closed(self):
        for market in ("QUINELLA","BRACKET"):
            a=fixture()
            a["market_status"][market]="SUSPENDED"
            with self.subTest(market=market),self.assertRaisesRegex(F07Rejected,"market_not_open"):
                calculate_f07(**a)
    def test_unpublished_market_fails_closed(self):
        a=fixture()
        a["market_status"]["BRACKET"]="NOT_PUBLISHED"
        with self.assertRaises(F07Rejected):calculate_f07(**a)
    def test_missing_and_extra_quinella_refused(self):
        for op in ("missing","extra"):
            a=fixture()
            if op=="missing":
                a["quoted_pairs"]["QUINELLA"].pop()
            else:
                a["quoted_pairs"]["QUINELLA"].append([2,3])
            with self.subTest(op=op),self.assertRaises(F07Rejected):
                calculate_f07(**a)
    def test_missing_and_extra_bracket_refused(self):
        for op in ("missing","extra"):
            a=fixture()
            if op=="missing":
                a["quoted_pairs"]["BRACKET"].pop()
            else:
                a["quoted_pairs"]["BRACKET"].append([1,1])
            with self.subTest(op=op),self.assertRaises(F07Rejected):
                calculate_f07(**a)
    def test_reverse_pair_and_same_quinella_rejected(self):
        for bad in ([3,2],[2,2]):
            a=fixture()
            a["quoted_pairs"]["QUINELLA"][0]=bad
            with self.subTest(bad=bad),self.assertRaises(F07Rejected):
                calculate_f07(**a)
    def test_duplicate_runner_rejected(self):
        a=fixture()
        a["runners"][-1]["number"]=1
        with self.assertRaises(F07Rejected):
            calculate_f07(**a)
    def test_unknown_runner_status_rejected(self):
        a=fixture()
        a["runners"][3]["status"]="NONFINISHER"
        with self.assertRaises(F07Rejected):
            calculate_f07(**a)
    def test_runner_frame_invalid_rejected(self):
        for bad in (0,9,True):
            a=fixture()
            a["runners"][0]["frame"]=bad
            with self.subTest(bad=bad),self.assertRaises(F07Rejected):
                calculate_f07(**a)
    def test_strength_nan_infinity_and_bool_rejected(self):
        for bad in (float("nan"),float("inf"),float("-inf"),True,0,-1):
            a=fixture()
            a["runners"][0]["strength"]=bad
            with self.subTest(bad=str(bad)),self.assertRaises(F07Rejected):
                calculate_f07(**a)
    def test_zero_one_active_refused(self):
        for n in (0,1):
            a=fixture()
            for r in a["runners"][n:]:
                r["status"]="SCRATCHED"
            with self.assertRaises(F07Rejected):
                calculate_f07(**a)
    def test_numerical_scale_invariance(self):
        a=fixture()
        x=calculate_f07(**a)
        for factor in (1e-12,1e12):
            b=copy.deepcopy(a)
            for r in b["runners"]:
                r["strength"] *= factor
            y=calculate_f07(**b)
            for market in ("quinella","bracket"):
                for u,v in zip(x[market],y[market]):
                    self.assertEqual(u["pair"],v["pair"])
                    self.assertAlmostEqual(u["probability"],v["probability"],places=12)
    def test_snapshot_is_offline_and_not_credential_claim(self):
        x=calculate_f07(**fixture())
        for key in ("live_source_authenticated","price_ev_computed","calibration_verified","actual_bet_authorized"):
            self.assertIs(x[key],False)
        self.assertTrue(x["market_coverage_verified"])
        self.assertEqual(len(x["sha256"]),64)
    def test_lottery_ordered_3_horse_direct_probability(self):
        a=make_args([dict(number=1,frame=1,status="ACTIVE",strength=1.0),
                     dict(number=2,frame=2,status="ACTIVE",strength=1.0),
                     dict(number=3,frame=2,status="ACTIVE",strength=2.0)])
        r=calculate_f07(**a)
        p={tuple(x["pair"]):x["probability"] for x in r["quinella"]}
        # P(1,2) = P(1 wins, 2 second)+P(2 wins, 1 second)
        # = (1/4)*(1/3)+(1/4)*(1/3) = 1/6
        self.assertAlmostEqual(p[(1,2)],1/6,places=12)
        self.assertAlmostEqual(sum(p.values()),1.0,places=12)
        b={tuple(x["pair"]):x["probability"] for x in r["bracket"]}
        self.assertAlmostEqual(b[(2,2)],p[(2,3)],places=12)
        self.assertAlmostEqual(b[(1,2)],p[(1,2)]+p[(1,3)],places=12)
if __name__=="__main__":unittest.main()
