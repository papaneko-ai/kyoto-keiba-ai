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
 def test_postrace_navigation_rejection_is_not_unknown_or_success(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);reason="PostraceRejected:missing_or_ambiguous_observed_navigation"
   self.put(root,"receipt.json",{"day":"20261128","results_meeting_state":"ORIGINAL_OBSERVED_NOT_FINAL_PROOF","payout_meeting_state":reason,"races":{str(n):{"state":"RESULT_SOURCE_OR_PARSE_FAILED","reason":reason} for n in range(1,13)}})
   self.put(root,"results_meeting.html",b"original")
   self.put(root,"payout_menu.html",b"original")
   v=inspect_source(root,"20261128","postrace")
   self.assertEqual(v["incidents"][0]["code"],"POSTRACE_OBSERVED_NAVIGATION_REJECTED")
   self.assertEqual(v["stages"][0]["observations"]["navigation_rejected_races"],list(range(1,13)))
   self.assertTrue(v["stages"][0]["observations"]["payout_navigation_rejected"])
   self.assertFalse(v["incidents"][0]["root_cause_closed"])
   self.assertFalse(v["source_claims_independently_certified"])
   self.assertTrue(label(reason+":private").startswith("UNCLASSIFIED_TEXT_SHA256_"))
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
 def test_track_failure_receipt_does_not_count_as_observed(self):
  import hashlib
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);day="20261129";raw=b"original"
   self.put(root,"receipt.json",{"day":day,"verified_races":[10,11],"observed_field_values":0})
   self.put(root,"g05_receipt.json",{"day":day})
   self.put(root,"g05_official_kyoto_track.html",raw)
   track={"day":day,"schema":"kyoto_g05_track_failure.v1","state":"TRACK_PARSE_FAILED","error_class":"G05TrackRejected","source_sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)}
   for lane,name in (("pc","G05"),("auxiliary","AUXILIARY")):
    self.put(root,"g05_track_receipt.json",track)
    result=inspect_source(root,day,lane)
    self.assertEqual(next(i for i in result["incidents"] if i["stage"]==name)["code"],"G05TrackRejected")
    self.assertFalse(next(i for i in result["stages"] if i["stage"]==name)["observations"]["track_original_bound_observation"])
    self.put(root,"g05_track_receipt.json",{**track,"state":"TRACK_FETCH_FAILED","error_code":"HTTP_STATUS_403","http_status":403})
    result=inspect_source(root,day,lane)
    self.assertEqual(next(i for i in result["incidents"] if i["stage"]==name)["code"],"HTTP_STATUS_403")
    self.assertFalse(result["source_claims_independently_certified"])
 def test_track_original_bound_observation_still_distinct_from_certification(self):
  import hashlib
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);day="20261129";raw=b"original"
   self.put(root,"receipt.json",{"day":day,"verified_races":[10,11]})
   self.put(root,"g05_receipt.json",{"day":day})
   self.put(root,"g05_official_kyoto_track.html",raw)
   doc={"schema":"kyoto_g05_kyoto_track.v1","day":day,"source_url":"https://www.jra.go.jp/keiba/baba/index2.html","source_sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),"same_day_official_meeting_heading_verified":True,"weather":"晴"}
   self.put(root,"g05_track_receipt.json",doc)
   for lane,name in (("pc","G05"),("auxiliary","AUXILIARY")):
    v=inspect_source(root,day,lane)
    self.assertEqual(next(i for i in v["stages"] if i["stage"]==name)["state"],"GAP_REQUIRES_DIAGNOSIS")
    self.assertFalse(v["source_claims_independently_certified"])
   for bad in ({**doc,"same_day_official_meeting_heading_verified":False},{**doc,"source_sha256":"a"*64},{**doc,"weather":None}):
    self.put(root,"g05_track_receipt.json",bad)
    self.assertEqual(inspect_source(root,day,"auxiliary")["incidents"][0]["stage"],"AUXILIARY")
 def test_auxiliary_partial_targets_and_stale_conditions_are_not_green(self):
  from diagnostics.kyoto_incident_recovery import G05_COURSE_FIELDS
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);day="20261128"
   self.put(root,"receipt.json",{"day":day,"target_races":[10,11],"verified_races":[10],"observed_field_values":1})
   row={"active_horses":15,"cancelled_horses":[],"missing_body_weight_kg":[1,2],"missing_body_weight_change_kg":[2],"missing_race_conditions":["turf_going"]}
   replay={"replay_complete":True,"verified_races":[10],"race_rows":{"10":row},"course_observed":["weather"]}
   v=inspect_source(root,day,"auxiliary",field_review=replay)
   self.assertEqual(v["incidents"][0]["code"],"AUXILIARY_SOURCE_FIELD_GAPS")
   g=v["stages"][0]["observations"]["field_review"]
   self.assertEqual(g["missing_target_races"],[11])
   self.assertEqual(g["race_field_gaps"]["10"]["missing_body_weight_kg"],[1,2])
   self.assertEqual(g["course_missing_fields"],list(G05_COURSE_FIELDS[1:]))
   self.assertTrue(g["missingness_is_not_root_cause_proof"])
 def test_auxiliary_complete_planned_slot_is_not_forced_to_all_twelve(self):
  from diagnostics.kyoto_incident_recovery import G05_COURSE_FIELDS
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);day="20261129"
   row={"active_horses":10,"cancelled_horses":[11],"missing_body_weight_kg":[],"missing_body_weight_change_kg":[],"missing_race_conditions":[]}
   replay={"replay_complete":True,"verified_races":[11],"race_rows":{"11":row},"course_observed":list(G05_COURSE_FIELDS)}
   self.put(root,"receipt.json",{"day":day,"target_races":[11],"verified_races":[11]})
   v=inspect_source(root,day,"auxiliary",field_review=replay)
   self.assertFalse(v["incidents"]);self.assertFalse(v["source_claims_independently_certified"])
   for targets in ([],[11,11],[0],None):
    self.put(root,"receipt.json",{"day":day,"target_races":targets,"verified_races":[11]})
    self.assertTrue(inspect_source(root,day,"auxiliary",field_review=replay)["incidents"])
   self.put(root,"receipt.json",{"day":day,"target_races":[11]})
   self.assertTrue(inspect_source(root,day,"auxiliary")["incidents"])
   v=inspect_source(root,day,"pc",field_review=replay)
   g=next(s["observations"]["field_review"] for s in v["stages"] if s["stage"]=="G05")
   self.assertEqual(g["missing_target_races"],list(range(1,11))+[12])
 def test_late_native_actual_step_and_log_evidence(self):
  from unittest.mock import patch
  from diagnostics.kyoto_incident_recovery import diagnose_run,prehttp_evidence,OBSERVER_GUARD,OBSERVER_CAPTURE,PATH_PREFIX
  for rid,stamp,nominal,jids,delay in ((46122141318,"07:38:29",0,(140908775524,140908811758),26609),(46127895288,"08:53:25",1,(140926496313,140926532260),27505)):
   created="2026-11-28T"+stamp+"Z"
   path=PATH_PREFIX+"two-source-production-observer.yml"
   run={"id":rid,"name":f"kyoto-native:15 {nominal} 28 11 *","head_branch":"main","head_repository":{"full_name":REPO},"status":"completed","conclusion":"failure","event":"schedule","path":path,"head_sha":"a"*40,"created_at":created}
   def step(n,name,c):return {"number":n,"name":name,"status":"completed","conclusion":c}
   rows=[{"id":jid,"run_id":rid,"name":lane+"-originals-independent","status":"completed","conclusion":"failure","steps":[step(6,OBSERVER_GUARD,"failure"),step(8,OBSERVER_CAPTURE[lane],"skipped")]} for lane,jid in zip(("pc","sp"),jids)]
   doc={"total_count":2,"jobs":rows}
   raw=(created+" AssertionError: OUTSIDE_DAY_WINDOW_NO_HTTP\n").encode()
   with self.subTest(rid=rid),patch("diagnostics.kyoto_incident_recovery.gh",side_effect=[run,doc,{"total_count":0,"artifacts":[]}]),patch("diagnostics.kyoto_incident_recovery.job_log",return_value=raw):
    v=diagnose_run(rid,"unused","unused")
    for lane in ("pc","sp"):
     item=v["lanes"][lane];e=item["pre_http_guard_evidence"]
     self.assertEqual(item["incidents"][0]["stage"],"PRE_HTTP")
     self.assertEqual(e["run_registration_delay_seconds"],delay)
     self.assertTrue(e["guard_reason_verified"])
     self.assertFalse(e["source_success_certified"])
     self.assertFalse(e["upstream_scheduler_root_cause_proved"])
     self.assertTrue(item["archive_error_secondary_unresolved"])
     self.assertFalse(item["artifact_authenticated"])
   missing=prehttp_evidence(run,path,"pc","20261128",doc,read_log=lambda _:b"not a verified exception")
   self.assertFalse(missing["guard_reason_verified"])
   wrong=prehttp_evidence(run,path,"pc","20261128",doc,read_log=lambda _:b"2026-11-28T01:15:01Z AssertionError: OUTSIDE_DAY_WINDOW_NO_HTTP")
   self.assertFalse(wrong["guard_reason_verified"])
   rows[0]["steps"][1]["conclusion"]="success"
   self.assertIsNone(prehttp_evidence(run,path,"pc","20261128",doc,read_log=lambda _:raw))
 def test_cushion_actual_late_guard_distinct_from_archive(self):
  from unittest.mock import patch
  from diagnostics.kyoto_incident_recovery import diagnose_run,PATH_PREFIX,CUSHION_CAPTURE,prehttp_evidence
  rid=46127940166;jid=140926589833;path=PATH_PREFIX+"cushion-source.yml"
  run={"id":rid,"head_branch":"main","head_repository":{"full_name":REPO},"status":"completed","conclusion":"failure","event":"workflow_run","path":path,"head_sha":"a"*40,"created_at":"2026-11-28T08:54:02Z"}
  doc={"total_count":1,"jobs":[{"id":jid,"run_id":rid,"name":"cushion-source-only","status":"completed","conclusion":"failure","steps":[{"number":5,"name":CUSHION_CAPTURE,"status":"completed","conclusion":"failure"}]}]}
  raw=b"2026-11-28T08:54:10.6040048Z ValueError: cushion_live_guard_no_http\n"
  with patch("diagnostics.kyoto_incident_recovery.gh",side_effect=[run,doc,{"total_count":0,"artifacts":[]}]),patch("diagnostics.kyoto_incident_recovery.job_log",return_value=raw):
   item=diagnose_run(rid,"unused","unused")["lanes"]["cushion"]
   self.assertEqual(item["incidents"][0]["code"],"CUSHION_LIVE_GUARD_OUTSIDE_WINDOW_NO_HTTP")
   self.assertTrue(item["pre_http_guard_evidence"]["guard_reason_verified"])
   self.assertFalse(item["artifact_authenticated"])
  for other in (b"2026-11-28T08:54:10Z raise ValueError(\"cushion_live_guard_no_http\")",b"2026-11-28T07:54:10Z ValueError: cushion_live_guard_no_http",b""):
   self.assertIsNone(prehttp_evidence(run,path,"cushion","20261128",doc,read_log=lambda _:other))
