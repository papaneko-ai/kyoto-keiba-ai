"""SP all-12 racewise capture: zero network fixtures, failure isolation and AES."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from diagnostics.kyoto_sp_all12_observed_capture import capture_all
from diagnostics.kyoto_weekend_sp_discovery import SEED

DAY="20261121"
def link(n):
    return f"https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01race{n:02d}{DAY}%2FAA"

class SPAll12(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"source"
        self.root.mkdir()

    def prepare(self,numbers=range(1,13),tamper=False):
        raw=("<html>"+''.join(f'<a href="{link(n)}">京都 {n}R</a>' for n in numbers)+"</html>").encode("cp932")
        (self.root/"official_sp_discovery_1.html").write_bytes(raw+(b"X" if tamper else b""))
        (self.root/"sp_discovery_receipt.json").write_text(json.dumps({
            "day":DAY,"attempts":[{"url":SEED,"file":"official_sp_discovery_1.html",
                                  "sha256":hashlib.sha256(raw).hexdigest()}]}))

    def test_saved_twelve_races_and_aes_roundtrip(self):
        import os
        from diagnostics.kyoto_weekend_capture import seal
        from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
        self.prepare()
        def fake(out,*,race_number,source_url,**kw):
            self.assertEqual(source_url,link(race_number))
            (Path(out)/"official_sp_racecard.html").write_bytes(f"saved_{race_number}".encode())
            return {"state":"SP_ORIGINAL_CAPTURED_NOT_ROSTER_VERIFIED","racecard_fetched":True}
        with patch("diagnostics.kyoto_sp_all12_observed_capture.capture_verified_sp_seed",side_effect=fake):
            receipt=capture_all(self.root,day=DAY,opener=object(),pacer=Mock())
        self.assertEqual(sum(v.get("racecard_fetched",False) for v in receipt["races"].values()),12)
        self.assertFalse(receipt["all_twelve_races_verified"])
        with patch.dict(os.environ,{"KYOTO_TARGET_DAY":DAY}):
            encrypted=self.root.parent/"encrypted"
            seal(DAY,str(self.root),str(encrypted),key="ab"*32,
                 repo="papaneko-ai/kyoto-keiba-ai",run_id="123")
            restored=self.root.parent/"restored"
            decrypt_evidence(encrypted,restored,key_hex="ab"*32,
                             repo="papaneko-ai/kyoto-keiba-ai",run_id="123")
        for n in range(1,13):
            self.assertEqual((restored/f"r{n:02d}_official_sp_racecard.html").read_bytes(),
                             f"saved_{n}".encode())

    def test_time_budget_defers_without_dropping_saved_originals(self):
        self.prepare()
        called=[]
        def fake(out,*,race_number,**kw):
            called.append(race_number)
            (Path(out)/"official_sp_racecard.html").write_bytes(b"saved")
            return {"state":"CAPTURED","racecard_fetched":True}
        ticks=iter([0.0,1.0,500.0]+[500.0]*9)
        with patch("diagnostics.kyoto_sp_all12_observed_capture.capture_verified_sp_seed",side_effect=fake):
            report=capture_all(self.root,day=DAY,opener=object(),pacer=Mock(),
                               deadline_monotonic=240.0,monotonic=lambda:next(ticks))
        self.assertEqual(called,[1,2])
        self.assertEqual(report["races"]["3"]["state"],"DEFERRED_FOR_AES_SEALING_BUDGET")
        self.assertTrue((self.root/"r01_official_sp_racecard.html").is_file())

    def test_one_race_failure_preserves_other_races(self):
        self.prepare([1,2,3])
        called=[]
        def fake(out,*,race_number,**kw):
            called.append(race_number)
            if race_number==2:
                raise RuntimeError("simulated")
            (Path(out)/"official_sp_racecard.html").write_bytes(b"saved")
            return {"state":"CAPTURED","racecard_fetched":True}
        with patch("diagnostics.kyoto_sp_all12_observed_capture.capture_verified_sp_seed",side_effect=fake):
            result=capture_all(self.root,day=DAY,opener=object(),pacer=Mock())
        self.assertEqual(called,[1,2,3])
        self.assertEqual(result["races"]["2"]["state"],"SP_RACE_EXCEPTION")
        self.assertTrue((self.root/"r03_official_sp_racecard.html").is_file())

    def test_tampering_stops_all_requests(self):
        self.prepare(tamper=True)
        with patch("diagnostics.kyoto_sp_all12_observed_capture.capture_verified_sp_seed") as fetch:
            with self.assertRaisesRegex(ValueError,"discovery_original_sha_mismatch"):
                capture_all(self.root,day=DAY,opener=object(),pacer=Mock())
            fetch.assert_not_called()

    def test_ambiguous_anchor_skipped(self):
        self.prepare([1,3])
        raw=(f'<a href="{link(1)}">京都 1R</a>'
             f'<a href="{link(1).replace("%2FAA","%2FBB")}">京都 1R</a>'
             f'<a href="{link(3)}">京都 3R</a>').encode("cp932")
        (self.root/"official_sp_discovery_1.html").write_bytes(raw)
        receipt=json.loads((self.root/"sp_discovery_receipt.json").read_text())
        receipt["attempts"][0]["sha256"]=hashlib.sha256(raw).hexdigest()
        (self.root/"sp_discovery_receipt.json").write_text(json.dumps(receipt))
        with patch("diagnostics.kyoto_sp_all12_observed_capture.capture_verified_sp_seed",return_value={"state":"CAPTURED"}) as fetch:
            result=capture_all(self.root,day=DAY,opener=object(),pacer=Mock())
        self.assertEqual(result["races"]["1"]["candidate_count"],2)
        self.assertEqual(fetch.call_count,1)

class WeekendSPTransport(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.day="20261128"
        self.urls=[f"https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01race{n:02d}{self.day}%2FAA" for n in range(1,4)]
        raw=("<html>"+"".join(f'<a href="{url}">京都 {n}R</a>' for n,url in enumerate(self.urls,1))+"</html>").encode("cp932")
        (self.root/"official_sp_discovery_1.html").write_bytes(raw)
        (self.root/"sp_discovery_receipt.json").write_text(json.dumps({"day":self.day,"attempts":[{"url":SEED,"file":"official_sp_discovery_1.html","sha256":hashlib.sha256(raw).hexdigest()}]}))

    def test_terminal_market_response_stops_next_races_and_preserves_card(self):
        from urllib.error import HTTPError
        from urllib.parse import parse_qs
        day=self.day
        raw=(f'<html><a onclick="doAction(\'/JRADB/accessO.html\',\'sw01oddsmenu{day}/AA\')">オッズ</a></html>').encode("cp932")
        menu=(f'<html><title>オッズ</title><a onclick="doAction(\'/JRADB/accessO.html\',\'sw01market01{day}/AA\')">馬連</a><a onclick="doAction(\'/JRADB/accessO.html\',\'sw01bracket01{day}/BB\')">枠連</a></html>').encode("cp932")
        calls=[]
        class Reply:
            status=200;headers={"Content-Type":"text/html"}
            def __init__(self,url,body):self.url=url;self.body=body
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def geturl(self):return self.url
            def read(self,n):return self.body
        class Opener:
            def open(self,request,timeout):
                token=parse_qs((request.data or b"").decode()).get("cname",[None])[0];calls.append((request.full_url,token))
                if token and "market01" in token:raise HTTPError(request.full_url,429,"limited",{},None)
                return Reply(request.full_url,menu if token else raw)
        r=capture_all(self.root,day=day,opener=Opener(),pacer=Mock())
        self.assertEqual(len(calls),3)
        self.assertEqual(r["races"]["1"]["network_requests_started"],3)
        self.assertEqual(r["races"]["2"]["state"],"SP_BATCH_TERMINAL_HTTP_STOP")
        self.assertEqual(r["races"]["3"]["network_requests_started"],0)
        self.assertEqual((self.root/"r01_official_sp_racecard.html").read_bytes(),raw)
        self.assertEqual((self.root/"r01_official_sp_odds_menu.html").read_bytes(),menu)
        self.assertFalse((self.root/"r02_official_sp_racecard.html").exists())

    def test_deadline_rechecked_after_pacing(self):
        from urllib.request import Request
        from diagnostics.kyoto_sp_all12_observed_capture import _SPTransportBoundary
        client=Mock();tick=[100.0]
        guard=_SPTransportBoundary(client,105.0,lambda:tick[0])
        tick[0]=105.0
        with self.assertRaisesRegex(RuntimeError,"deadline"):
            guard.open(Request(self.urls[0]),timeout=20)
        client.open.assert_not_called();self.assertEqual(guard.requests_started,0)
        self.assertEqual(guard.stop_reason,"DEADLINE")

    def test_transient_error_does_not_stop_other_races(self):
        from urllib.error import HTTPError
        calls=[]
        class Opener:
            def open(self,request,timeout):
                calls.append(request.full_url)
                raise HTTPError(request.full_url,503,"temporary",{},None)
        r=capture_all(self.root,day=self.day,opener=Opener(),pacer=Mock())
        self.assertEqual(calls,self.urls)
        self.assertEqual(sum(x["network_requests_started"] for x in r["races"].values()),3)
        self.assertTrue(all(r["races"][str(n)]["state"]=="SP_HTTP_FAILED" for n in range(1,4)))

if __name__=="__main__":
    unittest.main()
