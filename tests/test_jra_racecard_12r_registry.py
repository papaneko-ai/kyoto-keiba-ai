"""Offline-only tests; genuine archived JRA ZIP supplied separately, never fabricated."""
import unittest
from diagnostics.jra_racecard_12r_registry import INDEXED,racecard_sources
class RegistryTests(unittest.TestCase):
 def test_twelve_races(self):self.assertEqual(len(racecard_sources()),12)
 def test_complete_sequence(self):self.assertEqual([x["race_number"] for x in racecard_sources()],list(range(1,13)))
 def test_no_assumed_html(self):self.assertTrue(all(not x["raw_html_acquired"] for x in racecard_sources()))
 def test_no_backdated_snapshots(self):self.assertTrue(all(not x["pre_race_snapshot_verified"] for x in racecard_sources()))
 def test_no_training(self):self.assertTrue(all(not x["training_ready"] for x in racecard_sources()))
 def test_no_host_forgery(self):self.assertTrue(racecard_sources()[1]["url"].startswith("https://own.jra.jp/"))
 def test_deterministic(self):self.assertEqual(racecard_sources(),racecard_sources())
if __name__=="__main__":unittest.main()