if __name__=="__main__":unittest.main()

class ForensicContinuityTests(unittest.TestCase):
 def test_preserve_reopen_and_reject_tampering_without_plaintext(self):
  from diagnostics.kyoto_forensic_continuity import capture,restore
  run={"id":101,"head_sha":"a"*40}
  jobs={"total_count":3,"jobs":[{"id":1,"run_id":101,"conclusion":"success"},{"id":2,"run_id":101,"conclusion":"failure"},{"id":3,"run_id":101,"conclusion":"skipped"}]}
  arts={"total_count":0,"artifacts":[]}
  raw=b"secret-token-for-test\nTraceback (most recent call last):\nUnexpectedError: private data"
  called=[]
  def logs(jid):
   called.append(jid)
   if jid==2:raise ValueError("private unavailable")
   return raw
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp);m,cache=capture(run,jobs,arts,out,"a"*64,logs,clock=lambda:0)
   self.assertEqual(m["state"],"SEALED_WITH_EVIDENCE_GAPS");self.assertEqual(cache,{1:raw})
   self.assertEqual(called,[1,2])
   self.assertEqual(m["log_index"][0]["exception_line_refs"][0]["line"],2)
   self.assertNotIn(b"secret-token",(out/"forensic.json").read_bytes())
   self.assertNotIn(raw,(out/"forensic.aesgcm").read_bytes())
   self.assertIn("1",restore(out,"a"*64,run)["logs"])
   with self.assertRaises(ValueError):restore(out,"a"*64,{"id":102,"head_sha":"a"*40})
   p=out/"forensic.aesgcm";p.write_bytes(p.read_bytes()+b"x")
   with self.assertRaises(ValueError):restore(out,"a"*64,run)
 def test_unknown_receipt_remains_open_with_exact_reopen_pointer(self):
  from diagnostics.kyoto_forensic_continuity import obligations
  import hashlib
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);value="NovelParser: unexpected private token"
   raw=json.dumps({"day":"20261129","reason":value,"races":{"1":{"reason":value}}}).encode()
   (root/"receipt.json").write_bytes(raw)
   meta=inspect_source(root,"20261129","pc")
   refs=meta["receipt_failure_refs"]["refs"]
   self.assertEqual(len(refs),2)
   self.assertEqual(refs[0]["file_sha256"],hashlib.sha256(raw).hexdigest())
   self.assertEqual(refs[0]["value_sha256"],hashlib.sha256(value.encode()).hexdigest())
   self.assertNotIn(value,json.dumps(meta))
   self.assertTrue(any(i["cause_status"]=="ROOT_CAUSE_NOT_YET_PROVED" for i in meta["incidents"]))
   meta["artifact_authenticated"]=True;meta["artifact_id"]=7
   report={"source_run_id":3,"workflow_head_sha":"a"*40,"lanes":{"pc":meta},"jobs":[{"job_id":1}]}
   rows=obligations(report)
   self.assertTrue(rows);self.assertEqual(rows,obligations(report))
   self.assertTrue(all(not x["root_cause_proved"] and x["state"]=="OPEN_REPAIR_REQUIRED" for x in rows))
 def test_skipped_source_not_lost_in_empty_incident_list(self):
  from diagnostics.kyoto_forensic_continuity import obligations
  report={"source_run_id":3,"workflow_head_sha":"a"*40,"lanes":{"cushion":{"source_acquisition_state":"PRODUCER_NOT_EXECUTED_SKIP_REASON_UNVERIFIED","incidents":[]}},"jobs":[{"job_id":1}]}
  rows=obligations(report)
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0]["stage"],"PRODUCER_SKIP")
  self.assertFalse(rows[0]["root_cause_proved"])

 def test_rendered_fallback_kept_separate_from_raw_guard_evidence(self):
  from diagnostics.kyoto_forensic_continuity import capture,restore
  from diagnostics.kyoto_incident_recovery import forensic_job_log
  from unittest.mock import patch
  import subprocess
  run={"id":101,"head_sha":"a"*40}
  jobs={"total_count":1,"jobs":[{"id":1,"run_id":101,"conclusion":"failure"}]}
  arts={"total_count":0,"artifacts":[]}
  def unavailable(jid):raise subprocess.CalledProcessError(1,["gh","api"])
  def rendered(args,**kw):
   self.assertEqual(args,["gh","run","view","101","--repo","papaneko-ai/kyoto-keiba-ai","--job","1","--log"])
   kw["stdout"].write(b"job step 2026-11-28T10:00:00Z NovelError: masked")
  with tempfile.TemporaryDirectory() as tmp,patch("diagnostics.kyoto_incident_recovery.subprocess.run",side_effect=rendered):
   m,cache=capture(run,jobs,arts,tmp,"a"*64,lambda jid:forensic_job_log(101,jid,read_raw=unavailable),clock=lambda:0)
   self.assertEqual(m["state"],"SEALED_WITH_RENDERED_LOGS")
   self.assertEqual(cache,{})
   self.assertEqual(m["log_index"][0]["log_format"],"GH_RUN_VIEW_RENDERED")
   self.assertIn("1",restore(tmp,"a"*64,run)["logs"])
 def test_workout_preday_roster_pending_and_missing_races_distinct(self):
  from diagnostics.kyoto_incident_recovery import workout_incidents
  rows=[{"race":i,"status":"OFFICIAL_ROSTER_NOT_AVAILABLE"} for i in range(1,13)]
  proof=[{"race":i} for i in (9,10,11,12,9,10,11,12)]
  index={"state":"PRIMARY_INDEX_NOT_PRESERVED"}
  got=workout_incidents("20261129","2026-11-28T11:32:13Z",rows,proof,[],index)
  self.assertEqual({x["code"] for x in got},{"WORKOUT_PREDAY_ROSTER_JOIN_PENDING","WORKOUT_SOURCE_RACES_NOT_PRESERVED"})
  self.assertEqual(next(x for x in got if x["code"]=="WORKOUT_SOURCE_RACES_NOT_PRESERVED")["missing_races"],list(range(1,9)))
  self.assertTrue(all(not x["root_cause_closed"] for x in got))
  self.assertNotIn("WORKOUT_PREDAY_ROSTER_JOIN_PENDING",{x["code"] for x in workout_incidents("20261129","2026-11-29T00:00:00Z",rows,proof,[],index)})
 def test_workout_index_independent_shape_and_tamper(self):
  from diagnostics.kyoto_incident_recovery import workout_index_review,REPO,digest
  from cryptography.hazmat.primitives.ciphers.aead import AESGCM
  raw=b'<a href="/race/20261129-kyoto-09/">9</a><a href="/race/20261129-kyoto-01">1</a><a href="https://other.example/race/20261129-kyoto-02/">2</a>'
  key="a"*64;aad=f"kyoto-workout-navigation-v1|{REPO}|123|20261129|PRIMARY_INDEX".encode();nonce=b"n"*12
  blob=nonce+AESGCM(bytes.fromhex(key)).encrypt(nonce,raw,aad)
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/"primary_index.aesgcm";p.write_bytes(blob)
   m={"state":"INDEX_SEALED","filename":p.name,"archive_aad":aad.decode(),"captured_utc":"2026-11-28T11:32:13Z","ciphertext_sha256":digest(blob),"source_sha256":digest(raw),"bytes":len(raw),"discovery_state":"PARSER_RETURNED_RACES","discovered_races":[9]}
   v=workout_index_review(tmp,{"primary_index":m},"20261129",123,key)
   self.assertEqual(v["state"],"OBSERVED_ALTERNATE_LINK_SHAPE");self.assertEqual(v["alternate_shape_races"],[1]);self.assertEqual(v["independent_exact_races"],[9])
   self.assertEqual(workout_index_review(tmp,{"primary_index":dict(m,discovered_races=[8])},"20261129",123,key)["state"],"PARSER_INVENTORY_DISAGREEMENT")
   self.assertFalse(v["source_success_certified"])
   p.write_bytes(blob+b"x")
   self.assertEqual(workout_index_review(tmp,{"primary_index":m},"20261129",123,key)["state"],"PRIMARY_INDEX_AUTHENTICATION_OR_REPLAY_FAILED")
 def test_log_gap_always_has_open_repair_obligation(self):
  from diagnostics.kyoto_forensic_continuity import obligations
  report={"source_run_id":3,"workflow_head_sha":"a"*40,"lanes":{},"jobs":[{"job_id":1},{"job_id":2}],"forensic_evidence":{"state":"SEALED_WITH_EVIDENCE_GAPS","log_index":[{"job_id":1,"state":"LOG_UNAVAILABLE"},{"job_id":2,"state":"LOG_BUDGET_EXHAUSTED"}]}}
  rows=obligations(report)
  self.assertEqual(len(rows),2);self.assertEqual(len({x["incident_id"] for x in rows}),2)
  self.assertTrue(all(x["state"]=="OPEN_REPAIR_REQUIRED" and not x["root_cause_proved"] for x in rows))

