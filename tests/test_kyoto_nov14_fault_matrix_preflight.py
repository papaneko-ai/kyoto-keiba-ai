"""Nov14 fail-closed preflight fault injection; NO external HTTP.

Preserves the historical failed GET, verifies future accidental retries are
blocked, exercises link publication and evidence receipt failure behavior.
Tests themselves use only in-memory response stubs and temp directories.
"""
import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from diagnostics.kyoto_p1_nov14_official_one_shot_nav import (
    SOURCE,inspect_once,strict_link_from_official,DiscoveryRejected,LIMIT)
from diagnostics.kyoto_p1_nov14_receipt_handoff import (
    assess_saved_selection,HandoffRejected)
from diagnostics.kyoto_nov14_attempt_guard import (
    enforce_recorded_one_shot,evaluate_attempt_guard,AttemptGuardRejected)

WHEN=lambda:datetime(2026,11,13,1,0,tzinfo=timezone.utc)
EARLY=lambda:datetime(2026,11,12,2,34,tzinfo=timezone.utc)
PAST=lambda:datetime(2026,11,14,1,0,tzinfo=timezone.utc)
LINK='<a href="/JRADB/accessD.html?CNAME=pw01dde0108202605030720261114%2FAA">5回京都3日</a>'
def html(s):
    return ('<html><title>JRA</title><body>'+s+'</body></html>').encode('cp932')
class Reply:
    status=200
    headers={"Content-Type":"text/html; charset=Shift_JIS"}
    def __init__(self,raw,*,url=SOURCE,status=200,content_type=None):
        self.raw=raw;self.url=url;self.status=status
        if content_type is not None:self.headers={"Content-Type":content_type}
    def read(self,n):return self.raw[:n]
    def geturl(self):return self.url
    def __enter__(self):return self
    def __exit__(self,*exc):return False
class Stub:
    def __init__(self,reply=None,ex=None):
        self.reply=reply;self.ex=ex;self.calls=0
    def open(self,req,timeout):
        self.calls+=1
        assert req.full_url==SOURCE and req.get_method()=="GET"
        assert timeout==12
        if self.calls>1:raise AssertionError("duplicate GET")
        if self.ex:raise self.ex
        return self.reply

