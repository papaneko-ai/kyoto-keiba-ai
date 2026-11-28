import copy,unittest
from datetime import datetime,timezone
from diagnostics.kyoto_weekend_closure_review import index,slots,coverage_gaps,REPO,PREFIX,FAMILIES,HORSE,TRACK,MARKETS,EXTRA
DAY="20261129";FILE="two-source-production-observer.yml";NOW=datetime(2026,11,29,14,tzinfo=timezone.utc)
def workouts(d):
 w={"schema":"kyoto_independent_workout_day_replay.v1","day":DAY,"races":{}}
 for n,r in d["races"].items():
  if r.get("state")!="ROSTER_VERIFIED":continue
  w["races"][n]={"named_roster_digest":r["named_roster_digest"],"start":r["start_utc"],"horses":{h:{"state":"INDEPENDENT_WORKOUT_SOURCE_REPLAYED","mode":"PRIMARY","value_digest":"c"*64,"record_count":2,"source_proofs":[{"run_id":"3","sha256":"d"*64,"utc":"2026-11-28T11:00:00+00:00","provider":"white-green.jp"}]} for h in r["horses"] if r["horses"][h].get("workout")}}
 return w
def assess(day,d,allowed):
 return coverage_gaps(day,d,allowed,workouts(d),[3])
def run(rid=1,event="schedule",title="kyoto-native:15 0 29 11 *"):
 return {"id":rid,"event":event,"name":title,"head_repository":{"full_name":REPO},"head_branch":"main","path":PREFIX+FILE,"head_sha":"a"*40,"created_at":"2026-11-29T00:17:00Z","status":"completed","conclusion":"success"}
def data():
 def proof(after=False):
  return {"state":"SOURCE_VERIFIED","run_id":"1","utc":"2026-11-29T10:00:00Z" if after else "2026-11-29T00:00:00Z","sha256":"a"*64,"value_digest":"b"*64}
 r={"state":"ROSTER_VERIFIED","roster_digest":"a"*64,"named_roster_digest":"b"*64,"start_utc":"2026-11-29T05:00:00Z","racecard":proof(),"horses":{str(n):{f:proof() for f in HORSE} for n in (1,2)},"track":{f:proof() for f in TRACK},"supplementary_track_observations":{f:proof() for f in EXTRA},"markets":{f:{**proof(),"cancelled_horses":[]} for f in MARKETS},"paired_same_slot":True,"postrace":{"state":"DUAL_PAGE_FINAL_SOURCE_RECONCILED","run_id":"1","result":proof(True),"payout":proof(True)}}
 return {"schema":"kyoto_impl30_day_source_coverage.v1","day":DAY,"race_denominator":12,"postrace_history_index_complete":True,"races":{str(n):copy.deepcopy(r) for n in range(1,13)}}
