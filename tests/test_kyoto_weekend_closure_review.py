import copy,unittest
from datetime import datetime,timezone
from diagnostics.kyoto_weekend_closure_review import index,slots,coverage_gaps,REPO,PREFIX,FAMILIES,HORSE,TRACK,MARKETS,EXTRA
DAY="20261129";FILE="two-source-production-observer.yml";NOW=datetime(2026,11,29,14,tzinfo=timezone.utc)
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
 def test_duplicate_native_and_index(self):
  rs=[run(),run(2)]
  self.assertEqual(slots(DAY,FILE,index(DAY,FILE,{"total_count":2,"workflow_runs":rs}),NOW)[0]["state"],"NATIVE_SLOT_AMBIGUOUS")
  for bad in ({"total_count":3,"workflow_runs":rs},{"total_count":2,"workflow_runs":[run(),run()]},{"total_count":1,"workflow_runs":[{**run(),"head_branch":"other"}]}):
   with self.assertRaises(ValueError):index(DAY,FILE,bad)
 def test_every_required_family_mutation(self):
  d=data();v=coverage_gaps(DAY,d,[1,2]);self.assertTrue(v["all_reviewed_cells_present"]);self.assertFalse(v["full_acquisition_certified"])
  for f in FAMILIES:
   d=data();r=d["races"]["1"]
   if f=="racecard":r[f]={}
   elif f in HORSE:r["horses"]["1"][f]={}
   elif f in TRACK:r["track"][f]={}
   elif f in MARKETS:r["markets"][f]={}
   elif f in EXTRA:r["supplementary_track_observations"][f]={}
   elif f=="paired_market_same_slot":r["paired_same_slot"]=False
   else:r["postrace"]["result" if f=="official_result" else "payout"]={}
   v=coverage_gaps(DAY,d,[1,2]);self.assertFalse(v["all_reviewed_cells_present"],f);self.assertLess(v["counts"][f]["verified"],v["counts"][f]["expected"],f)
 def test_green_summary_not_accepted_unknown_denominator_and_conflict(self):
  d=data();d["full_data_acquisition_certified"]=True;d["races"]["1"]={"state":"ROSTER_OR_START_CONFLICT"}
  v=coverage_gaps(DAY,d,[1,2]);self.assertEqual(v["counts"]["profile"]["unknown_denominator_races"],1);self.assertFalse(v["all_reviewed_cells_present"])
 def test_wrong_day_and_poststart_source(self):
  for utc in ("2026-11-28T00:00:00Z","2026-11-29T05:00:00Z","2026-11-29T05:01:00Z"):
   d=data();d["races"]["1"]["racecard"]["utc"]=utc
   self.assertFalse(coverage_gaps(DAY,d,[1,2])["all_reviewed_cells_present"])
 def test_pair_different_run(self):
  d=data();d["races"]["1"]["markets"]["quinella"]["run_id"]="2"
  self.assertEqual(coverage_gaps(DAY,d,[1,2])["counts"]["paired_market_same_slot"]["verified"],11)
 def test_missing_origin_and_cancellation_proof(self):
  for bad in ("99",None):
   d=data();d["races"]["1"]["racecard"]["run_id"]=bad
   self.assertEqual(coverage_gaps(DAY,d,[1,2])["counts"]["racecard"]["verified"],11)
  d=data();del d["races"]["1"]["markets"]["quinella"]["cancelled_horses"];del d["races"]["1"]["markets"]["bracket_quinella"]["cancelled_horses"]
  self.assertEqual(coverage_gaps(DAY,d,[1,2])["counts"]["paired_market_same_slot"]["verified"],11)
  d=data();d["postrace_history_index_complete"]=False
  self.assertEqual(coverage_gaps(DAY,d,[1,2])["counts"]["official_payout"]["verified"],0)
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
  with self.assertRaises(ValueError):coverage_gaps(DAY,d,[1,2])
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
if __name__=="__main__":unittest.main()
