import json,tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_incident_recovery import inspect_source,run_identity,label,canonical,REPO
class IncidentRecoveryTests(unittest.TestCase):
 def put(self,root,name,value):
  (root/name).write_bytes(value if isinstance(value,bytes) else json.dumps(value).encode())
 def test_redirect_does_not_become_twelve_independent_causes(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.put(r,"receipt.json",{"day":"20261128","error_code":"any_redirect_disallowed","error_class":"DiscoveryRejected"})
   v=inspect_source(r,"20261128","pc");i={x["stage"]:x for x in v["incidents"]}
   self.assertEqual(i["PC_ENTRY"]["code"],"any_redirect_disallowed")
   self.assertEqual(i["G03"]["blocked_by"],"PC_MEETING");self.assertEqual(i["G06"]["blocked_by"],"G03")
   self.assertIsNone(i["G05"]["blocked_by"]);self.assertFalse(i["PC_ENTRY"]["root_cause_closed"])
   self.assertEqual(canonical(v),canonical(inspect_source(r,"20261128","pc")))
 def test_observed_post_entry_and_zero_candidates(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.put(r,"receipt.json",{"day":"20261128"})
   self.put(r,"sp_discovery_receipt.json",{"per_race_observed_navigation_candidates":{str(n):{"candidate_count":0} for n in range(1,13)},"attempts":[{"request_method":"GET"}]})
   self.put(r,"official_sp_discovery_1.html",'<a onclick="return doAction(\'/JRADB/accessD.html\',\'sw01dli00/80\')">出馬表</a>'.encode("utf8"))
   v=inspect_source(r,"20261128","sp")
   self.assertEqual(v["incidents"][0]["code"],"OBSERVED_POST_ENTRY_NO_POST_ATTEMPT")
   self.assertEqual(v["incidents"][1]["blocked_by"],"SP_DISCOVERY")
 def test_green_receipt_with_no_data_is_not_success(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.put(r,"receipt.json",{"day":"20261129","state":"SOURCE_ONLY_FINISHED"})
   v=inspect_source(r,"20261129","postrace")
   self.assertFalse(v["source_claims_independently_certified"]);self.assertEqual(len(v["incidents"]),1)
 def test_no_secret_or_url_in_error(self):
  for x in ("https://private.invalid/key","A"*64,"token=private"):
   self.assertNotIn(x,label(x));self.assertTrue(label(x).startswith("UNCLASSIFIED_TEXT_SHA256_"))
 def test_adaptive_replay_does_not_confuse_candidate_and_applied(self):
  import hashlib
  from diagnostics.kyoto_incident_recovery import replay_adaptive
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);raw=b"<html>new layout</html>";self.put(r,"official_pc_navigation_home.html",raw)
   p={"source_sha256":hashlib.sha256(raw).hexdigest(),"stage":"entry","channel":"PC","day":"20261129","parser_agreement":True,"counterexamples_rejected":True,"rule_sha256":"a"*64,"action_sha256":"b"*64,"rule":{"grammar":"test"}}
   def repair(raw_arg,day,channel,stage):
    self.assertEqual((raw_arg,day,channel,stage),(raw,"20261129","PC","entry"));return "/private","secret","name",p
   self.put(r,"receipt.json",{"day":"20261129"})
   self.assertEqual(replay_adaptive(r,"20261129","pc",repair)[0]["state"],"LOCAL_CANDIDATE_VERIFIED_NOT_APPLIED")
   self.put(r,"receipt.json",{"day":"20261129","adaptive_navigation_repairs":[p]})
   v=replay_adaptive(r,"20261129","pc",repair)[0]
   self.assertEqual(v["state"],"APPLIED_REPAIR_REPRODUCED");self.assertFalse(v["root_cause_closed"]);self.assertNotIn("secret",json.dumps(v))
   self.put(r,"receipt.json",{"day":"20261129","adaptive_navigation_repairs":[{**p,"action_sha256":"c"*64}]})
   self.assertEqual(replay_adaptive(r,"20261129","pc",repair)[0]["state"],"RECORDED_REPAIR_MISMATCH")
   def reject(*args):raise ValueError("unknown_layout")
   self.assertEqual(replay_adaptive(r,"20261129","pc",reject)[0]["state"],"REPAIR_SEARCH_UNRESOLVED")
 def test_salvage_receipt_is_preserved_without_success_credit(self):
  import hashlib
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.put(r,"official_meeting.html",b"original")
   doc={"day":"20261129","schema":"kyoto_archive_salvage.v1","saved_originals":{"official_meeting.html":{"sha256":hashlib.sha256(b"original").hexdigest(),"bytes":8}},"rejected_members":[{"path_sha256":"a"*64,"reason":"UNRECOGNIZED"}]}
   self.put(r,"receipt.json",doc)
   v=inspect_source(r,"20261129","pc")
   self.assertEqual(v["incidents"][0]["code"],"STRICT_ARCHIVE_REJECTED_PARTIAL_RECOVERY")
   self.assertFalse(v["source_claims_independently_certified"])
   doc["saved_originals"]["official_meeting.html"]["sha256"]="b"*64;self.put(r,"receipt.json",doc)
   self.assertEqual(inspect_source(r,"20261129","pc")["incidents"][0]["code"],"SALVAGE_RECEIPT_MISMATCH")
 def test_wrong_day(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.put(r,"receipt.json",{"day":"20261128"})
   with self.assertRaises(ValueError):inspect_source(r,"20261129","pc")
 def test_run_binding(self):
  r={"id":7,"head_branch":"main","head_repository":{"full_name":REPO},"status":"completed","event":"workflow_dispatch","path":".github/workflows/kyoto-20261128-29-two-source-production-observer.yml","head_sha":"a"*40,"created_at":"2026-11-28T03:00:00Z"}
  self.assertEqual(run_identity(r,7)[1:],(("pc","sp"),("20261128",)))
  for k,v in (("head_branch","other"),("head_repository",{"full_name":"other/repo"}),("created_at","2026-11-30T00:00:00Z"),("path",".github/workflows/other.yml")):
   with self.assertRaises(ValueError):run_identity({**r,k:v},7)
 def test_real_skipped_cushion_producer_records_no_archive_loss(self):
  from unittest.mock import patch
  from diagnostics.kyoto_incident_recovery import diagnose_run,write_report
  for rid,jid in ((46096556814,140829114593),(46100220249,140840732210),(46108030052,140865067475)):
   run={"id":rid,"head_branch":"main","head_repository":{"full_name":REPO},"status":"completed","event":"workflow_run","path":".github/workflows/kyoto-20261128-29-cushion-source.yml","head_sha":"a"*40,"created_at":"2026-11-28T03:00:00Z"}
   job={"id":jid,"run_id":rid,"name":"cushion-source-only","status":"completed","conclusion":"skipped","steps":None}
   with self.subTest(run=rid),patch("diagnostics.kyoto_incident_recovery.gh",side_effect=[run,{"total_count":1,"jobs":[job]},{"total_count":0,"artifacts":[]}]),patch("diagnostics.kyoto_incident_recovery.subprocess.run") as download:
    report=diagnose_run(rid,"unused","unused")
    lane=report["lanes"]["cushion"]
    self.assertEqual(lane["source_acquisition_state"],"PRODUCER_NOT_EXECUTED_SKIP_REASON_UNVERIFIED")
    self.assertEqual(lane["artifact_evidence"]["job_id"],jid)
    self.assertFalse(lane["artifact_evidence"]["skip_reason_verified"])
    self.assertFalse(lane["artifact_authenticated"])
    self.assertFalse(report["jobs"][0]["steps_available"])
    self.assertEqual(lane["incidents"],[])
    download.assert_not_called()
    with tempfile.TemporaryDirectory() as td:
     write_report(report,td)
     summary=(Path(td)/"summary.md").read_text()
     self.assertIn("スキップ",summary)
     self.assertNotIn("欠落未検出",summary)
 def test_non_skipped_missing_archive_still_reported(self):
  from unittest.mock import patch
  from diagnostics.kyoto_incident_recovery import diagnose_run
  rid=46108030052
  run={"id":rid,"head_branch":"main","head_repository":{"full_name":REPO},"status":"completed","event":"workflow_run","path":".github/workflows/kyoto-20261128-29-cushion-source.yml","head_sha":"a"*40,"created_at":"2026-11-28T03:00:00Z"}
  for conclusion in ("success","failure","cancelled"):
   job={"id":1,"run_id":rid,"name":"cushion-source-only","status":"completed","conclusion":conclusion,"steps":[]}
   with self.subTest(conclusion=conclusion),patch("diagnostics.kyoto_incident_recovery.gh",side_effect=[run,{"total_count":1,"jobs":[job]},{"total_count":0,"artifacts":[]}]):
    lane=diagnose_run(rid,"unused","unused")["lanes"]["cushion"]
    self.assertFalse(lane["artifact_authenticated"])
    self.assertEqual(lane["incidents"][0]["stage"],"ARCHIVE")
    self.assertEqual(lane["artifact_evidence"]["job_conclusion"],conclusion)
if __name__=="__main__":unittest.main()
