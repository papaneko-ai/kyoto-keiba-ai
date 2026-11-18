"""Pre-event SP whole transport path, independent of any configured R12 URL.

The URLs below are mock *HTML anchors*, never deployed or used on the web.
"""
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs
from unittest.mock import Mock
from diagnostics.kyoto_weekend_sp_discovery import discover,SEED
from diagnostics.kyoto_sp_observed_source import capture_verified_sp_seed

def html(body):return ("<html><body>"+body+"</body></html>").encode("cp932")
class Reply:
    status=200
    headers={"Content-Type":"text/html; charset=Shift_JIS"}
    def __init__(self,url,raw):self.url=url;self.raw=raw
    def geturl(self):return self.url
    def read(self,n):return self.raw[:n]
    def __enter__(self):return self
    def __exit__(self,*a):return False
class Client:
    def __init__(self,day,complete=True):
        self.day=day;self.complete=complete;self.calls=[]
        self.meeting=f"https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01meet{day}%2FAA"
        self.race=f"https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01race12{day}%2FBB"
    def open(self,req,timeout=12):
        url=req.full_url
        post=parse_qs((req.data or b"").decode()).get("cname",[None])[0]
        self.calls.append((url,post))
        if url==SEED:
            return Reply(url,html(f'<a href="{self.meeting}">京都 開催 {self.day}</a>'))
        if url==self.meeting:
            anchors=f'<a href="{self.race}">京都 12R</a>' if self.complete else "<p>未掲載</p>"
            return Reply(url,html(anchors))
        if url==self.race:
            return Reply(url,html(
                f'<a onclick="doAction(\'/JRADB/accessO.html\',\'sw01oddsmenu{self.day}/AA\')">オッズ</a>'))
        if url=="https://sp.jra.jp/JRADB/accessO.html":
            if post and post.startswith("sw01oddsmenu"):
                return Reply(url,html(
                    f'<a onclick="doAction(\'/JRADB/accessO.html\',\'sw01market12{self.day}/AA\')">馬連</a>'+
                    f'<a onclick="doAction(\'/JRADB/accessO.html\',\'sw01bracket12{self.day}/BB\')">枠連</a>'))
            return Reply(url,html("市場原本（模擬）"))
        raise AssertionError("unobserved_or_invalid_url")
class SPIntegrated(unittest.TestCase):
    def test_both_days_independent_sp_discovery_to_paired_market_transport(self):
        for day in ("20261121","20261122"):
            with self.subTest(day=day),tempfile.TemporaryDirectory() as td:
                client=Client(day);pacer=Mock()
                first=discover(Path(td)/"discovery",day=day,opener=client,pacer=pacer)
                self.assertEqual(first["racecard_url"],client.race)
                self.assertTrue(first["not_pc_derived"])
                (Path(td)/"source").mkdir()
                item=capture_verified_sp_seed(Path(td)/"source",race_day=day,
                    race_number=12,source_url=first["racecard_url"],
                    opener=client,pacer=pacer,include_odds=True)
                self.assertEqual(item["sp_market_state"],
                                 "BOTH_RAW_MARKET_ORIGINALS_CAPTURED_UNVALIDATED")
                self.assertTrue((Path(td)/"source"/"official_sp_quinella_odds.html").is_file())
                self.assertTrue((Path(td)/"source"/"official_sp_bracket_quinella_odds.html").is_file())
                self.assertEqual(sum(1 for _,token in client.calls if token is not None),3)
                self.assertEqual(client.calls[0][0],SEED)
                self.assertEqual(client.calls[1][0],client.meeting)
                self.assertEqual(client.calls[2][0],client.race)
                self.assertFalse(item["sp_odds_originals_verified"])
    def test_link_not_observed_does_not_make_up_racecard(self):
        with tempfile.TemporaryDirectory() as td:
            client=Client("20261121",complete=False)
            found=discover(Path(td)/"discovery",day="20261121",
                           opener=client,pacer=Mock())
            self.assertFalse(found["racecard_url"])
            self.assertEqual(len(client.calls),2)
    def test_never_derives_sp_link_from_pc(self):
        with tempfile.TemporaryDirectory() as td:
            client=Client("20261122",complete=True)
            found=discover(Path(td)/"discovery",day="20261122",opener=client,pacer=Mock())
            self.assertEqual(found["racecard_url"],client.race)
            self.assertTrue(all(not x[0].startswith("https://jra.jp/") for x in client.calls))
if __name__=="__main__":unittest.main()