class IncidentMetadataRepairTests(unittest.TestCase):
 def test_uses_existing_recovery_transport(self):
  from unittest.mock import patch
  from diagnostics.kyoto_incident_recovery import gh
  trace=[];expected={"total_count":0,"artifacts":[]}
  with patch("diagnostics.kyoto_repair_control.recover_collection",return_value=expected) as f:
   self.assertEqual(gh("repos/"+REPO+"/actions/runs/123/artifacts?per_page=100",trace),expected)
   f.assert_called_once_with("actions/runs/123/artifacts?per_page=100","artifacts",trace=trace)
 def test_failed_job_index_does_not_stop_artifact_index(self):
  from unittest.mock import patch
  from diagnostics.kyoto_incident_recovery import diagnose_run
  run={"id":123,"head_branch":"main","head_repository":{"full_name":REPO},"status":"completed","event":"workflow_dispatch","path":".github/workflows/kyoto-20261128-29-cushion-source.yml","head_sha":"a"*40,"created_at":"2026-11-28T03:00:00Z"}
  with patch("diagnostics.kyoto_incident_recovery.gh",side_effect=[run,TimeoutError(),{"total_count":0,"artifacts":[]}]):
   r=diagnose_run(123,"unused","unused")
  self.assertFalse(r["metadata_recovery"]["jobs"]["complete"])
  self.assertTrue(r["metadata_recovery"]["artifacts"]["complete"])
  self.assertTrue(any(x["code"]=="JOBS_INDEX_UNAVAILABLE" for x in r["open_repair_obligations"]))
 def test_failed_artifact_index_does_not_infer_missing_or_skip(self):
  from unittest.mock import patch
  from diagnostics.kyoto_incident_recovery import diagnose_run
  run={"id":123,"head_branch":"main","head_repository":{"full_name":REPO},"status":"completed","event":"workflow_dispatch","path":".github/workflows/kyoto-20261128-29-cushion-source.yml","head_sha":"a"*40,"created_at":"2026-11-28T03:00:00Z"}
  job={"id":1,"run_id":123,"name":"cushion-source-only","status":"completed","conclusion":"success","steps":[]}
  with patch("diagnostics.kyoto_incident_recovery.gh",side_effect=[run,{"total_count":1,"jobs":[job]},TimeoutError()]):
   r=diagnose_run(123,"unused","unused")
  self.assertTrue(r["metadata_recovery"]["jobs"]["complete"])
  self.assertEqual(r["lanes"]["cushion"]["artifact_evidence"]["state"],"ARTIFACT_INDEX_UNAVAILABLE")
  self.assertTrue(any(x["code"]=="ARTIFACTS_INDEX_UNAVAILABLE" for x in r["open_repair_obligations"]))
 def test_run_zip_third_channel_restoration_and_no_job_credit(self):
  import io,zipfile
  from diagnostics.kyoto_forensic_continuity import preserve_run_zip,restore_run_zip
  bio=io.BytesIO()
  with zipfile.ZipFile(bio,"w") as z:z.writestr("job/1.txt",b"private log")
  raw=bio.getvalue();run={"id":123,"head_sha":"a"*40}
  with tempfile.TemporaryDirectory() as td:
   m=preserve_run_zip(run,td,"a"*64,lambda rid:raw)
   self.assertFalse(m["job_attribution_verified"])
   self.assertEqual(restore_run_zip(run,td,"a"*64),raw)
   self.assertNotIn(b"private log",(Path(td)/"run_log_zip.aesgcm").read_bytes())
   with self.assertRaises(ValueError):restore_run_zip({"id":124,"head_sha":"a"*40},td,"a"*64)
   p=Path(td)/"run_log_zip.aesgcm";p.write_bytes(p.read_bytes()+b"x")
   with self.assertRaises(ValueError):restore_run_zip(run,td,"a"*64)
 def test_third_channel_invoked_when_both_indexes_unavailable(self):
  import io,zipfile
  from unittest.mock import patch
  from diagnostics.kyoto_incident_recovery import diagnose_run
  run={"id":123,"head_branch":"main","head_repository":{"full_name":REPO},"status":"completed","event":"workflow_dispatch","path":".github/workflows/kyoto-20261128-29-cushion-source.yml","head_sha":"a"*40,"created_at":"2026-11-28T03:00:00Z"}
  b=io.BytesIO()
  with zipfile.ZipFile(b,"w") as z:z.writestr("job.txt","log")
  with tempfile.TemporaryDirectory() as td,patch.dict("os.environ",{"ARCHIVE_KEY":"a"*64}),patch("diagnostics.kyoto_incident_recovery.gh",side_effect=[run,TimeoutError(),TimeoutError()]),patch("diagnostics.kyoto_incident_recovery.run_log_zip",return_value=b.getvalue()) as z:
   r=diagnose_run(123,"unused","unused",evidence_out=td)
   z.assert_called_once_with(123)
   self.assertEqual(r["run_log_zip_recovery"]["state"],"RUN_LOG_ZIP_RECOVERED_NOT_JOB_ATTRIBUTED")
   self.assertEqual(r["forensic_evidence"]["state"],"FORENSIC_CAPSULE_UNAVAILABLE")
