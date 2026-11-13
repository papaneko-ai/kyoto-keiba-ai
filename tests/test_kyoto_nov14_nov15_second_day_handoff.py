"""Nov14/15 fallback: offline original-observed navigation, no date leakage."""
import copy
import unittest
from diagnostics.kyoto_nov14_nov15_second_day_handoff import (
    validate_day15_handoff, classify_day14_capture, SecondDayRejected
)

SEL='<html><title>JRA</title><body><a href="/JRADB/accessD.html?CNAME=pw01meet20261115%2FA1">京都 11月15日</a></body></html>'.encode("cp932")
MEET='<html><title>京都</title><body><a href="/JRADB/accessD.html?CNAME=pw011120261115%2FB2">11R</a></body></html>'.encode("cp932")
RACE="https://jra.jp/JRADB/accessD.html?CNAME=pw011120261115%2FB2"
SPEC={"race_day":"20261115","race_number":11,"race_id":"2026-11-15_KYOTO_11R",
      "venue":"京都","pc_racecard_url":RACE,"sp_racecard_url":"",
      "normal_sales_open_utc":"2026-11-14T10:30:00+00:00"}
ROSTER={"race_date":"2026-11-15","race_number":11,"venue":"KYOTO",
        "source_url":RACE,"source_sha256":"a"*64,"source_bytes":1000,
        "fetched_at_utc":"2026-11-15T03:00:00Z",
        "runners":[
            {"horse_number":1,"frame_number":1,"horse_name":"馬A"},
            {"horse_number":2,"frame_number":2,"horse_name":"馬B"}
        ]}
START="2026-11-15T06:45:00Z"

