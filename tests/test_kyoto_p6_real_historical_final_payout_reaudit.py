"""Original SHA locked two ACTUAL official historical final payout tests.

The source ZIP must come from previous successful original capture run
43129613002, not a synthetic HTML generator. All odds in this file are FINAL
payouts after the actual race, never previous pre-race investment quotes.
"""
import os,unittest
from pathlib import Path
from diagnostics.kyoto_p6_real_historical_final_payout_reaudit import (
    extract_real_two_race_payouts,_payout,RealHistoricalPayoutRejected
)
SOURCE_ENV="KYOTO_ACTUAL_2DAY_ORIGINAL_ARCHIVE"
class ActualOfficialFinalPayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get(SOURCE_ENV):
            raise RuntimeError("actual_official_JRA_archive_required_no_synthetic_fallback")
        cls.original=Path(os.environ[SOURCE_ENV]).read_bytes()
    def test_actual_original_source_sha_and_both_races(self):
        r=extract_real_two_race_payouts(self.original)
        self.assertEqual(r["historical_race_count"],2)
        self.assertEqual(r["official_result_rows"],31)
        self.assertEqual(r["real_final_payout_pairs_verified"],4)
    def test_genuine_oct25_kyoto10_quinella(self):
        a=extract_real_two_race_payouts(self.original)["races"][0]
        self.assertEqual(a["date"],"2026-10-25")
        self.assertEqual(a["race_number"],10)
        self.assertEqual(a["quinella_final"],{"pair":[10,12],"yen_per_100":15090})
        self.assertEqual([a["winner_horse_number"],a["runner_up_horse_number"]],[12,10])
    def test_genuine_oct25_kyoto10_bracket(self):
        a=extract_real_two_race_payouts(self.original)["races"][0]
        self.assertEqual(a["bracket_final"],{"pair":[6,7],"yen_per_100":1540})
        self.assertEqual([a["winner_frame_number"],a["runner_up_frame_number"]],[7,6])
    def test_genuine_nov08_kyoto11_quinella(self):
        a=extract_real_two_race_payouts(self.original)["races"][1]
        self.assertEqual(a["date"],"2026-11-08")
        self.assertEqual(a["race_number"],11)
        self.assertEqual(a["quinella_final"],{"pair":[8,11],"yen_per_100":1670})
        self.assertEqual([a["winner_horse_number"],a["runner_up_horse_number"]],[11,8])
    def test_genuine_nov08_kyoto11_bracket(self):
        a=extract_real_two_race_payouts(self.original)["races"][1]
        self.assertEqual(a["bracket_final"],{"pair":[4,6],"yen_per_100":1330})
        self.assertEqual([a["winner_frame_number"],a["runner_up_frame_number"]],[6,4])
    def test_same_input_same_receipt_sha(self):
        self.assertEqual(extract_real_two_race_payouts(self.original),
                         extract_real_two_race_payouts(self.original))
    def test_single_corrupted_zip_byte_refused(self):
        raw=bytearray(self.original)
        raw[15]^=1
        with self.assertRaises(RealHistoricalPayoutRejected):
            extract_real_two_race_payouts(bytes(raw))
    def test_cross_date_wrong_source_refused(self):
        with self.assertRaises(RealHistoricalPayoutRejected):
            extract_real_two_race_payouts(self.original+b"garbage")
    def test_stale_or_final_cannot_be_relabelled_pre_race(self):
        r=extract_real_two_race_payouts(self.original)
        self.assertTrue(r["all_sources_postrace_only"])
        self.assertFalse(r["pre_race_market_prices_verified"])
        self.assertFalse(r["pre_race_frozen_investments_verified"])
        self.assertFalse(r["real_paper_trade_pnl_verified"])
    def test_missing_quinella_payout_fails(self):
        with self.assertRaises(RealHistoricalPayoutRejected):
            _payout("枠連 1-2 300 円 8 番人気 ワイド","馬連","馬単")
    def test_ambiguous_quinella_payout_fails(self):
        with self.assertRaises(RealHistoricalPayoutRejected):
            _payout("馬連 1-2 200 円 1 番人気 馬単 馬連 2-3 300 円 2 番人気 馬単","馬連","馬単")
    def test_unordered_pair_fails(self):
        with self.assertRaises(RealHistoricalPayoutRejected):
            _payout("馬連 12-10 15,090 円 62 番人気 馬単","馬連","馬単")
    def test_quinella_same_horse_fails(self):
        with self.assertRaises(RealHistoricalPayoutRejected):
            _payout("馬連 5-5 100 円 1 番人気 馬単","馬連","馬単")
    def test_bracket_same_frame_is_allowed(self):
        p=_payout("枠連 3-3 500 円 1 番人気 ワイド","枠連","ワイド")
        self.assertEqual(p,{"pair":[3,3],"yen_per_100":500})
    def test_bracket_9_out_of_range_fails(self):
        with self.assertRaises(RealHistoricalPayoutRejected):
            _payout("枠連 6-9 500 円 1 番人気 ワイド","枠連","ワイド")
    def test_bad_payout_currency_fails(self):
        with self.assertRaises(RealHistoricalPayoutRejected):
            _payout("馬連 1-2 0 円 1 番人気 馬単","馬連","馬単")
if __name__=="__main__":unittest.main()
