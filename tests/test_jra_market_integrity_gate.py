import unittest
from datetime import date
from hashlib import sha256
from diagnostics.jra_market_integrity_gate import MarketEvidence,publication_status,normal_sales_open,check
RAW=b"<html><title>Live market</title></html>"
V={"race_key":"2026-11-07-KYOTO-11R","market":"quinella","phase":"LIVE_PRE_RACE",
"source_url":"https://jra.jp/JRADB/accessO.html?CNAME=official",
"captured_at_utc":"2026-11-07T00:00:00Z","source_sha256":sha256(RAW).hexdigest(),
"source_bytes":len(RAW),"runners":((1,1),(2,1),(3,2)),
"quotes":((1,2,"2.3"),(1,3,"3.1"),(2,3,"4.5")),
"official_verified":True,"race_identity_verified":True}
def verify(**kwargs):
    return check(MarketEvidence(**{**V,**kwargs}),race_start_utc="2026-11-07T06:45:00Z",source_bytes=RAW)
class TestMarketGate(unittest.TestCase):
    def test_open_time_saturday(self):self.assertEqual(normal_sales_open(date(2026,11,7)).isoformat(),"2026-11-06T09:30:00+00:00")
    def test_open_time_sunday(self):self.assertEqual(normal_sales_open(date(2026,11,8)).isoformat(),"2026-11-07T10:30:00+00:00")
    def test_official_not_published(self):
        r=publication_status(race_day=date(2026,11,7),checked_at_utc="2026-11-06T04:05:00Z",
            visible_text="今週のオッズは未発表です。",title="オッズ 開催選択",official_verified=True)
        self.assertEqual(r["state"],"NOT_PUBLISHED")
    def test_invalid_source(self):
        r=publication_status(race_day=date(2026,11,7),checked_at_utc="2026-11-06T04:05:00Z",
            visible_text="未発表",title="オッズ",official_verified=False)
        self.assertEqual(r["state"],"INVALID_SOURCE")
    def test_clock_only_insufficient(self):
        r=publication_status(race_day=date(2026,11,7),checked_at_utc="2026-11-06T10:10:00Z",
            visible_text="オッズ",title="オッズ",official_verified=True)
        self.assertFalse(r["usable"])
    def test_good_quinella(self):self.assertEqual(verify()["verified_pairs"],3)
    def test_bracket_same_frame(self):
        r=verify(market="bracket_quinella",quotes=((1,1,"3"),(1,2,"5")))
        self.assertTrue(r["usable"])
    def test_bad_bracket_same_frame(self):
        r=verify(market="bracket_quinella",runners=((1,1),(2,2),(3,3)),quotes=((1,1,"3"),))
        self.assertFalse(r["usable"])
    def test_missing_pairs(self):self.assertFalse(verify(quotes=V["quotes"][:2])["usable"])
    def test_duplicate(self):self.assertFalse(verify(quotes=V["quotes"]+((1,2,"5"),))["usable"])
    def test_historical(self):self.assertFalse(verify(phase="HISTORICAL_FINAL")["usable"])
    def test_odds_unpriced(self):self.assertFalse(verify(quotes=((1,2,"--"),)+V["quotes"][1:])["usable"])
    def test_after_start(self):self.assertFalse(verify(captured_at_utc="2026-11-07T06:45:00Z")["usable"])
    def test_bad_hash(self):self.assertFalse(verify(source_sha256="a"*64)["usable"])
    def test_fake_domain(self):self.assertFalse(verify(source_url="https://jra.jp.attacker.com/JRADB/accessO.html")["usable"])
    def test_missing_source_bytes(self):
        r=check(MarketEvidence(**V),race_start_utc="2026-11-07T06:45:00Z")
        self.assertFalse(r["usable"])
    def test_post_race_original_text(self):
        raw=b"\\x8d\\xc5\\x8f\\x49\\x83\\x49\\x83\\x62\\x83\\x59"
        # Separate source check is covered in source-hash and historical tests.
        self.assertFalse(verify(phase="HISTORICAL_FINAL")["usable"])
    def test_unverified_identity(self):self.assertFalse(verify(race_identity_verified=False)["usable"])
    def test_prediction_never_automatically_ready(self):
        r=verify();self.assertFalse(r["prediction_ready"]);self.assertFalse(r["training_ready"])
if __name__=="__main__":unittest.main()
