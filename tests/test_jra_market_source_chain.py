"""Synthetic-market integration tests: real data is separately archived."""
import unittest
from diagnostics.jra_market_source_chain import audit_source_originals,SourceChainError
HEAD="2026年11月7日（土曜）5回京都1日 11レース"
def html(title,body,final=False):
    return ("<html><title>"+title+" JRA</title><body>"+HEAD+
       ("最終オッズ" if final else "")+body+"</body></html>").encode("cp932")
TOKEN1="pw154ou1008202605011120261107Z/AA"
TOKEN2="pw153ou1008202605011120261107Z/BB"
MENU=("<a onclick=\"return doAction('/JRADB/accessO.html','"+TOKEN1+"')\">馬連</a>"+
      "<a onclick=\"return doAction('/JRADB/accessO.html','"+TOKEN2+"')\">枠連</a>")
Q="".join('<table class="basic narrow-xy umaren">'+str(i)+" "+
          " ".join(f"{j} 3.0" for j in range(i+1,7))+"</table>" for i in range(1,6))
B='<table class="basic narrow-xy waku">1 2.0 2 4.0 3 5.0</table><table class="basic narrow-xy waku">2 3.0 3 5.0</table><table class="basic narrow-xy waku">3 4.0</table>'
RUNNERS=((1,1),(2,1),(3,2),(4,2),(5,3),(6,3))
def run(final=False,late=False,wrong_date=False):
 return audit_source_originals(
   html("単勝・複勝オッズ",MENU,final),
   {"quinella":html("馬連オッズ",Q,final),
    "bracket_quinella":html("枠連オッズ",B,final)},
   {"quinella":"https://jra.jp/JRADB/accessO.html",
    "bracket_quinella":"https://jra.jp/JRADB/accessO.html"},
   race_key="2026-11-07_KYOTO_11R",race_day="20261108" if wrong_date else "20261107",
   venue="京都",race_number=11,channel="PC",
   captured_at_utc="2026-11-07T07:00:00Z" if late else "2026-11-07T00:00:00Z",
   verified_start_utc="2026-11-07T06:45:00Z",
   active_runners=RUNNERS,historical=final)
class Chain(unittest.TestCase):
 def test_two_markets_parsed(self):
  x=run();self.assertEqual(x["markets"]["quinella"]["pair_count"],15)
  self.assertEqual(x["markets"]["bracket_quinella"]["pair_count"],6)
 def test_live_source_validated_but_not_prediction(self):
  x=run();self.assertEqual(x["classification"],"VALIDATED_LIVE_MARKETS_NOT_PREDICTION_RELEASED")
  self.assertFalse(x["prediction_ready"])
 def test_historical_quarantine(self):
  x=run(final=True);self.assertEqual(x["classification"],"QUARANTINED_HISTORICAL_FINAL")
  self.assertFalse(x["markets"]["quinella"]["pre_race_usable"])
 def test_post_start_blocks(self):
  self.assertEqual(run(late=True)["classification"],"BLOCKED_SOURCE_INTEGRITY")
 def test_wrong_race_date_blocks(self):
  with self.assertRaises(SourceChainError):run(wrong_date=True)
 def test_determinism(self):
  self.assertEqual(run(),run())
if __name__=="__main__":unittest.main()
