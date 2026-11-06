import unittest
from diagnostics.jra_official_odds_chain import audit
A="pw154ou1008202604100120261031Z/BB"
B="pw153ou1008202604100120261031Z/37"
def raw_market(title,kind,rows,final=False):
    text="<p>最終オッズ</p>" if final else ""
    return ('<html><title>'+title+'</title><body>'+text+
      ''.join('<table class="basic narrow-xy '+kind+'">'+r+'</table>' for r in rows)+
      '</body></html>').encode("cp932")
def menu(final=False):
    text="<p>最終オッズ</p>" if final else ""
    return ("""<html><title>単勝・複勝オッズ JRA</title><body>"""+text+
      """<a onclick="return doAction('/JRADB/accessO.html', '"""+A+"""');">馬連</a>
      <a onclick="return doAction('/JRADB/accessO.html', '"""+B+"""');">枠連</a>
      </body></html>""").encode("cp932")
def run(final=False):
    return audit(menu(final),raw_market("馬連オッズ","umaren",
      ["1 2 2.0 3 5.0","2 3 4.0"],final),
      raw_market("枠連オッズ","waku",["1 2.2 2 4.4","2 3.3"],final),
      date="20261031",race=1,runners=3)
class OfflineMarketChain(unittest.TestCase):
 def test_parsed_both_market_types(self):
  x=run();self.assertEqual(x["markets"]["quinella"]["pair_count"],3)
  self.assertEqual(x["markets"]["bracket_quinella"]["pair_count"],3)
 def test_final_odds_are_quarantined(self):
  x=run(True)
  self.assertEqual(x["state"],"QUARANTINED_FINAL_ODDS")
  self.assertFalse(x["prediction_ready"])
 def test_nonfinal_still_not_verified_for_prediction(self):
  x=run();self.assertEqual(x["state"],"MATRIX_PARSED_PHASE_UNVERIFIED")
  self.assertFalse(x["prediction_ready"])
 def test_phase_conflict_fails_closed(self):
  with self.assertRaises(ValueError):
   audit(menu(True),raw_market("馬連オッズ","umaren",
       ["1 2 2.0 3 5.0","2 3 4.0"],False),
       raw_market("枠連オッズ","waku",["1 2.2 2 4.4","2 3.3"],True),
       date="20261031",race=1,runners=3)
if __name__=="__main__":unittest.main()
