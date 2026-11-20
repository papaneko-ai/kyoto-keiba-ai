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

if __name__=="__main__":
    unittest.main()
