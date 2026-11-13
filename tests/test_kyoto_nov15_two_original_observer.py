"""Nov15 two-original observation mock transport, no JRA network."""
import tempfile, unittest
from pathlib import Path
from diagnostics.kyoto_nov15_two_original_observer import (
    observe,accept_observation,ObservationRejected,DAY,SOURCE)

ANCHOR='<html><a href="/JRADB/accessD.html?CNAME=pw01meet20261115%2FA1">5回京都4日</a></html>'.encode("cp932")
MEETING=b'<html><title>KYOTO</title><body>observed no race claim</body></html>'
class R:
 def __init__(self, url, data, status=200, content_type="text/html"):
    self.url=url;self.data=data;self.status=status;self.headers={"Content-Type":content_type}
 def geturl(self):return self.url
 def read(self,n):return self.data[:n]
 def __enter__(self):return self
 def __exit__(self,*x):return False
class Stub:
 def __init__(self,selection=ANCHOR,meeting=MEETING,ex=None):
    self.selection=selection;self.meeting=meeting;self.ex=ex;self.urls=[]
 def open(self,request,timeout=12):
    self.urls.append(request.full_url)
    if self.ex:raise self.ex
    return R(request.full_url,self.selection if len(self.urls)==1 else self.meeting)
class ObservationTests(unittest.TestCase):
 def setUp(self):
    self.temp=tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.root=Path(self.temp.name)/"one-shot"
 def run_obs(self,opener=None,allowed=True,now="2026-11-14T09:00:00Z"):
    return observe(self.root,now_utc=now,opener=opener or Stub(),allowed=allowed)
 def test_two_requests_are_actual_observed_links_only(self):
    stub=Stub()
    result=self.run_obs(stub)
    self.assertEqual(result["state"],"NOV15_MEETING_ORIGINALS_OBSERVED_NOT_RACECARD")
    self.assertEqual(len(stub.urls),2)
    self.assertEqual(stub.urls[0],SOURCE)
    self.assertIn(DAY,stub.urls[1])
    self.assertFalse(result["both_markets_verified"])
    self.assertEqual(accept_observation(self.root)["state"],"TWO_ORIGINALS_MATCH_RECEIPT_ONLY")
 def test_optional_third_get_requires_observed_unique_race(self):
    race_anchor='<html><a href="/JRADB/accessD.html?CNAME=pw020aaa01%2F0120261115">京都 1R</a></html>'.encode("cp932")
    class Three(Stub):
      def open(self,request,timeout=12):
        self.urls.append(request.full_url)
        return R(request.full_url,self.selection if len(self.urls)==1 else race_anchor if len(self.urls)==2 else b"<html>actual observed racecard bytes</html>")
    stub=Three()
    result=observe(self.root,now_utc="2026-11-15T02:00:00Z",opener=stub,
                  allowed=True,include_observed_racecard=True)
    self.assertEqual(len(stub.urls),3)
    self.assertTrue(result["racecard_original_fetched"])
    self.assertEqual(result["state"],"NOV15_RACECARD_ORIGINAL_OBSERVED_ROSTER_UNVERIFIED")
    self.assertEqual(result["http_requests_started"],3)
    self.assertFalse(result["both_markets_verified"])
    self.assertFalse(result["real_racecard_verified"])
    self.assertEqual(accept_observation(self.root)["state"],"TWO_ORIGINALS_MATCH_RECEIPT_ONLY")
 def test_every_captured_original_has_utc_timestamp(self):
    import json
    race_anchor='<html><a href="/JRADB/accessD.html?CNAME=pw020aaa01%2F0120261115">京都 1R</a></html>'.encode("cp932")
    class Three(Stub):
      def open(self,request,timeout=12):
        self.urls.append(request.full_url)
        return R(request.full_url,self.selection if len(self.urls)==1 else race_anchor if len(self.urls)==2 else b"<html>racecard</html>")
    result=observe(self.root,now_utc="2026-11-15T02:00:00Z",opener=Three(),allowed=True,
                   include_observed_racecard=True)
    for key in ("started_at_utc","selection_captured_at_utc",
                "meeting_captured_at_utc","racecard_captured_at_utc","ended_at_utc"):
        self.assertIn(key,result)
        self.assertTrue(result[key].endswith("+00:00"))
 def test_later_numbered_observed_race_is_preferred_without_start_claim(self):
    race_anchors=('<html>'
      '<a href="/JRADB/accessD.html?CNAME=pw020aaa01%2F0120261115">京都 1R</a>'
      '<a href="/JRADB/accessD.html?CNAME=pw020aaa12%2F1220261115">京都 12R</a>'
      '</html>').encode("cp932")
    class Three(Stub):
      def open(self,request,timeout=12):
        self.urls.append(request.full_url)
        return R(request.full_url,self.selection if len(self.urls)==1 else
                 race_anchors if len(self.urls)==2 else b"<html>racecard</html>")
    result=observe(self.root,now_utc="2026-11-15T02:00:00Z",
                   opener=Three(),allowed=True,include_observed_racecard=True)
    self.assertEqual(result["racecard_number"],12)
    self.assertEqual(result["http_requests_started"],3)
    self.assertFalse(result["real_racecard_verified"])
 def test_no_observed_race_means_only_two_gets(self):
    stub=Stub()
    result=observe(self.root,now_utc="2026-11-15T02:00:00Z",opener=stub,
                  allowed=True,include_observed_racecard=True)
    self.assertEqual(len(stub.urls),2)
    self.assertFalse(result["racecard_original_fetched"])
 def test_tampered_third_original_rejected(self):
    race_anchor='<html><a href="/JRADB/accessD.html?CNAME=pw020aaa01%2F0120261115">京都 1R</a></html>'.encode("cp932")
    class Three(Stub):
      def open(self,request,timeout=12):
        self.urls.append(request.full_url)
        return R(request.full_url,self.selection if len(self.urls)==1 else race_anchor if len(self.urls)==2 else b"<html>racecard</html>")
    observe(self.root,now_utc="2026-11-15T02:00:00Z",opener=Three(),allowed=True,
            include_observed_racecard=True)
    (self.root/"official_racecard.html").write_bytes(b"tampered")
    with self.assertRaisesRegex(ObservationRejected,"racecard_original_digest_mismatch"):
        accept_observation(self.root)
 def test_selection_invalid_encoding_preserves_exact_original_before_failure(self):
    import hashlib,json
    broken=b"<html>\\x81</html>"
    stub=Stub(selection=broken)
    r=self.run_obs(stub)
    self.assertEqual(r["state"],"FAILED_CLOSED")
    self.assertEqual(len(stub.urls),1)
    self.assertEqual((self.root/"official_selection.html").read_bytes(),broken)
    self.assertEqual(r["selection_sha256"],hashlib.sha256(broken).hexdigest())
    self.assertEqual(r["selection_bytes"],len(broken))
    self.assertIn("selection_captured_at_utc",r)
 def test_meeting_invalid_encoding_keeps_both_origins(self):
    import hashlib
    broken=b"<html>\\x81</html>"
    stub=Stub(meeting=broken)
    r=self.run_obs(stub)
    self.assertEqual(r["state"],"FAILED_CLOSED")
    self.assertEqual(len(stub.urls),2)
    self.assertEqual((self.root/"official_selection.html").read_bytes(),ANCHOR)
    self.assertEqual((self.root/"official_meeting.html").read_bytes(),broken)
    self.assertEqual(r["meeting_sha256"],hashlib.sha256(broken).hexdigest())
 def test_racecard_invalid_encoding_preserves_all_three_originals(self):
    import hashlib
    observed='<html><a href="/JRADB/accessD.html?CNAME=pw020aaa12%2F1220261115">京都 12R</a></html>'.encode("cp932")
    class BrokenRace(Stub):
      def open(self,request,timeout=12):
        self.urls.append(request.full_url)
        data=self.selection if len(self.urls)==1 else observed if len(self.urls)==2 else b"<html>\\x81</html>"
        return R(request.full_url,data)
    stub=BrokenRace()
    r=observe(self.root,now_utc="2026-11-15T02:00:00Z",opener=stub,allowed=True,
              include_observed_racecard=True)
    self.assertEqual(r["state"],"FAILED_CLOSED")
    self.assertEqual(len(stub.urls),3)
    self.assertTrue(r["racecard_original_fetched"])
    self.assertEqual((self.root/"official_racecard.html").read_bytes(),b"<html>\\x81</html>")
    self.assertEqual(r["racecard_sha256"],hashlib.sha256(b"<html>\\x81</html>").hexdigest())
 def test_empty_unpublished_selection_stops_after_one(self):
    stub=Stub(selection=b"<html>NO KYOTO</html>")
    result=self.run_obs(stub)
    self.assertEqual(result["state"],"FAILED_CLOSED")
    self.assertEqual(len(stub.urls),1)
 def test_ambiguous_meetings_stops_after_one(self):
    extra='<a href="/JRADB/accessD.html?CNAME=pw01meet20261115%2FX2">京都15日</a>'.encode("cp932")
    stub=Stub(selection=ANCHOR+extra)
    result=self.run_obs(stub)
    self.assertEqual(result["state"],"FAILED_CLOSED")
    self.assertEqual(len(stub.urls),1)
 def test_timeout_stops_without_retry(self):
    stub=Stub(ex=TimeoutError("synthetic failure"))
    result=self.run_obs(stub)
    self.assertEqual(result["state"],"FAILED_CLOSED")
    self.assertEqual(len(stub.urls),1)
    with self.assertRaisesRegex(ObservationRejected,"observation_not_successful"):
        accept_observation(self.root)
 def test_without_permission_uses_zero_gets(self):
    stub=Stub()
    with self.assertRaisesRegex(ObservationRejected,"not_explicitly_authorized"):
        self.run_obs(stub,allowed=False)
    self.assertEqual(len(stub.urls),0)
 def test_wrong_time_zero_gets(self):
    stub=Stub()
    with self.assertRaisesRegex(ObservationRejected,"outside_observation_window"):
        self.run_obs(stub,now="2026-11-12T00:00:00Z")
    self.assertEqual(len(stub.urls),0)
 def test_after_date_zero_gets(self):
    stub=Stub()
    with self.assertRaisesRegex(ObservationRejected,"outside_observation_window"):
        self.run_obs(stub,now="2026-11-15T04:00:00Z")
    self.assertEqual(len(stub.urls),0)
 def test_preserves_original_on_repeat(self):
    self.run_obs()
    with self.assertRaisesRegex(ObservationRejected,"one_shot_output_existing"):
        self.run_obs()
 def test_modified_original_is_detected(self):
    self.run_obs()
    (self.root/"official_meeting.html").write_bytes(b"tampered")
    with self.assertRaisesRegex(ObservationRejected,"digest_mismatch"):
        accept_observation(self.root)
 def test_incomplete_original_is_detected(self):
    self.run_obs()
    (self.root/"official_selection.html").unlink()
    with self.assertRaisesRegex(ObservationRejected,"original_missing"):
        accept_observation(self.root)
 def test_no_data_claims_real_racecard(self):
    self.run_obs()
    accepted=accept_observation(self.root)
    self.assertFalse(accepted["racecard_verified"])
    self.assertFalse(accepted["market_verified"])
 def test_no_meeting_redirect_allowed(self):
    # The stub model represents HTTP transport; mismatch of final URLs must
    # fail if live server returns a redirected destination.
    class Redirect(Stub):
      def open(self,request,timeout=12):
        self.urls.append(request.full_url)
        return R("https://evil.invalid/",ANCHOR)
    result=self.run_obs(Redirect())
    self.assertEqual(result["state"],"FAILED_CLOSED")
if __name__=="__main__":unittest.main()
