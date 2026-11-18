import unittest
from diagnostics.kyoto_g06_twelve_race_dual_market_gate import audit_twelve_races,G06Incomplete
DAY="20261121"
T="2026-11-21T01:00:00Z"
def html(market,r,final=False):
    name="馬連オッズ" if market=="quinella" else "枠連オッズ"
    css="umaren" if market=="quinella" else "waku"
    rows=([str(i)+" "+" ".join(f"{j} 3.0" for j in range(i+1,7)) for i in range(1,6)] if market=="quinella"
        else ["1 2.1 2 8.8 3 7.3","2 3.0 3 2.6","3 4.4"])
    tables="".join(f'<table class="basic narrow-xy {css}">{line}</table>' for line in rows)
    return (f"<html><title>{name} JRA</title><body>2026年11月21日 京都 {r}レース "+
        ("最終オッズ" if final else "発売中")+tables+"</body></html>").encode("cp932")
def fixture(r,final=False):
    menus=''.join(f"""<a onclick="return doAction('/JRADB/accessO.html','pw{tag}{r:02d}{DAY}A/AA')">{name}</a>"""
          for tag,name in (("15","馬連"),("07","枠連")))
    menu=(f"<html><title>JRA オッズ</title><body>2026年11月21日 京都 {r}レース "+
          ("最終オッズ" if final else "発売中")+menus+"</body></html>").encode("cp932")
    return dict(menu_raw=menu,market_raw={m:html(m,r,final) for m in
         ("quinella","bracket_quinella")},market_urls={m:"https://jra.jp/JRADB/accessO.html"
         for m in ("quinella","bracket_quinella")},race_key=f"20261121-KYOTO-{r:02d}",
         race_day=DAY,venue="京都",race_number=r,channel="PC",captured_at_utc=T,
         verified_start_utc="2026-11-21T04:00:00Z",
         active_runners=((1,1),(2,1),(3,2),(4,2),(5,3),(6,3)),
         historical=final,market_captured_at_utc={"quinella":T,"bracket_quinella":T})
def all_races(final=False):return {i:fixture(i,final) for i in range(1,13)}
class Batch(unittest.TestCase):
    def test_twelve_both_markets_structural(self):
        d=audit_twelve_races(all_races(),provenance="SYNTHETIC_OFFLINE_TEST",expected_day=DAY)
        self.assertEqual(d["live_source_validated_count"],12)
        self.assertFalse(d["g06_certified"])
    def test_all_final_rejected_for_prerace(self):
        d=audit_twelve_races(all_races(True),provenance="SYNTHETIC_OFFLINE_TEST",expected_day=DAY)
        self.assertEqual(d["historical_final_quarantined_count"],12)
        self.assertEqual(d["live_source_validated_count"],0)
    def test_missing_race(self):
        d=all_races();del d[4]
        with self.assertRaises(G06Incomplete):audit_twelve_races(d,provenance="SYNTHETIC_OFFLINE_TEST",expected_day=DAY)
    def test_missing_market(self):
        d=all_races();del d[1]["market_raw"]["quinella"]
        with self.assertRaises(G06Incomplete):audit_twelve_races(d,provenance="SYNTHETIC_OFFLINE_TEST",expected_day=DAY)
    def test_after_start(self):
        d=all_races();d[7]["market_captured_at_utc"]["quinella"]="2026-11-21T05:00:00Z"
        result=audit_twelve_races(d,provenance="SYNTHETIC_OFFLINE_TEST",expected_day=DAY)
        self.assertNotEqual(result["races"][6]["classification"],"VALIDATED_LIVE_MARKETS_NOT_PREDICTION_RELEASED")
    def test_real_claim_not_certified(self):
        d=audit_twelve_races(all_races(),provenance="REAL_ARCHIVED_ORIGINAL",expected_day=DAY)
        self.assertFalse(d["evidence_independently_verified"])
if __name__=="__main__":unittest.main()