class ClosureTests(unittest.TestCase):
 def test_exact_native_slots_not_inferred_from_dispatch_count(self):
  rs=[run()]+[run(i,"workflow_dispatch","workflow_dispatch") for i in (2,3,4)]
  v=slots(DAY,FILE,index(DAY,FILE,{"total_count":4,"workflow_runs":rs}),NOW)
  self.assertEqual([x["state"] for x in v],["NATIVE_RUN_COMPLETED"]+["NATIVE_SLOT_NOT_OBSERVED"]*3)
  self.assertEqual(v[0]["late_seconds"],120)
 def test_external_slot_observations_are_not_native_or_source_credit(self):
  from diagnostics.kyoto_weekend_closure_review import external_slots
  rs=[run(),run(2,"workflow_dispatch","workflow_dispatch")]
  v=external_slots(DAY,FILE,index(DAY,FILE,{"total_count":2,"workflow_runs":rs}),NOW)
  self.assertEqual([x["state"] for x in v],["DISPATCH_COMPLETED"]+["DISPATCH_NOT_OBSERVED"]*3)
  self.assertEqual(v[0]["run_ids"],[2]);self.assertFalse(v[0]["provider_proved"]);self.assertFalse(v[0]["source_success_certified"])
  rs.append(run(3,"workflow_dispatch","workflow_dispatch"))
  self.assertEqual(external_slots(DAY,FILE,index(DAY,FILE,{"total_count":3,"workflow_runs":rs}),NOW)[0]["state"],"DISPATCH_AMBIGUOUS")
 def test_sp_run_credit_is_market_only(self):
  d=data();r=d["races"]["1"]
  for m in MARKETS:r["markets"][m]["run_id"]="8"
  r["racecard"]["run_id"]="8"
  v=coverage_gaps(DAY,d,[1],workouts(d),[3],allowed_sp_market_run_ids=[8])
  self.assertEqual(v["counts"]["quinella"]["verified"],12)
  self.assertEqual(v["counts"]["paired_market_same_slot"]["verified"],12)
  self.assertEqual(v["counts"]["racecard"]["verified"],11)
 def test_sp_only_roster_credit_requires_exact_independent_card_not_market_id(self):
  d=data();r=d["races"]["1"];r["roster_source_channel"]="SP"
  r["racecard"].update(run_id="8",channel="SP",source_kind="INDEPENDENT_SP_PRESTART_ROSTER")
  p={k:r[k] for k in ("roster_digest","named_roster_digest","start_utc")}
  p["racecard"]={k:v for k,v in r["racecard"].items() if k not in ("state","run_id")}
  p["horses"]={"1":{},"2":{}}
  slots=[{"day":DAY,"run_id":"8","races":{"1":p}}]
  def check(doc,source=slots,allowed=(8,)):
   return coverage_gaps(DAY,doc,[1,8],workouts(doc),[3],allowed_sp_market_run_ids=allowed,verified_sp_roster_slots=source)
  good=check(d)
  self.assertEqual(good["counts"]["racecard"]["verified"],12)
  self.assertEqual(good["counts"]["profile"]["verified"],22)
  self.assertEqual(good["counts"]["prior_form"]["verified"],22)
  self.assertFalse(good["all_reviewed_cells_present"])
  self.assertEqual(check(d,[])["counts"]["racecard"]["verified"],11)
  self.assertEqual(check(d,slots,())["counts"]["racecard"]["verified"],11)
  for field,value in (("sha256","f"*64),("run_id","9"),("utc","2026-11-29T00:01:00Z"),("source_kind","OTHER")):
   bad=copy.deepcopy(d);bad["races"]["1"]["racecard"][field]=value
   result=check(bad);self.assertEqual(result["counts"]["racecard"]["verified"],11)
   self.assertEqual(result["counts"]["profile"]["unknown_denominator_races"],1)
  bad=copy.deepcopy(d);bad["races"]["1"]["named_roster_digest"]="f"*64
  self.assertEqual(check(bad)["counts"]["racecard"]["verified"],11)
 def test_duplicate_native_and_index(self):
  rs=[run(),run(2)]
  self.assertEqual(slots(DAY,FILE,index(DAY,FILE,{"total_count":2,"workflow_runs":rs}),NOW)[0]["state"],"NATIVE_SLOT_AMBIGUOUS")
  for bad in ({"total_count":3,"workflow_runs":rs},{"total_count":2,"workflow_runs":[run(),run()]},{"total_count":1,"workflow_runs":[{**run(),"head_branch":"other"}]}):
   with self.assertRaises(ValueError):index(DAY,FILE,bad)
 def test_every_required_family_mutation(self):
  d=data();v=assess(DAY,d,[1,2]);self.assertTrue(v["all_reviewed_cells_present"]);self.assertFalse(v["full_acquisition_certified"])
  for f in FAMILIES:
   d=data();r=d["races"]["1"]
   if f=="racecard":r[f]={}
   elif f in HORSE:r["horses"]["1"][f]={}
   elif f in TRACK:r["track"][f]={}
   elif f in MARKETS:r["markets"][f]={}
   elif f in EXTRA:r["supplementary_track_observations"][f]={}
   elif f=="paired_market_same_slot":r["paired_same_slot"]=False
   else:r["postrace"]["result" if f=="official_result" else "payout"]={}
   v=assess(DAY,d,[1,2]);self.assertFalse(v["all_reviewed_cells_present"],f);self.assertLess(v["counts"][f]["verified"],v["counts"][f]["expected"],f)
 def test_green_summary_not_accepted_unknown_denominator_and_conflict(self):
  d=data();d["full_data_acquisition_certified"]=True;d["races"]["1"]={"state":"ROSTER_OR_START_CONFLICT"}
  v=assess(DAY,d,[1,2]);self.assertEqual(v["counts"]["profile"]["unknown_denominator_races"],1);self.assertFalse(v["all_reviewed_cells_present"])
 def test_wrong_day_and_poststart_source(self):
  for utc in ("2026-11-28T00:00:00Z","2026-11-29T05:00:00Z","2026-11-29T05:01:00Z"):
   d=data();d["races"]["1"]["racecard"]["utc"]=utc
   self.assertFalse(assess(DAY,d,[1,2])["all_reviewed_cells_present"])
 def test_pair_different_run(self):
  d=data();d["races"]["1"]["markets"]["quinella"]["run_id"]="2"
  self.assertEqual(assess(DAY,d,[1,2])["counts"]["paired_market_same_slot"]["verified"],11)
 def test_missing_origin_and_cancellation_proof(self):
  for bad in ("99",None):
   d=data();d["races"]["1"]["racecard"]["run_id"]=bad
   self.assertEqual(assess(DAY,d,[1,2])["counts"]["racecard"]["verified"],11)
  d=data();del d["races"]["1"]["markets"]["quinella"]["cancelled_horses"];del d["races"]["1"]["markets"]["bracket_quinella"]["cancelled_horses"]
  self.assertEqual(assess(DAY,d,[1,2])["counts"]["paired_market_same_slot"]["verified"],11)
  d=data();d["postrace_history_index_complete"]=False
  self.assertEqual(assess(DAY,d,[1,2])["counts"]["official_payout"]["verified"],0)
 def test_workout_two_previous_utc_date_slots_and_failed_run(self):
  v=slots(DAY,"workout-source.yml",[],NOW)
  old={**run(),"path":PREFIX+"workout-source.yml","created_at":"2026-11-27T11:32:00Z","name":"kyoto-native:30 11 27 11 *"}
  self.assertEqual(len(index("20261127","workout-source.yml",{"total_count":1,"workflow_runs":[old]})),1)
  with self.assertRaises(ValueError):index("20261127",FILE,{"total_count":0,"workflow_runs":[]})
  self.assertEqual([x["due_utc"] for x in v],["2026-11-28T11:30:00+00:00","2026-11-28T22:30:00+00:00"])
  r=run();r["conclusion"]="failure"
  v=slots(DAY,FILE,index(DAY,FILE,{"total_count":1,"workflow_runs":[r]}),NOW)
  self.assertEqual(v[0]["state"],"NATIVE_RUN_UNSUCCESSFUL")
 def test_incomplete_race_inventory(self):
  d=data();del d["races"]["12"]
  with self.assertRaises(ValueError):assess(DAY,d,[1,2])
 def test_producer_job_artifact_classification_counterexamples(self):
  from diagnostics.kyoto_job_artifact_state import JOB,classify_artifact,SKIPPED
  for (filename,lane),name in JOB.items():
   j={"id":7,"run_id":1,"name":name,"status":"completed","conclusion":"skipped","steps":None}
   def state(rows,matches=None,total=None):
    return classify_artifact(filename,lane,1,matches or [],{"jobs":rows,"total_count":len(rows) if total is None else total})
   self.assertEqual(state([j])["state"],SKIPPED)
   self.assertFalse(state([j])["skip_reason_verified"])
   for mutated in ({**j,"run_id":2},{**j,"name":"other"},{**j,"status":"in_progress"}):
    self.assertEqual(state([mutated])["state"],"MISSING_JOB_STATE_UNVERIFIED")
   self.assertEqual(state([j],total=2)["state"],"MISSING_JOB_STATE_UNVERIFIED")
   self.assertEqual(state([j,{**j,"id":8}])["state"],"MISSING_JOB_STATE_UNVERIFIED")
   self.assertEqual(state([j],[{"id":9,"expired":True}])["state"],"MISSING_EXPIRED_OR_AMBIGUOUS")
   self.assertEqual(state([j],[{"id":9,"expired":False},{"id":10,"expired":False}])["state"],"MISSING_EXPIRED_OR_AMBIGUOUS")
   self.assertEqual(state([j],[{"id":9,"expired":False}])["state"],"PRESENT")
   self.assertEqual(state([{**j,"conclusion":"success"}])["state"],"MISSING_AFTER_JOB_SUCCESS")
   self.assertEqual(state([{**j,"conclusion":"failure"}])["state"],"MISSING_AFTER_JOB_UNSUCCESSFUL")
 def test_collect_metadata_uses_job_index_for_missing_artifact(self):
  from unittest.mock import patch
  from diagnostics.kyoto_weekend_closure_review import collect_metadata
  file="cushion-source.yml";rid=46108030052;jid=140865067475
  row={**run(rid,"workflow_run","workflow_run"),"path":PREFIX+file}
  job={"id":jid,"run_id":rid,"name":"cushion-source-only","status":"completed","conclusion":"skipped"}
  def api(path,trace):
   if "/runs?created=" in path:
    rows=[row] if file in path else []
    return {"total_count":len(rows),"workflow_runs":rows}
   if "/artifacts?" in path:return {"total_count":0,"artifacts":[]}
   if "/jobs?" in path:return {"total_count":1,"jobs":[job]}
   raise AssertionError(path)
  with patch("diagnostics.kyoto_weekend_closure_review.gh",side_effect=api):
   metadata,errors=collect_metadata(DAY,NOW)
   self.assertFalse(errors)
   self.assertEqual(metadata[file]["runs"][0]["artifacts"]["cushion"],{"state":"JOB_SKIPPED_NO_ARTIFACT","ids":[],"job_id":jid,"job_conclusion":"skipped","skip_reason_verified":False})
   self.assertTrue(any(x["scope"]=="job_index" and x["run_id"]==rid for x in metadata[file]["metadata_recovery"]))
  def failed_api(path,trace):
   if "/jobs?" in path:raise TimeoutError()
   return api(path,trace)
  with patch("diagnostics.kyoto_weekend_closure_review.gh",side_effect=failed_api):
   metadata,errors=collect_metadata(DAY,NOW)
   self.assertFalse(errors)
   result=metadata[file]["runs"][0]
   self.assertEqual(result["job_index_error"],"TimeoutError")
   self.assertEqual(result["artifacts"]["cushion"]["state"],"MISSING_JOB_STATE_UNVERIFIED")
 def test_workout_wrong_source_run_roster_and_poststart_are_not_credited(self):
  d=data();w=workouts(d)
  self.assertEqual(coverage_gaps(DAY,d,[1,2],w,[3])["counts"]["workout"]["verified"],24)
  self.assertEqual(coverage_gaps(DAY,d,[1,2],w,[4])["counts"]["workout"]["verified"],0)
  self.assertEqual(coverage_gaps(DAY,d,[1,2])["counts"]["workout"]["verified"],0)
  for mutate in ("roster","future","secondary","source"):
   x=copy.deepcopy(w);r=x["races"]["1"];p=r["horses"]["1"]
   if mutate=="roster":r["named_roster_digest"]="f"*64
   elif mutate=="future":p["source_proofs"][0]["utc"]="2026-11-29T05:00:00+00:00"
   elif mutate=="secondary":p["mode"]="SECONDARY_CORROBORATED"
   else:p["source_proofs"][0]["provider"]="unknown.example"
   self.assertLess(coverage_gaps(DAY,d,[1,2],x,[3])["counts"]["workout"]["verified"],24)
 def test_cancelled_weight_only_with_exact_card_proof(self):
  d=data();r=d["races"]["1"]
  for f in ("body_weight_kg","body_weight_change_kg"):r["horses"]["1"][f]={}
  card=r["racecard"]
  e={"state":"CANCELLATION_STATUS_FROM_REPLAYED_CARD","day":DAY,"run_id":card["run_id"],"sha256":card["sha256"],"utc":card["utc"],"roster_digest":r["roster_digest"],"named_roster_digest":r["named_roster_digest"],"start_utc":r["start_utc"],"registered_horse_count":2,"cancelled_horses":[1]}
  cr={"schema":"kyoto_independent_cancellation_review.v1","day":DAY,"races":{"1":e}}
  v=coverage_gaps(DAY,d,[1,2],workouts(d),[3],cr)
  for f in ("body_weight_kg","body_weight_change_kg"):
   self.assertEqual(v["counts"][f],{"expected":23,"verified":23,"unknown_denominator_races":0})
   self.assertEqual(v["weight_not_applicable_counts"][f],1)
  self.assertEqual(v["counts"]["profile"]["expected"],24)
  self.assertEqual(v["counts"]["workout"]["verified"],24)
  self.assertEqual(v["races"][0]["registered_horses"],2)
  self.assertTrue(v["all_reviewed_cells_present"])
  for k,val in (("sha256","f"*64),("run_id","2"),("utc","2026-11-29T05:01:00Z"),("named_roster_digest","f"*64),("roster_digest","f"*64),("day","20261128"),("registered_horse_count",3),("cancelled_horses",[1,1]),("cancelled_horses",[3]),("cancelled_horses",[1,2])):
   bad=copy.deepcopy(cr);bad["races"]["1"][k]=val
   q=coverage_gaps(DAY,d,[1,2],workouts(d),[3],bad)
   self.assertEqual(q["counts"]["body_weight_kg"]["expected"],24,k)
   self.assertEqual(q["counts"]["body_weight_kg"]["verified"],23,k)
   self.assertFalse(q["all_reviewed_cells_present"],k)
  self.assertEqual(assess(DAY,d,[1,2])["counts"]["body_weight_kg"]["expected"],24)
 def test_supplemental_sp_reuses_only_present_originals_without_pc_credit(self):
  from diagnostics.kyoto_day_supplemental_replay import review_sp
  m={"index_complete":True,"runs":[{"id":i,"event":"workflow_dispatch","status":"completed","artifacts":{"sp":{"state":s}}} for i,s in ((1,"PRESENT"),(2,"JOB_SKIPPED_NO_ARTIFACT"),(3,"MISSING_AFTER_JOB_SUCCESS"),(4,"PRESENT"))]}
  def invoke(task,end):
   self.assertEqual(task[:3],("lane",DAY,REPO))
   self.assertEqual(task[-1],"SP")
   if task[3]==4:return {"error_class":"TIMEOUT"}
   self.assertEqual(task[3],1)
   return {"source_original_sha_utc_checked":True}
  def aggregate(day,entries):
   self.assertEqual(day,DAY)
   self.assertEqual([e["run"]["id"] for e in entries],[1,2,3,4])
   self.assertEqual(entries[1]["source_assessment"]["SP"],{})
   self.assertEqual(entries[2]["source_assessment"]["SP"],{})
   self.assertEqual(entries[3]["source_assessment"]["SP"],{"error_class":"TIMEOUT"})
   return {"schema":"kyoto_impl32_sp_handoff.v1","day":day,"race_denominator":12,"pc_denominator_modified":False,"prestart_certified":False,"market_verified":False,"live_acquisition_certified":False}
  v=review_sp(DAY,m,invoke=invoke,aggregate=aggregate)
  self.assertEqual(v["source_http_requests"],0)
  self.assertEqual(v["replay_errors"],[{"run_id":4,"error_class":"TIMEOUT"}])
  self.assertFalse(v["pc_denominator_modified"])
  self.assertEqual(v["source_inventory"][1]["artifact_state"],"JOB_SKIPPED_NO_ARTIFACT")
  with self.assertRaises(ValueError):review_sp(DAY,{**m,"runs":m["runs"]+[m["runs"][0]]},invoke=invoke,aggregate=aggregate)
  def bad(day,entries):return {**aggregate(day,entries),"market_verified":True}
  with self.assertRaises(ValueError):review_sp(DAY,m,invoke=invoke,aggregate=bad)
 def test_sp_market_replay_uses_exact_context_and_rejects_unbound_receipts(self):
  from diagnostics.kyoto_day_supplemental_replay import review_sp
  m={"index_complete":True,"runs":[{"id":i,"event":"workflow_dispatch","status":"completed","artifacts":{"sp":{"state":"PRESENT"}}} for i in (1,2,3)]}
  calls=[];context={"1":{"start_utc":"2026-11-29T05:00:00Z"}}
  def invoke(task,end):
   calls.append(task)
   return {"ciphertext_authenticated":task[3]!=3,"source_original_sha_utc_checked":True,"sp_market_slot":{"day":DAY,"run_id":str(99 if task[3]==2 else task[3]),"races":{"1":{}}}}
  def aggregate(day,entries):
   return {"schema":"kyoto_impl32_sp_handoff.v1","day":day,"race_denominator":12,"pc_denominator_modified":False,"prestart_certified":False,"market_verified":False,"live_acquisition_certified":False}
  v=review_sp(DAY,m,invoke=invoke,aggregate=aggregate,sp_context=context)
  self.assertEqual(sorted(t[3] for t in calls),[1,2,3]);self.assertTrue(all(t[5]==context for t in calls))
  self.assertEqual([s["run_id"] for s in v["verified_market_slots"]],["1"])
  self.assertFalse(v["market_verified"])
 def test_supplemental_cushion_delegates_authenticated_observations_only(self):
  from diagnostics.kyoto_day_supplemental_replay import replay_cushions
  d=data();before=copy.deepcopy(d)
  def read(rid,path):
   if rid==2:raise ValueError("bad_cipher")
   if rid==3:return {"day":"20261128"}
   return {"day":DAY,"captured_at_utc":"2026-11-29T00:00:00Z","source_sha256":"a"*64}
  def combine(day,c,obs):
   self.assertEqual(c,before)
   self.assertEqual([x[0] for x in obs],[1])
   return {"schema":"kyoto_impl36_cushion_day.v1","day":day,"race_denominator":12,"races":{str(n):{} for n in range(1,13)},"prediction_ready":False,"full_data_acquisition_certified":False}
  v=replay_cushions(DAY,d,[(1,"a"),(2,"b"),(3,"c")],read,combine)
  self.assertEqual(d,before)
  self.assertEqual([x["run_id"] for x in v["authenticated_observations"]],["1"])
  self.assertEqual([x["run_id"] for x in v["replay_errors"]],[2,3])
  self.assertEqual(v["source_http_requests"],0)
  with self.assertRaises(ValueError):replay_cushions(DAY,d,[(1,"a"),(1,"b")],read,combine)
  def bad(day,c,obs):return {**combine(day,c,obs),"prediction_ready":True}
  with self.assertRaises(ValueError):replay_cushions(DAY,d,[(1,"a")],read,bad)
