import unittest
from diagnostics.jra_official_market_navigation import find_market_links,MarketNavigationError
A="pw154ou1008202604100120261031Z/BB"
B="pw153ou1008202604100120261031Z/37"
def doc(a=A,b=B):
    return ("""<html><title>単勝・複勝オッズ JRA</title><body>
    <a onclick="return doAction('/JRADB/accessO.html', '%s');">馬連</a>
    <a onclick="return doAction('/JRADB/accessO.html', '%s');">枠連</a>
    </body></html>"""%(a,b)).encode("cp932")
class MarketLinks(unittest.TestCase):
 def test_both_official_types(self):
  r=find_market_links(doc(),expected_race_day="20261031",expected_race_number=1)
  self.assertEqual(set(r["markets"]),{"quinella","bracket_quinella"})
  self.assertFalse(r["prices_verified"])
 def test_other_race_is_rejected(self):
  with self.assertRaises(MarketNavigationError):
   find_market_links(doc(),expected_race_day="20261031",expected_race_number=2)
 def test_missing_market_is_rejected(self):
  with self.assertRaises(MarketNavigationError):
   find_market_links(doc(b=""),expected_race_day="20261031",expected_race_number=1)
 def test_mismatched_channel_is_rejected(self):
  with self.assertRaises(MarketNavigationError):
   find_market_links(doc(),expected_race_day="20261031",expected_race_number=1,expected_host="sp.jra.jp")
 def test_conflicting_links_are_rejected(self):
  raw=doc().decode("cp932").replace("</body>",
   """<a onclick="return doAction('/JRADB/accessO.html', 'pw154ou1008202604100120261031Z/AA');">馬連</a></body>""").encode("cp932")
  with self.assertRaises(MarketNavigationError):
   find_market_links(raw,expected_race_day="20261031",expected_race_number=1)
 def test_never_labels_navigation_as_prices(self):
  r=find_market_links(doc(),expected_race_day="20261031",expected_race_number=1)
  self.assertFalse(r["prediction_ready"]);self.assertFalse(r["training_ready"])
if __name__=="__main__":unittest.main()
