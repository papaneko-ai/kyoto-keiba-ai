"""Destructive archive tests: never promote copied/offline source to live odds."""
import hashlib
import io
import json
import unittest
import zipfile
from diagnostics.kyoto_p1_nov14_official_one_shot_nav import SOURCE,strict_link_from_official
from diagnostics.p8_official_source_status import (
    inspect_official_selection_archive, inspect_recorded_link_alert, SourceStatusRejected
)

GOOD=('<html><title>JRA</title><body>'
      '<a href="/JRADB/accessD.html?CNAME=pw01dde0108202605030720261114%2FAA">'
      '5回京都3日</a></body></html>').encode("cp932")

def payload(*,raw=GOOD,change=None,symlink=False,include_original=True):
    parsed=strict_link_from_official(raw)
    receipt={
      "schema":"kyoto_jra_20261114_kyoto_navigation_one_off.v1",
      "origin":"JRA_OFFICIAL_PC_SELECTION","source_url":SOURCE,
      "attempted_GET":1,"status":parsed["status"],
      "started_utc":"2026-11-12T08:00:00+00:00",
      "completed_utc":"2026-11-12T08:00:02+00:00",
      "source_sha256":hashlib.sha256(raw).hexdigest(),
      "source_bytes":len(raw),
      "current_meeting_racecards_verified":False,
      "current_prerace_market_verified":False,
      "paper_trade_authorized":False,
      "observed_links":parsed["observed_links"],
    }
    if change:
        change(receipt)
    z=io.BytesIO()
    with zipfile.ZipFile(z,"w") as out:
        out.writestr("receipt.json",json.dumps(receipt))
        if include_original:
            if symlink:
                info=zipfile.ZipInfo("official_selection.html")
                info.create_system=3
                info.external_attr=(0o120777)<<16
                out.writestr(info,raw)
            else:
                out.writestr("official_selection.html",raw)
    return z.getvalue()

class OperatorStatusTests(unittest.TestCase):
    def test_real_bytes_offline_do_not_credit_live_racecard(self):
        r=inspect_official_selection_archive(payload())
        self.assertEqual(r["classification"],"OFFICIAL_MEETING_LINK_OBSERVED_NOT_RACECARD")
        self.assertEqual(r["operational_progress_credit"],0)
        self.assertEqual(r["network_requests"],0)
        self.assertTrue(r["official_meeting_url"].startswith("https://jra.jp/"))
        self.assertFalse(r["prerace_quinella_verified"])
        self.assertFalse(r["prerace_bracket_verified"])
    def test_unpublished_official_source_safe(self):
        r=inspect_official_selection_archive(payload(raw=b"<html><title>JRA</title></html>"))
        self.assertEqual(r["classification"],"OFFICIAL_LINK_NOT_YET_PUBLISHED_SAFE_STOP")
        self.assertIsNone(r["official_meeting_url"])
    def test_bad_receipt_hash_fails(self):
        with self.assertRaises(SourceStatusRejected):
            inspect_official_selection_archive(payload(change=lambda r:r.update(source_sha256="0"*64)))
    def test_inflated_claim_fails(self):
        with self.assertRaises(SourceStatusRejected):
            inspect_official_selection_archive(payload(change=lambda r:r.update(current_prerace_market_verified=True)))
    def test_invalid_zip_fails(self):
        with self.assertRaises(SourceStatusRejected):
            inspect_official_selection_archive(b"not a zip")
    def test_missing_original_fails(self):
        with self.assertRaises(SourceStatusRejected):
            inspect_official_selection_archive(payload(include_original=False))
    def test_symlink_member_fails(self):
        with self.assertRaises(SourceStatusRejected):
            inspect_official_selection_archive(payload(symlink=True))
    def test_path_traversal_member_fails(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,"w") as z:
            z.writestr("../receipt.json","{}")
        with self.assertRaises(SourceStatusRejected):
            inspect_official_selection_archive(b.getvalue())
    def test_duplicate_receipt_member_fails(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,"w") as z:
            z.writestr("receipt.json","{}")
            z.writestr("nested/receipt.json","{}")
        with self.assertRaises(SourceStatusRejected):
            inspect_official_selection_archive(b.getvalue())
    def test_forged_archived_handoff_fails(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,"w") as z:
            with zipfile.ZipFile(io.BytesIO(payload())) as original:
                for member in original.namelist():
                    z.writestr(member,original.read(member))
            z.writestr("verified_meeting_handoff.json",json.dumps({"state":"LIVE_VERIFIED"}))
        with self.assertRaises(SourceStatusRejected):
            inspect_official_selection_archive(b.getvalue())
    def test_recorded_link_break_is_warning_only(self):
        receipt={"schema_version":"jra_one_shot_market_capture.v1",
                 "channel":"PC","race_id":"2026-11-14_KYOTO_11R",
                 "state":"CAPTURE_BLOCKED",
                 "operator_alert":{"severity":"ERROR","code":"JRA_RACECARD_LINK_BROKEN"},
                 "link_repair":{"state":"BROKEN_NOT_REPAIRED","original_http_status":404}}
        result=inspect_recorded_link_alert(json.dumps(receipt).encode())
        self.assertEqual(result["severity"],"ERROR")
        self.assertFalse(result["actual_jra_source_independently_verified"])
        self.assertEqual(result["operational_progress_credit"],0)
    def test_forged_successful_repair_claim_cannot_gain_credit(self):
        receipt={"schema_version":"jra_one_shot_market_capture.v1",
                 "channel":"PC","race_id":"2026-11-14_KYOTO_11R",
                 "state":"SOURCE_FROZEN",
                 "operator_alert":{"severity":"INFO","code":"JRA_LINK_REPAIRED_VERIFIED"},
                 "link_repair":{"status":"REPAIRED_VERIFIED_PC_ONLY"}}
        result=inspect_recorded_link_alert(json.dumps(receipt).encode())
        self.assertTrue(result["record_only_not_authenticated"])
        self.assertEqual(result["operational_progress_credit"],0)
    def test_mismatched_repair_state_rejected(self):
        receipt={"schema_version":"jra_one_shot_market_capture.v1",
                 "channel":"PC","race_id":"2026-11-14_KYOTO_11R",
                 "state":"CAPTURE_BLOCKED",
                 "operator_alert":{"severity":"INFO","code":"JRA_LINK_REPAIRED_VERIFIED"},
                 "link_repair":{"state":"FAILED_CLOSED"}}
        with self.assertRaises(SourceStatusRejected):
            inspect_recorded_link_alert(json.dumps(receipt).encode())
    def test_spoofed_severity_rejected(self):
        receipt={"schema_version":"jra_one_shot_market_capture.v1",
                 "channel":"PC","race_id":"2026-11-14_KYOTO_11R",
                 "state":"CAPTURE_BLOCKED",
                 "operator_alert":{"severity":"INFO","code":"JRA_RACECARD_LINK_BROKEN"},
                 "link_repair":{"state":"BROKEN_NOT_REPAIRED","original_http_status":404}}
        with self.assertRaises(SourceStatusRejected):
            inspect_recorded_link_alert(json.dumps(receipt).encode())
    def test_no_guess_from_empty_zip(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,"w") as z:
            z.writestr("receipt.json","{}")
        with self.assertRaises(SourceStatusRejected):
            inspect_official_selection_archive(b.getvalue())

if __name__=="__main__":unittest.main()