class PostraceIsolationTests(unittest.TestCase):
 def candidates(self):
  return {"index_complete":True,"runs":[{"id":i,"head_sha":"a"*40,"event":"workflow_dispatch","status":"completed","artifacts":{"postrace":{"state":"PRESENT","ids":[100+i]}}} for i in (1,2)]}
 def history(self,complete=True):
  return {"schema":"kyoto_impl30_postrace_replay.v1","day":DAY,"prior_artifact_index_complete":complete,"run_evidence":[{"run_id":1,"recomputed_races":12},{"run_id":2,"error_class":"TimeoutError"}],"races":{}}
 def invoke(self,history=None,*,fail_decrypt=False,fail_replay=False,fail_include=False):
  from diagnostics.kyoto_weekend_closure_review import replay_postrace_isolated
  before=data();orig=copy.deepcopy(before);calls=[]
  def download(rid,name,path,repo,timeout):
   self.assertEqual(repo,REPO);self.assertLessEqual(timeout,25)
   calls.append(("download",rid))
   if rid==2:raise TimeoutError()
  def decrypt(src,raw,**kw):
   calls.append(("decrypt",int(kw["run_id"])))
   if fail_decrypt:raise ValueError()
   raw.mkdir()
  def replay(raw,**kw):
   calls.append(("replay",int(kw["current_run"])))
   if fail_replay:raise ValueError()
   return self.history() if history is None else history
  def include(c,h,**kw):
   calls.append(("include",h["prior_artifact_index_complete"]))
   if fail_include:
    c["races"]["1"].clear();raise ValueError()
   c["postrace_history_index_complete"]=h["prior_artifact_index_complete"]
   return c
  result,state=replay_postrace_isolated(DAY,self.candidates(),before,{},{},"key",download=download,decrypt=decrypt,replay=replay,include=include,clock=lambda:0)
  self.assertEqual(before,orig)
  self.assertEqual(result["races"]["1"]["racecard"],orig["races"]["1"]["racecard"])
  self.assertEqual(result["races"]["1"]["markets"],orig["races"]["1"]["markets"])
  self.assertEqual(coverage_gaps(DAY,result,[1,2])["counts"]["racecard"]["verified"],12)
  self.assertEqual(coverage_gaps(DAY,result,[1,2])["counts"]["official_result"]["verified"],0)
  return result,state,calls
 def test_latest_archive_loss_falls_back_without_false_complete_history(self):
  v,s,c=self.invoke()
  self.assertEqual(s["state"],"HISTORY_REPLAYED_INCOMPLETE")
  self.assertEqual(c,[("download",2),("download",1),("decrypt",1),("replay",1),("include",False)])
  self.assertFalse(v["postrace_history_index_complete"])
  self.assertEqual(s["attempts"][0]["error_class"],"TimeoutError")
 def test_transient_latest_archive_loss_can_be_proved_recovered(self):
  h=self.history();h["run_evidence"][1]={"run_id":2,"recomputed_races":12}
  v,s,c=self.invoke(h)
  self.assertEqual(s["state"],"HISTORY_REPLAYED");self.assertEqual(s["recovered_prior_failed_runs"],[2]);self.assertTrue(v["postrace_history_index_complete"])
  self.assertEqual(c.count(("replay",1)),1)
 def test_all_original_failures_do_not_erase_daytime(self):
  v,s,c=self.invoke(fail_decrypt=True)
  self.assertEqual(s["state"],"ALL_POSTRACE_ORIGINAL_REOPENS_FAILED_DAYTIME_RETAINED")
  self.assertEqual(c,[("download",2),("download",1),("decrypt",1)])
  self.assertFalse(v["postrace_history_index_complete"])
 def test_replay_or_include_error_cannot_erase_verified_cells(self):
  for args in ({"fail_replay":True},{"fail_include":True}):
   v,s,c=self.invoke(**args)
   self.assertEqual(s["state"],"POSTRACE_REPLAY_FAILED_DAYTIME_RETAINED")
   self.assertFalse(v["postrace_history_index_complete"])
 def test_daytime_checkpoint_has_independent_counts_and_digest(self):
  import tempfile,json,hashlib,os
  from pathlib import Path
  from unittest.mock import patch
  from diagnostics.kyoto_weekend_closure_review import write_daytime_checkpoint
  d=data();d["postrace_history_index_complete"]=False
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{"GITHUB_RUN_ID":"42"}):
   out=Path(tmp);v=write_daytime_checkpoint(DAY,out,d,[1,2],[],[])
   raw=(out/"daytime_coverage_checkpoint.json").read_bytes().rstrip(b"\n")
   p=json.loads(raw)
   self.assertEqual(p["review_run_id"],"42")
   self.assertEqual(p["coverage"],v)
   self.assertEqual(p["coverage"]["counts"]["racecard"]["verified"],12)
   self.assertEqual(p["coverage"]["counts"]["official_result"]["verified"],0)
   self.assertEqual(hashlib.sha256(raw).hexdigest(),(out/"daytime_coverage_checkpoint.sha256").read_text().strip())
   self.assertFalse(p["full_acquisition_certified"])