class Nov14FaultMatrixTests(unittest.TestCase):
    def run_capture(self,opener,clock=WHEN):
        with tempfile.TemporaryDirectory() as directory:
            receipt=inspect_once(directory,opener=opener,clock=clock)
            state=assess_saved_selection(directory)
            return receipt,state

    def test_prior_attempt_is_locked_and_never_repeated(self):
        status=enforce_recorded_one_shot()
        self.assertFalse(status["allow_JRA_GET"])
        self.assertFalse(status["allow_workflow_rerun"])
        self.assertEqual(status["prior_attempted_GET"],1)

    def test_prior_attempt_tampered_record_rejected(self):
        with self.assertRaisesRegex(AttemptGuardRejected,"incident_not_locked"):
            evaluate_attempt_guard("no real prior attempt",prior_attempted_get=1,event_name="push")

    def test_missing_incident_refuses_any_live_permission(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(AttemptGuardRejected,"incident_record_unavailable"):
                enforce_recorded_one_shot(Path(d)/"missing")

    def test_workflow_checks_prior_attempt_before_jra_get(self):
        workflow=Path(".github/workflows/kyoto-p1-nov14-one-shot-meeting-observation.yml").read_text(encoding="utf8")
        self.assertLess(workflow.index("Block Nov14 repeat GET"),
                        workflow.index("ONE limited official JRA GET"))
        self.assertIn("enforce_recorded_one_shot",workflow)

    def test_early_publication_clock_never_calls_network(self):
        stub=Stub(Reply(html(LINK)))
        receipt,state=self.run_capture(stub,EARLY)
        self.assertEqual(stub.calls,0)
        self.assertEqual(receipt["attempted_GET"],0)
        self.assertEqual(state["state"],"NO_OFFICIAL_ORIGINAL_SAFE_STOP")

    def test_late_publication_clock_never_calls_network(self):
        stub=Stub(Reply(html(LINK)))
        receipt,state=self.run_capture(stub,PAST)
        self.assertEqual(stub.calls,0)
        self.assertEqual(receipt["status"],"STALE_MEETING_DISCOVERY_NO_HTTP")
        self.assertEqual(state["state"],"NO_OFFICIAL_ORIGINAL_SAFE_STOP")

    def test_timeout_failed_closed_and_exactly_one_request(self):
        stub=Stub(ex=TimeoutError("synthetic timeout"))
        receipt,state=self.run_capture(stub)
        self.assertEqual(stub.calls,1)
        self.assertEqual(receipt["status"],"FAILED_CLOSED")
        self.assertEqual(receipt["error_class"],"TimeoutError")
        self.assertEqual(state["state"],"FAILED_OFFICIAL_CAPTURE_SAFE_STOP")

    def test_http_503_failed_closed(self):
        stub=Stub(Reply(html(LINK),status=503))
        receipt,state=self.run_capture(stub)
        self.assertEqual(stub.calls,1)
        self.assertEqual(receipt["status"],"FAILED_CLOSED")
        self.assertIsNone(state["official_meeting_url"])

    def test_redirect_failed_closed(self):
        stub=Stub(Reply(html(LINK),url="https://jra.jp.evil.invalid/"))
        receipt,state=self.run_capture(stub)
        self.assertEqual(stub.calls,1)
        self.assertEqual(receipt["status"],"FAILED_CLOSED")
        self.assertEqual(state["state"],"FAILED_OFFICIAL_CAPTURE_SAFE_STOP")

    def test_non_html_content_type_failed_closed(self):
        stub=Stub(Reply(html(LINK),content_type="application/json"))
        receipt,state=self.run_capture(stub)
        self.assertEqual(receipt["status"],"FAILED_CLOSED")
        self.assertEqual(stub.calls,1)

    def test_invalid_encoding_failed_closed(self):
        stub=Stub(Reply(b'\x81'))
        receipt,state=self.run_capture(stub)
        self.assertEqual(receipt["status"],"FAILED_CLOSED")
        self.assertEqual(state["state"],"FAILED_OFFICIAL_CAPTURE_SAFE_STOP")

    def test_oversize_page_failed_closed(self):
        stub=Stub(Reply(b"x"*(LIMIT+1)))
        receipt,state=self.run_capture(stub)
        self.assertEqual(stub.calls,1)
        self.assertEqual(receipt["status"],"FAILED_CLOSED")

    def test_not_yet_visible_creates_no_fake_meeting_link(self):
        stub=Stub(Reply(html('<a href="#">other date</a>')))
        receipt,state=self.run_capture(stub)
        self.assertEqual(receipt["status"],"NOT_YET_VISIBLE")
        self.assertEqual(state["state"],"OFFICIAL_LINK_NOT_YET_PUBLISHED_SAFE_STOP")
        self.assertIsNone(state["official_meeting_url"])

    def test_ambiguous_meeting_link_failed_closed(self):
        stub=Stub(Reply(html(LINK+LINK.replace("%2FAA","%2FBB"))))
        receipt,state=self.run_capture(stub)
        self.assertEqual(receipt["status"],"FAILED_CLOSED")
        self.assertEqual(receipt["safe_error_code"],"ambiguous_current_kyoto_link")
        self.assertEqual(state["state"],"FAILED_OFFICIAL_CAPTURE_SAFE_STOP")

    def test_valid_official_like_fixture_does_not_certify_race_or_markets(self):
        stub=Stub(Reply(html(LINK)))
        receipt,state=self.run_capture(stub)
        self.assertEqual(receipt["status"],"OFFICIAL_NOV14_KYOTO_MEETING_LINK_OBSERVED")
        self.assertEqual(state["state"],"OFFICIAL_MEETING_LINK_OBSERVED_NOT_RACECARD")
        self.assertFalse(state["racecard_verified"])
        self.assertFalse(state["prerace_markets_verified"])
        self.assertEqual(state["network_requests"],0)

    def test_tampered_html_receipt_stops_handoff(self):
        with tempfile.TemporaryDirectory() as d:
            stub=Stub(Reply(html(LINK)))
            inspect_once(d,opener=stub,clock=WHEN)
            (Path(d)/"official_selection.html").write_bytes(html(LINK)+b'X')
            with self.assertRaisesRegex(HandoffRejected,"digest"):
                assess_saved_selection(d)

    def test_no_repeat_get_in_same_directory_after_success(self):
        with tempfile.TemporaryDirectory() as d:
            stub=Stub(Reply(html(LINK)))
            inspect_once(d,opener=stub,clock=WHEN)
            with self.assertRaisesRegex(DiscoveryRejected,"must_not_be_overwritten"):
                inspect_once(d,opener=stub,clock=WHEN)
            self.assertEqual(stub.calls,1)

if __name__=="__main__":
    unittest.main()
