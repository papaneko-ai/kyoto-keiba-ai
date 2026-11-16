"""Weekend PC/SP must refer to the exact same Kyoto 12R identity; zero HTTP."""
import unittest
from unittest.mock import patch
from diagnostics import kyoto_nov15_two_original_observer as pc

class RaceTargetParityTests(unittest.TestCase):
    def test_both_day_pc_observe_only_exact_12_even_with_earlier_races(self):
        for day in ("20261121","20261122"):
            with self.subTest(day=day):
                links=[
                    ("https://jra.jp/JRADB/accessD.html?CNAME=pw020aaa11%2F11"+day,
                     "京都 11R", "pw020aaa11/11"+day),
                    ("https://jra.jp/JRADB/accessD.html?CNAME=pw020aaa12%2F12"+day,
                     "京都 12R", "pw020aaa12/12"+day),
                ]
                with patch.object(pc,"DAY",day),patch.object(pc,"observed_links",return_value=links):
                    selected=pc._single_observed_racecard(b"official saved mock",
                                                        "https://jra.jp/JRADB/accessD.html?CNAME=meeting")
                self.assertEqual(selected,(12,links[1][0]))
    def test_saturday_and_sunday_must_not_fallback_to_11r(self):
        for day in ("20261121","20261122"):
            links=[("https://jra.jp/JRADB/accessD.html?CNAME=pw020aaa11%2F11"+day,
                    "京都 11R","pw020aaa11/11"+day)]
            with patch.object(pc,"DAY",day),patch.object(pc,"observed_links",return_value=links):
                self.assertIsNone(pc._single_observed_racecard(b"mock","https://jra.jp/"))
    def test_ambiguous_dual_12r_official_links_are_rejected(self):
        day="20261121"
        links=[
            ("https://jra.jp/JRADB/accessD.html?CNAME=pw020aaa12%2F12"+day,
             "京都 12R","pw020aaa12/12"+day),
            ("https://jra.jp/JRADB/accessD.html?CNAME=pw020bbb12%2F12"+day,
             "京都 12R","pw020bbb12/12"+day),
        ]
        with patch.object(pc,"DAY",day),patch.object(pc,"observed_links",return_value=links):
            with self.assertRaisesRegex(pc.ObservationRejected,"ambiguous_same_race"):
                pc._single_observed_racecard(b"mock","https://jra.jp/")
    def test_historical_nov15_max_race_policy_preserved(self):
        day="20261115"
        links=[("https://jra.jp/JRADB/accessD.html?CNAME=pw020aaa01%2F01"+day,
                "京都 1R","pw020aaa01/01"+day)]
        with patch.object(pc,"DAY",day),patch.object(pc,"observed_links",return_value=links):
            self.assertEqual(pc._single_observed_racecard(b"mock","https://jra.jp/")[0],1)
if __name__=="__main__":
    unittest.main()
