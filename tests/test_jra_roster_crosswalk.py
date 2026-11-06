"""Synthetic offline CI for full-roster crosswalk; real-HTML tests shipped separately."""
import unittest
from diagnostics.jra_roster_crosswalk import crosswalk,inspect_entry_snapshot,reconcile_counts
URL="https://www.jra.go.jp/JRADB/accessD.html"
HTML=("""<table><tr><th class="horse">馬名</th><th class="num">馬番</th><th class="waku">枠</th><th class="place">着順</th></tr>"""
      """<tr><td class="place">1</td><td class="waku"><img alt="枠3赤"></td><td class="num">5</td>"""
      """<td class="horse"><a href="/JRADB/accessU.html?CNAME=test123">試験馬</a></td></tr></table>""").encode("cp932")
class Tests(unittest.TestCase):
 def test_one_horse(self):
  x=crosswalk(HTML,result_url=URL)
  self.assertEqual(x["runner_row_count"],1)
  self.assertEqual(x["runners"][0]["horse_number"],5)
  self.assertEqual(x["runners"][0]["frame_number"],3)
  self.assertIsNone(x["runners"][0]["permanent_jra_horse_id"])
  self.assertFalse(x["prediction_ready"])
 def test_id_not_inferred(self):
  x=crosswalk(HTML,result_url=URL)
  self.assertFalse(x["permanent_ids_verified"])
 def test_reproducible(self):
  self.assertEqual(crosswalk(HTML,result_url=URL),crosswalk(HTML,result_url=URL))
 def test_not_official(self):
  with self.assertRaises(ValueError):crosswalk(HTML,result_url="https://not-jra.example")
 def test_no_card(self):
  x=inspect_entry_snapshot(b"<title>\x8fo\x94n\x95\\</title>",source_url=URL)
  self.assertFalse(x["racecard_certified"])
 def test_missing_counts(self):
  x=reconcile_counts(crosswalk(HTML,result_url=URL))
  self.assertEqual(x["status"],"MISSING_INDEPENDENT_RACECARD")
 def test_equal_counts_not_certified(self):
  x=reconcile_counts(crosswalk(HTML,result_url=URL),{1:1})
  self.assertEqual(x["status"],"COUNTS_MATCH_NOT_CERTIFIED")
  self.assertFalse(x["verified"])
if __name__=="__main__":unittest.main()
