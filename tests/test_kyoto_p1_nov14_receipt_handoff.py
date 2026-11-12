"""Offline receipt/original handoff: detect tampering and never invent live proof."""
import json
import tempfile
import unittest
from pathlib import Path
from hashlib import sha256
from diagnostics.kyoto_p1_nov14_official_one_shot_nav import (
    SOURCE, strict_link_from_official)
from diagnostics.kyoto_p1_nov14_receipt_handoff import assess_saved_selection, HandoffRejected

GOOD=('<html><title>JRA</title><body>'
      '<a href="/JRADB/accessD.html?CNAME=pw01dde0108202605030720261114%2FAA">'
      '5回京都3日</a></body></html>').encode("cp932")

def evidence(root, raw=GOOD, *, status=None):
    summary=strict_link_from_official(raw)
    receipt={
        "schema":"kyoto_jra_20261114_kyoto_navigation_one_off.v1",
        "origin":"JRA_OFFICIAL_PC_SELECTION","source_url":SOURCE,
        "attempted_GET":1,"status":status or summary["status"],
        "started_utc":"2026-11-12T08:00:00+00:00",
        "completed_utc":"2026-11-12T08:00:02+00:00",
        "source_sha256":sha256(raw).hexdigest(),"source_bytes":len(raw),
        "current_meeting_racecards_verified":False,
        "current_prerace_market_verified":False,"paper_trade_authorized":False,
        "observed_links":summary["observed_links"],
    }
    (root/"receipt.json").write_text(json.dumps(receipt),encoding="utf8")
    (root/"official_selection.html").write_bytes(raw)
    return receipt

class MeetingHandoffTests(unittest.TestCase):
    def test_real_original_bound_to_observed_meeting(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);evidence(p)
            r=assess_saved_selection(p)
            self.assertEqual(r["state"],"OFFICIAL_MEETING_LINK_OBSERVED_NOT_RACECARD")
            self.assertEqual(r["official_meeting_url"],"https://jra.jp/JRADB/accessD.html?CNAME=pw01dde0108202605030720261114%2FAA")
            self.assertFalse(r["racecard_verified"])
            self.assertFalse(r["prerace_markets_verified"])
            self.assertEqual(r["network_requests"],0)
    def test_tampered_html_hash_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);evidence(p)
            (p/"official_selection.html").write_bytes(GOOD+b"x")
            with self.assertRaisesRegex(HandoffRejected,"digest"):assess_saved_selection(p)
    def test_claims_inflated_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);r=evidence(p)
            r["current_prerace_market_verified"]=True
            (p/"receipt.json").write_text(json.dumps(r),encoding="utf8")
            with self.assertRaisesRegex(HandoffRejected,"claims"):assess_saved_selection(p)
    def test_wrong_date_html_cannot_claim_observed(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);r=evidence(p,GOOD.replace(b"20261114",b"20261115"))
            r["status"]="OFFICIAL_NOV14_KYOTO_MEETING_LINK_OBSERVED"
            (p/"receipt.json").write_text(json.dumps(r),encoding="utf8")
            with self.assertRaisesRegex(HandoffRejected,"claims"):assess_saved_selection(p)
    def test_unpublished_original_never_guesses_meeting(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);evidence(p,b"<html><title>JRA</title></html>")
            r=assess_saved_selection(p)
            self.assertEqual(r["state"],"OFFICIAL_LINK_NOT_YET_PUBLISHED_SAFE_STOP")
            self.assertIsNone(r["official_meeting_url"])
    def test_missing_original_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);evidence(p);(p/"official_selection.html").unlink()
            with self.assertRaises(HandoffRejected):assess_saved_selection(p)
    def test_zero_http_no_original_safe_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            (p/"receipt.json").write_text(json.dumps({
              "schema":"kyoto_jra_20261114_kyoto_navigation_one_off.v1",
              "origin":"JRA_OFFICIAL_PC_SELECTION","source_url":SOURCE,
              "attempted_GET":0,"status":"WAIT_FOR_JRA_OFFICIAL_PUBLICATION_NO_HTTP"
            }),encoding="utf8")
            r=assess_saved_selection(p)
            self.assertEqual(r["state"],"NO_OFFICIAL_ORIGINAL_SAFE_STOP")
    def test_zero_http_cannot_fake_original(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            (p/"receipt.json").write_text(json.dumps({
              "schema":"kyoto_jra_20261114_kyoto_navigation_one_off.v1",
              "origin":"JRA_OFFICIAL_PC_SELECTION","source_url":SOURCE,
              "attempted_GET":0,"status":"WAIT_FOR_JRA_OFFICIAL_PUBLICATION_NO_HTTP"
            }),encoding="utf8")
            (p/"official_selection.html").write_bytes(GOOD)
            with self.assertRaises(HandoffRejected):assess_saved_selection(p)
    def test_source_outside_publication_window_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);r=evidence(p)
            r["started_utc"]="2026-11-12T04:00:00+00:00"
            (p/"receipt.json").write_text(json.dumps(r),encoding="utf8")
            with self.assertRaises(HandoffRejected):assess_saved_selection(p)
    def test_duplicate_link_cannot_promote(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);evidence(p)
            (p/"official_selection.html").write_bytes(GOOD.replace(b"</body>",b'<a href="/JRADB/accessD.html?CNAME=pw01dde0108202605030720261114%2FBB">5\x89\xf1\x8b\x9e\x93s3\x93\xfa</a></body>'))
            with self.assertRaises(Exception):assess_saved_selection(p)

if __name__=="__main__":unittest.main()
