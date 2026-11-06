import copy,json,unittest
from pathlib import Path
from diagnostics.jra_live_odds_readiness import accept,ROOT,MENU,LINKS
class RealOfficialOddsReceiptTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.menu=json.loads(MENU.read_text(encoding="utf8"))
  cls.links=json.loads(LINKS.read_text(encoding="utf8"))
 def test_genuine_pc_and_sp_not_published(self):
  r=accept(self.menu,self.links)
  self.assertEqual(r["status"],"OFFICIAL_UNPUBLISHED_CONFIRMED")
  self.assertEqual({x["status"] for x in r["source_channels"]},{"NOT_PUBLISHED"})
 def test_not_price_verified(self):
  r=accept(self.menu,self.links)
  self.assertFalse(r["pre_race_odds_available"])
  self.assertFalse(r["prediction_ready"])
 def test_explicit_next_market_time(self):
  self.assertEqual(accept(self.menu,self.links)["normal_sale_start_utc"],
    "2026-11-06T09:30:00+00:00")
 def test_no_stale_result_contamination(self):
  self.assertTrue(accept(self.menu,self.links)["historical_final_as_prerace_forbidden"])
 def test_wrong_identity_fails_closed(self):
  x=copy.deepcopy(self.menu);x["race"]="2026-11-07-KYOTO-10R"
  with self.assertRaises(ValueError):accept(x,self.links)
 def test_missing_mobile_channel_fails(self):
  x=copy.deepcopy(self.menu);x["sources"]=x["sources"][:1]
  with self.assertRaises(ValueError):accept(x,self.links)
 def test_missing_origin_hash_fails(self):
  x=copy.deepcopy(self.menu);x["sources"][0]["content_sha256"]=""
  with self.assertRaises(ValueError):accept(x,self.links)
 def test_deterministic(self):
  self.assertEqual(accept(self.menu,self.links),accept(self.menu,self.links))
if __name__=="__main__":unittest.main()
