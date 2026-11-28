import copy,unittest
from datetime import datetime,timezone
from diagnostics.kyoto_weekend_closure_review import index,slots,coverage_gaps,REPO,PREFIX,FAMILIES,HORSE,TRACK,MARKETS
DAY="20261129";FILE="two-source-production-observer.yml";NOW=datetime(2026,11,29,14,tzinfo=timezone.utc)
def run(rid=1,event="schedule",title="kyoto-native:15 0 29 11 *"):
 return {"id":rid,"event":event,"name":title,"head_repository":{"full_name":REPO},"head_branch":"main","path":PREFIX+FILE,"head_sha":"a"*40,"created_at":"2026-11-29T00:17:00Z","status":"completed","conclusion":"success"}
def data():
 def proof(after=False):
  return {"state":"SOURCE_VERIFIED","run_id":"1","utc":"2026-11-29T10:00:00Z" if after else "2026-11-29T00:00:00Z","sha256":"a"*64,"value_digest":"b"*64}
 r={"state":"ROSTER_VERIFIED","roster_digest":"a"*64,"named_roster_digest":"b"*64,"start_utc":"2026-11-29T05:00:00Z","racecard":proof(),"horses":{str(n):{f:proof() for f in HORSE} for n in (1,2)},"track":{f:proof() for f in TRACK},"markets":{f:{**proof(),"cancelled_horses":[]} for f in MARKETS},"paired_same_slot":True,"postrace":{"state":"DUAL_PAGE_FINAL_SOURCE_RECONCILED","result":proof(True),"payout":proof(True)}}
 return {"schema":"kyoto_impl30_day_source_coverage.v1","day":DAY,"races":{str(n):copy.deepcopy(r) for n in range(1,13)}}
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
  d=data();v=coverage_gaps(DAY,d);self.assertTrue(v["all_reviewed_cells_present"]);self.assertFalse(v["full_acquisition_certified"])
  for f in FAMILIES:
   d=data();r=d["races"]["1"]
   if f=="racecard":r[f]={}
   elif f in HORSE:r["horses"]["1"][f]={}
   elif f in TRACK:r["track"][f]={}
   elif f in MARKETS:r["markets"][f]={}
   elif f=="paired_market_same_slot":r["paired_same_slot"]=False
   else:r["postrace"]["result" if f=="official_result" else "payout"]={}
   v=coverage_gaps(DAY,d);self.assertFalse(v["all_reviewed_cells_present"],f);self.assertLess(v["counts"][f]["verified"],v["counts"][f]["expected"],f)
 def test_green_summary_not_accepted_unknown_denominator_and_conflict(self):
  d=data();d["full_data_acquisition_certified"]=True;d["races"]["1"]={"state":"ROSTER_OR_START_CONFLICT"}
  v=coverage_gaps(DAY,d);self.assertEqual(v["counts"]["profile"]["unknown_denominator_races"],1);self.assertFalse(v["all_reviewed_cells_present"])
 def test_wrong_day_and_poststart_source(self):
  for utc in ("2026-11-28T00:00:00Z","2026-11-29T05:00:00Z","2026-11-29T05:01:00Z"):
   d=data();d["races"]["1"]["racecard"]["utc"]=utc
   self.assertFalse(coverage_gaps(DAY,d)["all_reviewed_cells_present"])
 def test_pair_different_run(self):
  d=data();d["races"]["1"]["markets"]["quinella"]["run_id"]="2"
  self.assertEqual(coverage_gaps(DAY,d)["counts"]["paired_market_same_slot"]["verified"],11)
 def test_incomplete_race_inventory(self):
  d=data();del d["races"]["12"]
  with self.assertRaises(ValueError):coverage_gaps(DAY,d)
if __name__=="__main__":unittest.main()
