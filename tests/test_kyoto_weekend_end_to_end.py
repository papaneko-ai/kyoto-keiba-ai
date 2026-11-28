"""Zero-JRA-HTTP end-to-end rehearsal: capture -> SHA/UTC -> seal -> decrypt."""
import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, Mock
from diagnostics.kyoto_weekend_capture import capture,seal
from diagnostics.kyoto_weekend_postflight import check_originals
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence

DAY="20261121"
PC_SELECTION="https://jra.jp/JRADB/accessD.html?CNAME=pw01dli00%2FF3"
PC_MEETING="https://jra.jp/JRADB/accessD.html?CNAME=pw01meet20261121%2FA1"
SP_RACE="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01race1220261121%2FBB"
KYOTO_TRACK="https://www.jra.go.jp/keiba/baba/index2.html"

class FixedDate(datetime):
    @classmethod
    def now(cls, tz=None):
        current=datetime(2026,11,21,2,10,tzinfo=timezone.utc)
        return current.astimezone(tz) if tz is not None else current.replace(tzinfo=None)

class Response:
    status=200
    headers={"Content-Type":"text/html; charset=Shift_JIS"}
    def __init__(self, url,raw): self.url=url;self.raw=raw
    def geturl(self): return self.url
    def read(self,n):return self.raw[:n]
    def __enter__(self):return self
    def __exit__(self,*a):return False

class OfflineClient:
    def __init__(self,files): self.files=files;self.requests=[]
    def open(self,req,timeout=12):
        url=req.full_url
        self.requests.append(url)
        if url not in self.files:raise AssertionError("unexpected_network_path")
        return Response(url,self.files[url])

def raw_html(x):return ("<html><body>"+x+"</body></html>").encode("cp932")

class WeekendEndToEndTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        env=patch.dict(os.environ,{"KYOTO_TARGET_DAY":DAY},clear=False)
        env.start()
        self.addCleanup(env.stop)
        crypto=patch("diagnostics.kyoto_nov15_encrypted_evidence.DAY",DAY)
        crypto.start()
        self.addCleanup(crypto.stop)

    def _seal_reopen(self,lane,originals):
        report=check_originals(originals,day=DAY,channel=lane)
        self.assertTrue(report["source_verified"],report)
        self.assertFalse(report["prediction_ready"])
        (originals/"source_verification.json").write_text(json.dumps(report))
        dest=self.root/(lane+"_sealed")
        seal(DAY,str(originals),str(dest),key="ab"*32,
             repo="papaneko-ai/kyoto-keiba-ai",run_id="101")
        self.assertFalse(originals.exists())
        self.assertFalse((dest/"official_selection.html").exists())
        decoded=self.root/(lane+"_decoded")
        evidence=decrypt_evidence(dest,decoded,key_hex="ab"*32,
                 repo="papaneko-ai/kyoto-keiba-ai",run_id="101")
        self.assertTrue(evidence["authentication_tag_verified"])
        self.assertEqual(json.loads((decoded/"source_verification.json").read_text())["source_verified"],True)
        return decoded

    def test_pc_actual_observer_parses_originals_then_audits_and_seals(self):
        selection=raw_html('<a href="'+PC_MEETING.replace("https://jra.jp","")+'">京都 20261121</a>')
        meeting=raw_html("<p>京都 12R 出馬表未掲載</p>")
        client=OfflineClient({PC_SELECTION:selection,PC_MEETING:meeting,
                              KYOTO_TRACK:raw_html("unverified meeting heading")})
        with patch("diagnostics.kyoto_weekend_capture.datetime",FixedDate),patch(
                "diagnostics.kyoto_nov15_two_original_observer.RequestPacer",return_value=Mock()):
            result=capture(DAY,"PC",str(self.root/"pc"),live=False,opener=client)
        self.assertEqual(client.requests,[PC_SELECTION,PC_MEETING,KYOTO_TRACK])
        self.assertTrue(result["g05_kyoto_track_source_saved"])
        self.assertFalse(result["g05_same_day_track_heading_verified"])
        self.assertEqual(result["observed_http_requests_started"],2)
        decoded=self._seal_reopen("PC",self.root/"pc")
        self.assertEqual((decoded/"official_selection.html").read_bytes(),selection)
        self.assertEqual((decoded/"official_meeting.html").read_bytes(),meeting)
        self.assertFalse(result["both_markets_verified"])

    def test_sp_exact_official_source_produces_independent_receipts(self):
        client=OfflineClient({SP_RACE:raw_html("synthetic SP race source")})
        with patch("diagnostics.kyoto_sp_observed_source.RequestPacer",return_value=Mock()):
            result=capture(DAY,"SP",str(self.root/"sp"),live=False,
                           opener=client,sp_source_url=SP_RACE)
        self.assertEqual(client.requests,[SP_RACE])
        self.assertEqual(result["observed_http_requests_started"],1)
        decoded=self._seal_reopen("SP",self.root/"sp")
        self.assertEqual((decoded/"official_sp_racecard.html").read_bytes(),client.files[SP_RACE])
        self.assertFalse(result["both_markets_verified"])

if __name__=="__main__":
    unittest.main()
