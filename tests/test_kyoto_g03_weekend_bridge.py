"""G03 production bridge: 12 originals, R12 reuse, partial failures and sealing."""
import hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_weekend_capture import capture,seal
from tests.test_kyoto_g03_all_races import meeting,card
DAY="20261121"
URL="https://jra.jp/JRADB/accessD.html?CNAME=pw01dli00%2FF3"

class Bridge(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
        env=patch.dict(os.environ,{"KYOTO_TARGET_DAY":DAY})
        env.start();self.addCleanup(env.stop)

    def observer(self,path,**kw):
        root=Path(path);root.mkdir()
        raw=card(15)
        (root/"official_meeting.html").write_bytes(meeting())
        (root/"official_racecard.html").write_bytes(raw)
        (root/"receipt.json").write_text(json.dumps({
            "day":DAY,"observed_meeting_url":URL,
            "observed_racecard_url":f"https://jra.jp/JRADB/accessD.html?CNAME=pw00test12{DAY}%2FAA",
            "racecard_number":12,"racecard_original_fetched":True,
            "racecard_sha256":hashlib.sha256(raw).hexdigest(),
            "racecard_captured_at_utc":"2026-11-21T01:07:00Z",
            "selection_sha256":"abc"}))
        return {"state":"NOV15_RACECARD_ORIGINAL_OBSERVED_ROSTER_UNVERIFIED",
                "http_requests_started":3,"selection_sha256":"abc"}

    def run_capture(self,broken=False):
        requests=[]
        def fetch(_,url):
            requests.append(url)
            if broken and "test06" in url: raise TimeoutError("injected_failure")
            return card(3+int(url.split("test")[1][:2]))
        with patch("diagnostics.kyoto_nov15_two_original_observer.observe",self.observer),patch(
            "diagnostics.kyoto_g03_weekend_bridge._read",side_effect=fetch),patch(
            "diagnostics.jra_one_shot_market_capture.RequestPacer"):
            result=capture(DAY,"PC",str(self.root/"raw"),live=False,opener=object())
        return result,requests

    def test_all_races_and_existing_aes_gcm(self):
        r,calls=self.run_capture()
        self.assertTrue(r["g03_all_race_originals_observed"])
        self.assertEqual(len(calls),11)
        receipt=json.loads((self.root/"raw"/"g03_receipt.json").read_text())
        self.assertTrue(receipt["complete"])
        self.assertTrue(receipt["race12_original_reused"])
        self.assertEqual(receipt["races"]["12"]["captured_at_utc"],"2026-11-21T01:07:00Z")
        self.assertEqual(len(list((self.root/"raw").glob("g03_official_racecard_*.html"))),12)
        with patch("diagnostics.kyoto_nov15_encrypted_evidence.DAY",DAY):
            seal(DAY,str(self.root/"raw"),str(self.root/"sealed"),key="ab"*32,
                repo="papaneko-ai/kyoto-keiba-ai",run_id="101")
        self.assertFalse((self.root/"raw").exists())
        self.assertTrue((self.root/"sealed"/"originals.tar.gz.aesgcm").is_file())

    def test_missing_one_is_partial_with_originals_preserved(self):
        r,calls=self.run_capture(broken=True)
        self.assertFalse(r["g03_all_race_originals_observed"])
        receipt=json.loads((self.root/"raw"/"g03_receipt.json").read_text())
        self.assertEqual(receipt["missing_races"],[6])
        self.assertTrue((self.root/"raw"/"g03_official_racecard_05.html").is_file())
        self.assertTrue((self.root/"raw"/"g03_official_racecard_07.html").is_file())
