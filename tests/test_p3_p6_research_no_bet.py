"""P3/P4/P5/P6 numerical invariants and historical no-bet behavior.

All market figures in mechanics tests are laboratory fixtures, NOT JRA odds.
"""
import csv
import io
import math
import unittest
from pathlib import Path
from diagnostics.p3_p6_research_no_bet import (
    ResearchRejected, ordered_first_second, quinella_from_strength,
    bracket_from_quinella, market_ev, allocate_research_budget,
    historical_no_bet_receipt,
)

CSV = Path(__file__).resolve().parents[1] / "docs/diagnostics/p2_historical_feature_matrix_20261107_148.csv"

class ResearchEngineTests(unittest.TestCase):
    def test_two_runner_probabilities(self):
        q=quinella_from_strength({1:3,2:1})
        self.assertEqual(set(q),{(1,2)})
        self.assertAlmostEqual(q[(1,2)],1)

    def test_many_runner_pl_probabilities_normalized(self):
        weights={1:4,2:3,3:2,4:1}
        ordered=ordered_first_second(weights)
        q=quinella_from_strength(weights)
        self.assertAlmostEqual(sum(ordered.values()),1)
        self.assertAlmostEqual(sum(q.values()),1)
        self.assertEqual(len(q),6)
        self.assertAlmostEqual(q[(1,2)], ordered[(1,2)]+ordered[(2,1)])

    def test_reject_invalid_strengths(self):
        for bad in (0,-1,float('nan'),float('inf')):
            with self.subTest(bad=bad),self.assertRaises(ResearchRejected):
                quinella_from_strength({1:1,2:bad})

    def test_bracket_same_frame(self):
        q=quinella_from_strength({1:3,2:2,3:1})
        f=bracket_from_quinella(q,{1:1,2:1,3:2})
        self.assertIn((1,1),f)
        self.assertIn((1,2),f)
        self.assertAlmostEqual(sum(f.values()),1)
        self.assertAlmostEqual(f[(1,1)],q[(1,2)])

    def test_bracket_requires_every_runner_frame(self):
        with self.assertRaises(ResearchRejected):
            bracket_from_quinella(quinella_from_strength({1:2,2:1}),{1:1})

    def test_market_ev_requires_full_coverage(self):
        q=quinella_from_strength({1:3,2:2,3:1})
        with self.assertRaisesRegex(ResearchRejected,'market_coverage_mismatch'):
            market_ev(q,{(1,2):4.5})

    def test_ev_rejects_unnormalized_probability(self):
        with self.assertRaisesRegex(ResearchRejected,'pair_probabilities_not_normalized'):
            market_ev({(1,2):.25},{(1,2):5})

    def test_market_ev_numeric(self):
        result=market_ev({(1,2):.25,(1,3):.25,(2,3):.5},
                         {(1,2):5,(1,3):2,(2,3):2},uncertainty_margin=.2)[0]
        self.assertAlmostEqual(result['gross_return_per_1'],1.25)
        self.assertAlmostEqual(result['lower_bound_net_per_1'],0)
        self.assertAlmostEqual(result['expected_net_per_1'],.25)

    def test_reject_nonfinite_odds(self):
        for bad in ("NaN","Infinity",0,1,-3):
            with self.subTest(bad=bad),self.assertRaises(ResearchRejected):
                market_ev({(1,2):1.0},{(1,2):bad})

    def test_zero_daily_budget_means_no_tickets(self):
        r=allocate_research_budget([],daily_limit_yen=0)
        self.assertEqual(r['spent_yen'],0)
        self.assertEqual(r['selected'],[])
        self.assertFalse(r['live_bet_authorized'])

    def test_reject_non_100_yen_budget(self):
        with self.assertRaises(ResearchRejected):
            allocate_research_budget([],daily_limit_yen=1050)

    def test_unverified_market_always_skipped(self):
        r=allocate_research_budget([{'date':'2026-11-14','race':1,'ticket_type':'QUINELLA',
             'prediction_ready':True,'market_verified':False,'model_calibrated':True,
             'clock_verified':True,'tickets':[{'amount_yen':100}]}],daily_limit_yen=1000)
        self.assertEqual(r['spent_yen'],0)

    def test_research_budget_stays_under_cap(self):
        def row(n):
            return {'date':'2026-11-14','race':n,'ticket_type':'QUINELLA',
                    'prediction_ready':True,'market_verified':True,
                    'model_calibrated':True,'clock_verified':True,'confidence':.5,
                    'tickets':[{'amount_yen':100},{'amount_yen':100}]}
        r=allocate_research_budget([row(i) for i in range(1,8)],daily_limit_yen=600)
        self.assertEqual(r['spent_yen'],600)
        self.assertLessEqual(len(r['selected']),4)
        self.assertEqual(r['unspent_yen'],0)
        self.assertFalse(r['prediction_ready'])

    def test_reject_nonfinite_confidence(self):
        bad={'date':'2026-11-14','race':1,'ticket_type':'QUINELLA',
             'prediction_ready':True,'market_verified':True,'model_calibrated':True,
             'clock_verified':True,'confidence':float('nan'),
             'tickets':[{'amount_yen':100}]}
        with self.assertRaisesRegex(ResearchRejected,'confidence_invalid'):
            allocate_research_budget([bad],daily_limit_yen=1000)

    def test_reject_invalid_ticket_metadata(self):
        bad={'date':'2026-11-14','race':1,'ticket_type':'QUINELLA',
             'prediction_ready':True,'market_verified':True,'model_calibrated':True,
             'clock_verified':True,'confidence':.5,'tickets':[None]}
        with self.assertRaisesRegex(ResearchRejected,'ticket_invalid'):
            allocate_research_budget([bad],daily_limit_yen=1000)

    def test_reject_duplicate_race(self):
        row={'date':'2026-11-14','race':1,'ticket_type':'QUINELLA'}
        with self.assertRaisesRegex(ResearchRejected,'duplicate_race'):
            allocate_research_budget([row,dict(row)],daily_limit_yen=1000)

    def test_reject_invalid_very_extreme_strength(self):
        with self.assertRaises(ResearchRejected):
            quinella_from_strength({1:1e300,2:1e-300})

    def test_actual_historical_csv_never_produces_bets(self):
        rows=list(csv.DictReader(CSV.open(encoding='utf-8')))
        r=historical_no_bet_receipt(rows)
        self.assertEqual(r['runner_count'],148)
        self.assertEqual(r['suggested_races'],[])
        self.assertEqual(r['virtual_investment_yen'],0)
        self.assertEqual(r['ledger_events_written'],0)
        self.assertFalse(r['prediction_ready'])
        self.assertFalse(r['actual_purchase'])

    def test_historical_receipt_idempotent(self):
        rows=list(csv.DictReader(CSV.open(encoding='utf-8')))
        self.assertEqual(historical_no_bet_receipt(rows),historical_no_bet_receipt(rows))

    def test_cannot_convert_history_into_approved_prediction(self):
        rows=list(csv.DictReader(CSV.open(encoding='utf-8')))
        rows[0]['source_row_status']='PREDICTION_READY'
        with self.assertRaises(ResearchRejected):
            historical_no_bet_receipt(rows)

if __name__=='__main__':
    unittest.main()
