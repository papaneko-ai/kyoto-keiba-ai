"""R06 fixed-gate exhaustive P3 horse/frame probability consistency.

Positive, same-frame, maximum-field, scratched-runner and destructive LAB
tests. No authentic JRA source or actual ticket/purchase is claimed.
"""
import copy,hashlib,math,unittest
from diagnostics.p3_p6_research_no_bet import (
    ordered_first_second,quinella_from_strength,bracket_from_quinella,
    ResearchRejected)
from diagnostics.p3_offline_model_tournament import predict,TournamentRejected
from test_p3_offline_model_tournament import fixture

def runners(n):
    weights={i:float(i+1) for i in range(1,n+1)}
    frames={i:(i-1)//2+1 for i in range(1,n+1)}
    return weights,frames

class R06PairFrameAcceptance(unittest.TestCase):
    def test_ordered_horse_probabilities_sum_one(self):
        for n in (3,8,16):
            weights,_=runners(n)
            ordered=ordered_first_second(weights)
            self.assertEqual(len(ordered),n*(n-1))
            self.assertAlmostEqual(math.fsum(ordered.values()),1,places=12)
            self.assertTrue(all(0<p<1 for p in ordered.values()))

    def test_quinella_is_exact_symmetrization(self):
        weights,_=runners(16)
        ordered=ordered_first_second(weights)
        paired=quinella_from_strength(weights)
        self.assertEqual(len(paired),120)
        for (i,j),p in paired.items():
            self.assertLess(i,j)
            self.assertAlmostEqual(p,ordered[(i,j)]+ordered[(j,i)],places=14)
        self.assertAlmostEqual(math.fsum(paired.values()),1,places=12)

    def test_frame_probability_is_exact_horse_aggregation(self):
        w,f=runners(16)
        p=quinella_from_strength(w)
        brackets=bracket_from_quinella(p,f)
        self.assertEqual(len(brackets),36)
        self.assertAlmostEqual(math.fsum(brackets.values()),1,places=12)
        for pair,prob in brackets.items():
            aggregate=math.fsum(value for (a,b),value in p.items()
              if tuple(sorted((f[a],f[b])))==pair)
            self.assertAlmostEqual(prob,aggregate,places=12)

    def test_same_frame_is_supported_and_positive(self):
        w,f=runners(16)
        brackets=bracket_from_quinella(quinella_from_strength(w),f)
        self.assertEqual(set((i,i) for i in range(1,9)) &
                         set(brackets),set((i,i) for i in range(1,9)))
        self.assertTrue(all(brackets[(i,i)]>0 for i in range(1,9)))

    def test_scratched_runner_excluded_without_leak(self):
        weights,frames=runners(8)
        weights.pop(8);frames.pop(8)
        pairs=quinella_from_strength(weights)
        frame=bracket_from_quinella(pairs,frames)
        self.assertEqual(len(pairs),21)
        self.assertTrue(all(8 not in pair for pair in pairs))
        self.assertAlmostEqual(math.fsum(frame.values()),1,places=12)

    def test_missing_frame_fails_closed(self):
        weights,frames=runners(8);frames.pop(8)
        with self.assertRaisesRegex(ResearchRejected,"frame_missing"):
            bracket_from_quinella(quinella_from_strength(weights),frames)

    def test_nonnumeric_strength_refused(self):
        weights,_=runners(8);weights[4]=float("nan")
        with self.assertRaises(ResearchRejected):
            quinella_from_strength(weights)

    def test_zero_strength_refused(self):
        weights,_=runners(8);weights[4]=0
        with self.assertRaises(ResearchRejected):
            quinella_from_strength(weights)

    def test_out_of_range_frame_refused(self):
        weights,frames=runners(8);frames[8]=9
        with self.assertRaisesRegex(ResearchRejected,"frame_value_invalid"):
            bracket_from_quinella(quinella_from_strength(weights),frames)

    def test_invalid_probability_and_sum_refused(self):
        _,frames=runners(3)
        for p in ({(1,2):float("nan")}, {(1,2):0.4}, {(1,2):1.1}):
            with self.subTest(p=p):
                with self.assertRaises(ResearchRejected):
                    bracket_from_quinella(p,frames)

    def test_model_forecast_preserves_both_market_normalization(self):
        s=fixture(10)["snapshot"]
        for model in ("PL_BASE","PL_SHARP","PL_FLAT","PAIR_PRODUCT","PL_PRODUCT_BLEND"):
            p=predict(s,model)
            self.assertAlmostEqual(math.fsum(x["probability"] for x in p["quinella"]),1,places=12)
            self.assertAlmostEqual(math.fsum(x["probability"] for x in p["bracket"]),1,places=12)
            self.assertFalse(p["production_eligible"])

    def test_forecast_determinism_and_roster_reorder(self):
        s=fixture(10)["snapshot"]
        before=predict(s,"PL_BASE")
        s["runners"].reverse()
        after=predict(s,"PL_BASE")
        self.assertEqual(before,after)

    def test_illegal_same_horse_market_is_never_issued(self):
        s=fixture(10)["snapshot"]
        p=predict(s,"PL_BASE")
        self.assertTrue(all(x["pair"][0]<x["pair"][1] for x in p["quinella"]))
        self.assertTrue(any(x["pair"][0]==x["pair"][1] for x in p["bracket"]))

    def test_spoofed_live_input_refused(self):
        s=fixture(10)["snapshot"];s["source_scope"]="JRA_LIVE"
        with self.assertRaisesRegex(TournamentRejected,"nonlab_source_forbidden"):
            predict(s,"PL_BASE")
if __name__=="__main__":unittest.main()
