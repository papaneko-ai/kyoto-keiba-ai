import json
import tempfile
import unittest
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
from types import SimpleNamespace
from diagnostics.kyoto_g06_market_link_evidence import observed_market_links

SPEC=SimpleNamespace(race_id="RACE1",race_day="20261121",venue="京都",race_number=1)
START="2026-11-21T06:00:00Z"
RAW=b"<html><title>odds</title><body>sample</body></html>"
class Tests(unittest.TestCase):
    def build(self,d,channel="PC",raw=RAW,timestamp="2026-11-21T02:00:00Z",state="CAPTURE_BLOCKED"):
        folder=Path(d)/channel.lower()
        folder.mkdir()
        (folder/"official_odds_menu.html").write_bytes(raw)
        receipt={"channel":channel,"race_id":"RACE1","state":state,"request_receipts":[
            {"step":"odds_menu","bytes":len(raw),"sha256":sha256(raw).hexdigest(),
             "captured_at_utc":timestamp}]}
        (folder/"receipt.json").write_text(json.dumps(receipt))
        return folder
    def test_no_receipt_does_not_count_racecard_url(self):
        with tempfile.TemporaryDirectory() as d:
            x=observed_market_links(d,race_spec=SPEC,verified_start_utc=START)
            self.assertFalse(x["PC"]["observed"])
            self.assertFalse(x["SP"]["observed"])
    def test_proven_menu_allows_observed_route(self):
        with tempfile.TemporaryDirectory() as d:
            self.build(d)
            valid={"source_final_odds_detected":False,"markets":{
                "quinella":{"cname_sha256":"a","official_post_url":"https://jra.jp/JRADB/accessO.html"},
                "bracket_quinella":{"cname_sha256":"b","official_post_url":"https://jra.jp/JRADB/accessO.html"}}}
            with patch("diagnostics.kyoto_g06_market_link_evidence._html_race_identity",return_value=True),patch("diagnostics.kyoto_g06_market_link_evidence.find_market_links",return_value=valid):
                x=observed_market_links(d,race_spec=SPEC,verified_start_utc=START)
                self.assertTrue(x["PC"]["observed"])
                self.assertFalse(x["SP"]["observed"])
    def test_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            folder=self.build(d)
            (folder/"official_odds_menu.html").write_bytes(b"not same")
            self.assertFalse(observed_market_links(d,race_spec=SPEC,verified_start_utc=START)["PC"]["observed"])
    def test_after_start_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            self.build(d,timestamp="2026-11-21T06:10:00Z")
            self.assertFalse(observed_market_links(d,race_spec=SPEC,verified_start_utc=START)["PC"]["observed"])
    def test_final_odds_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            self.build(d,state="REJECT_FINAL_ODDS")
            self.assertFalse(observed_market_links(d,race_spec=SPEC,verified_start_utc=START)["PC"]["observed"])
    def test_wrong_race_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            folder=self.build(d)
            r=json.loads((folder/"receipt.json").read_text())
            r["race_id"]="OTHER"
            (folder/"receipt.json").write_text(json.dumps(r))
            self.assertFalse(observed_market_links(d,race_spec=SPEC,verified_start_utc=START)["PC"]["observed"])
if __name__=="__main__": unittest.main()
