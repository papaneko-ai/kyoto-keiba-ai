import unittest
from dataclasses import replace
from diagnostics.kyoto_extensible_market_quotes import MarketQuote,MarketQuoteError,combine_market_quotes
CUTOFF="2026-11-21T05:00:00Z"
def q(t,n,odds="12.3"):
    return MarketQuote("2026-11-21_KYOTO_1R",t,n,odds,
       "2026-11-21T02:00:00Z","a"*64,"LIVE_PRE_RACE")
class MultiMarket(unittest.TestCase):
    def test_and_both_markets_one_race(self):
        x=combine_market_quotes([q("quinella",(1,2)),q("bracket_quinella",(1,2))],cutoff_utc=CUTOFF)
        self.assertEqual(len(x["markets_present"]),2)
        self.assertTrue(x["supports_quinella_and_bracket_together"])
        self.assertFalse(x["recommendations_ready"])
    def test_single_market_permitted(self):
        x=combine_market_quotes([q("quinella",(1,2))],cutoff_utc=CUTOFF)
        self.assertFalse(x["supports_quinella_and_bracket_together"])
    def test_three_way_future_schema_without_live_enable(self):
        self.assertEqual(q("trio",(1,2,3)).validated(cutoff_utc=CUTOFF).combination,(1,2,3))
        with self.assertRaises(MarketQuoteError):
            combine_market_quotes([q("trio",(1,2,3))],cutoff_utc=CUTOFF)
    def test_trifecta_order_is_significant(self):
        self.assertNotEqual(q("trifecta",(1,2,3)).combination,q("trifecta",(3,2,1)).combination)
    def test_unordered_not_canonical_rejected(self):
        with self.assertRaises(MarketQuoteError):
            q("quinella",(2,1)).validated(cutoff_utc=CUTOFF)
    def test_same_frame_bracket_pair_can_be_held_for_roster_validation(self):
        quote=q("bracket_quinella",(1,1))
        result=combine_market_quotes([quote,q("quinella",(1,2))],cutoff_utc=CUTOFF)
        self.assertTrue(result["supports_quinella_and_bracket_together"])
        self.assertFalse(result["recommendations_ready"])
    def test_duplicate_horse_in_quinella_invalid(self):
        with self.assertRaises(MarketQuoteError):
            q("quinella",(1,1)).validated(cutoff_utc=CUTOFF)
    def test_frame_out_of_bounds(self):
        with self.assertRaises(MarketQuoteError):
            q("bracket_quinella",(1,9)).validated(cutoff_utc=CUTOFF)
    def test_different_race_rejected(self):
        other=replace(q("quinella",(1,3)),race_id="2026-11-21_KYOTO_2R")
        with self.assertRaises(MarketQuoteError):
            combine_market_quotes([q("quinella",(1,2)),other],cutoff_utc=CUTOFF)
    def test_after_start_rejected(self):
        with self.assertRaises(MarketQuoteError):
            combine_market_quotes([replace(q("quinella",(1,2)),captured_utc="2026-11-21T06:00:00Z")],cutoff_utc=CUTOFF)
    def test_final_odd_rejected(self):
        with self.assertRaises(MarketQuoteError):
            combine_market_quotes([replace(q("quinella",(1,2)),source_phase="HISTORICAL_FINAL")],cutoff_utc=CUTOFF)
    def test_nan_rejected(self):
        with self.assertRaises(MarketQuoteError):
            q("quinella",(1,2),"NaN").validated(cutoff_utc=CUTOFF)
    def test_duplicate_rejected(self):
        with self.assertRaises(MarketQuoteError):
            combine_market_quotes([q("quinella",(1,2)),q("quinella",(1,2),"13.0")],cutoff_utc=CUTOFF)
    def test_tampered_sha_rejected(self):
        with self.assertRaises(MarketQuoteError):
            replace(q("quinella",(1,2)),source_sha256="BAD").validated(cutoff_utc=CUTOFF)
if __name__=="__main__":unittest.main()
