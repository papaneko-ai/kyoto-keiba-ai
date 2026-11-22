"""Nov22 real official Japanese race start timestamp acceptance and negatives."""
import unittest
from diagnostics.kyoto_g03_all_races import parse,G03Error
from tests.test_kyoto_g03_all_races import card,PARENT

DAY="20261122"
UTC="2026-11-22T00:17:00Z"

class ActualJapaneseStart(unittest.TestCase):
    def test_official_japanese_start_time(self):
        r=parse(card(time="発走時刻：10時05分",race=1,day=DAY),DAY,1,PARENT,UTC)
        self.assertEqual(r["start_time_jst"],"10:05")
        self.assertEqual(r["runner_count"],8)
    def test_legacy_colon_start_still_works(self):
        r=parse(card(time="発走 10:05",race=1,day=DAY),DAY,1,PARENT,UTC)
        self.assertEqual(r["start_time_jst"],"10:05")
    def test_mixed_consistent_formats_accepted(self):
        r=parse(card(time="発走 10:05 発走時刻：10時05分",race=1,day=DAY),DAY,1,PARENT,UTC)
        self.assertEqual(r["start_time_jst"],"10:05")
    def test_conflicting_start_refused(self):
        with self.assertRaisesRegex(G03Error,"start_time_not_proven"):
            parse(card(time="発走 10:05 発走時刻：10時15分",race=1,day=DAY),DAY,1,PARENT,UTC)
    def test_non_start_time_cannot_be_promoted(self):
        with self.assertRaisesRegex(G03Error,"start_time_not_proven"):
            parse(card(time="入場時間 10時05分",race=1,day=DAY),DAY,1,PARENT,UTC)

if __name__=="__main__":unittest.main()