class SPNamedBridgeTests(unittest.TestCase):
 def fixture(self):
  from diagnostics.kyoto_weekend_closure_review import canon,digest
  names=((1,1,"馬A"),(2,2,"馬B"))
  card={"sha256":"a"*64,"utc":"2026-11-29T01:00:00+00:00","channel":"SP","source_kind":"INDEPENDENT_SP_PRESTART_ROSTER","value_digest":"c"*64}
  p={"roster_digest":"d"*64,"named_roster_digest":digest(canon(names)),"start_utc":"2026-11-29T02:45:00+00:00","racecard":card,"horses":{"1":{},"2":{}},"numbers":[1,2],"track":{}}
  d=data();d["races"]["1"]={**p,"state":"ROSTER_VERIFIED","roster_source_channel":"SP","racecard":{"state":"SOURCE_VERIFIED","run_id":"8",**card}}
  return d,[{"day":DAY,"run_id":"8","races":{"1":p}}],names,p
 def test_selected_sp_card_names_link_both_readers(self):
  from diagnostics.kyoto_weekend_closure_review import bridge_sp_named_rosters
  d,slots,names,p=self.fixture();orig=copy.deepcopy(d);calls=[]
  def read(day,rid,key,targets,timeout):
   calls.append((day,rid,targets,timeout))
   return {1:{"named":names,"proof":p}}
  r,st,v=bridge_sp_named_rosters(DAY,d,slots,{1:None},{}, "key",read=read,clock=lambda:0)
  self.assertEqual(r[1],names);self.assertEqual(st[1],p["start_utc"])
  self.assertEqual(calls,[(DAY,8,[1],15)])
  self.assertEqual(v["verified_races"],[1]);self.assertNotIn("馬A",str(v));self.assertEqual(d,orig)
  self.assertFalse(v["raw_names_published"])
 def test_conflicts_existing_and_wrong_slot_never_overwritten(self):
  from diagnostics.kyoto_weekend_closure_review import bridge_sp_named_rosters
  for conflict,existing,wrong in (([1],{},False),([],{1:((1,1,"other"),)},False),([],{},True)):
   d,slots,names,p=self.fixture()
   if wrong:slots[0]["run_id"]="9"
   def denied(*a):raise AssertionError("no archive reopen")
   r,st,v=bridge_sp_named_rosters(DAY,d,slots,existing,{},"key",conflict,read=denied)
   self.assertEqual(r,existing);self.assertEqual(v["verified_races"],[])
 def test_name_digest_and_source_mutations_rejected(self):
  from diagnostics.kyoto_weekend_closure_review import bridge_sp_named_rosters
  for change in ("names","card","start","numbers"):
   d,slots,names,p=self.fixture();q=copy.deepcopy(p)
   if change=="names":names=((1,1,"other"),names[1])
   if change=="card":q["racecard"]["sha256"]="b"*64
   if change=="start":q["start_utc"]="2026-11-29T03:00:00+00:00"
   if change=="numbers":q["numbers"]=[1,3]
   r,st,v=bridge_sp_named_rosters(DAY,d,slots,{},{},"key",read=lambda *a:{1:{"named":names,"proof":q}})
   self.assertFalse(r);self.assertFalse(st);self.assertFalse(v["verified_races"])
 def test_archive_failure_preserves_daytime_and_no_saturday_extra_read(self):
  from diagnostics.kyoto_weekend_closure_review import bridge_sp_named_rosters
  d,slots,names,p=self.fixture();before=copy.deepcopy(d);calls=[]
  def bad(*a):calls.append(a);raise TimeoutError()
  r,st,v=bridge_sp_named_rosters(DAY,d,slots,{},{},"key",read=bad)
  self.assertFalse(r);self.assertEqual(v["archive_attempts"][0]["error_class"],"TimeoutError");self.assertEqual(d,before)
  bridge_sp_named_rosters("20261128",d,slots,{},{},"key",read=bad)
  self.assertEqual(len(calls),1)

if __name__=="__main__":unittest.main()