class SecondDayHandoffTests(unittest.TestCase):
 def handoff(self,**k):
    v=dict(spec_data=copy.deepcopy(SPEC),roster=copy.deepcopy(ROSTER),
           official_selection_original=SEL,official_meeting_original=MEET,
           verified_start_utc=START)
    v.update(k)
    return validate_day15_handoff(**v)
 def test_day15_observed_pc_original_binding(self):
    r=self.handoff()
    self.assertEqual(r["race_day"],"20261115")
    self.assertEqual(r["observed_pc_racecard_url"],RACE)
    self.assertEqual(r["runner_count"],2)
    self.assertEqual(r["http_attempts"],0)
    self.assertFalse(r["real_prerace_quinella_authenticated"])
    self.assertFalse(r["real_paper_trade_authorized"])
 def test_deterministic_same_input(self):
    self.assertEqual(self.handoff(),self.handoff())
 def test_day14_bad_date_not_reused(self):
    spec={**SPEC,"race_day":"20261114","race_id":"2026-11-14_KYOTO_11R"}
    with self.assertRaises(SecondDayRejected):
        self.handoff(spec_data=spec)
 def test_day14_meeting_not_misused_for_day15(self):
    altered=SEL.replace(b"20261115",b"20261114")
    with self.assertRaisesRegex(SecondDayRejected,"unique_observed"):
        self.handoff(official_selection_original=altered)
 def test_old_day_racecard_rejected(self):
    spec={**SPEC,"pc_racecard_url":RACE.replace("20261115","20261114")}
    with self.assertRaises(SecondDayRejected):
        self.handoff(spec_data=spec)
 def test_unobserved_race_url_fails(self):
    spec={**SPEC,"pc_racecard_url":RACE.replace("%2FB2","%2FC2")}
    roster={**ROSTER,"source_url":spec["pc_racecard_url"]}
    with self.assertRaisesRegex(SecondDayRejected,"racecard_link_not_bound"):
        self.handoff(spec_data=spec,roster=roster)
 def test_duplicate_meeting_anchor_fails(self):
    s=SEL.replace(b"</body>",'<a href="/JRADB/accessD.html?CNAME=pw01meet20261115%2FX2">京都 15日</a></body>'.encode("cp932"))
    with self.assertRaisesRegex(SecondDayRejected,"ambiguous"):
        self.handoff(official_selection_original=s)
 def test_race_label_missing_fails(self):
    m=MEET.replace(b"11R",b"12R")
    with self.assertRaisesRegex(SecondDayRejected,"unique_observed"):
        self.handoff(official_meeting_original=m)
 def test_unsafe_external_anchor_fails(self):
    m=MEET.replace(b'/JRADB/accessD.html',b'https://fake.invalid/JRADB/accessD.html')
    with self.assertRaisesRegex(SecondDayRejected,"unique_observed"):
        self.handoff(official_meeting_original=m)
 def test_empty_original_not_accepted(self):
    with self.assertRaisesRegex(SecondDayRejected,"two_independent_original"):
        self.handoff(official_selection_original=b"")
 def test_same_originals_not_accepted(self):
    with self.assertRaisesRegex(SecondDayRejected,"not_independent"):
        self.handoff(official_selection_original=MEET)
 def test_roster_other_meeting_not_accepted(self):
    r={**ROSTER,"race_date":"2026-11-14"}
    with self.assertRaisesRegex(SecondDayRejected,"race_spec_roster"):
        self.handoff(roster=r)
 def test_roster_capture_after_start_rejected(self):
    r={**ROSTER,"fetched_at_utc":"2026-11-15T06:45:01Z"}
    with self.assertRaisesRegex(SecondDayRejected,"race_spec_roster"):
        self.handoff(roster=r)
 def test_sp_url_requires_independent_sp_original(self):
    spec={**SPEC,"sp_racecard_url":"https://sp.jra.jp/JRADB/accessD.html?CNAME=sw011120261115%2FB2"}
    with self.assertRaisesRegex(SecondDayRejected,"sp_source_unproven"):
        self.handoff(spec_data=spec)
 def test_day14_failure_classification_never_grants_retry(self):
    v=classify_day14_capture({"attempted_GET":1,"status":"FAILED_CLOSED"})
    self.assertFalse(v["nov14_retry_authorized"])
    self.assertTrue(v["day15_separate_trial_permitted_in_principle"])
    self.assertEqual(v["cause"],"UNKNOWN_WITHOUT_HTTP_ORIGINAL")
 def test_day14_successful_link_does_not_mean_markets(self):
    v=classify_day14_capture({"attempted_GET":1,"status":"OFFICIAL_NOV14_KYOTO_MEETING_LINK_OBSERVED"})
    self.assertEqual(v["status"],"DAY14_MEETING_LINK_OBSERVED_ONLY")
 def test_day14_timeout_triage_does_not_grant_retry(self):
    x=classify_day14_capture({"attempted_GET":1,"status":"FAILED_CLOSED",
                              "error_class":"TimeoutError"})
    self.assertEqual(x["cause"],"TRANSPORT_TIMEOUT")
    self.assertFalse(x["nov14_retry_authorized"])
    self.assertTrue(x["evidence_incomplete_without_original"])
 def test_day14_encoding_triage_action(self):
    x=classify_day14_capture({"attempted_GET":1,"status":"FAILED_CLOSED",
                              "safe_error_code":"source_encoding_invalid"})
    self.assertEqual(x["cause"],"HTML_ENCODING")
    self.assertIn("CP932",x["safe_action"])
 def test_day14_ambiguous_link_triage_action(self):
    x=classify_day14_capture({"attempted_GET":1,"status":"FAILED_CLOSED",
                              "safe_error_code":"ambiguous_current_kyoto_link"})
    self.assertEqual(x["cause"],"DUPLICATE_MEETING_LINKS")
 def test_day14_unverified_response_does_not_mean_unpublished(self):
    x=classify_day14_capture({"attempted_GET":1,"status":"FAILED_CLOSED",
                              "safe_error_code":"unverified_original_http_response"})
    self.assertEqual(x["cause"],"HTTP_RESPONSE_UNVERIFIED")
    self.assertNotEqual(x["cause"],"NOT_YET_VISIBLE")
 def test_inconsistent_day14_receipt_not_accepted(self):
    with self.assertRaisesRegex(SecondDayRejected,"state_conflict"):
        classify_day14_capture({"attempted_GET":1,"status":"NOT_YET_VISIBLE"})
 def test_no_http_attempt_distinguished(self):
    v=classify_day14_capture({"attempted_GET":0,"status":"WAIT_FOR_JRA_OFFICIAL_PUBLICATION_NO_HTTP"})
    self.assertEqual(v["status"],"DAY14_NO_GET_ATTEMPT_PROVEN_BY_SUPPLIED_RECEIPT")
 def test_same_day_start_timezone_rejected(self):
    with self.assertRaisesRegex(SecondDayRejected,"start_must_be_utc"):
        self.handoff(verified_start_utc="2026-11-15T15:45:00+09:00")
 def test_source_claim_not_authenticated(self):
    self.assertEqual(self.handoff()["source_observation_claim"],"OFFLINE_OPERATOR_SUPPLIED_NOT_AUTHENTICATED")

if __name__=="__main__": unittest.main()
