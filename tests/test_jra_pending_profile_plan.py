"""Unit tests for a no-network 136-horse acquisition plan."""
import copy,json,unittest
from diagnostics.jra_pending_profile_plan import ROOT,compile_plan,resume_candidates,PlanningError
class PlanTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rows=json.loads((ROOT/"feature_rows_148.json").read_text(encoding="utf8"))
  cls.coverage=json.loads((ROOT/"feature_coverage.json").read_text(encoding="utf8"))
 def test_verified_counts(self):
  result=compile_plan(self.rows,self.coverage)
  self.assertEqual((result["frozen_runners"],result["already_verified"],result["pending_profiles"]),(148,12,136))
  self.assertEqual(result["batch_count"],23)
 def test_no_requery_previously_verified(self):
  plan=compile_plan(self.rows,self.coverage)
  self.assertFalse(any(item["horse_number"]==1 for b in plan["batches"] for item in b["items"]))
 def test_sorted_unique_and_all_races(self):
  p=compile_plan(self.rows,self.coverage)
  ids=[(x["race_number"],x["horse_number"]) for b in p["batches"] for x in b["items"]]
  self.assertEqual(ids,sorted(set(ids)))
  self.assertEqual(set(r for r,n in ids),set(range(1,13)))
 def test_all_batches_at_most_six(self):
  p=compile_plan(self.rows,self.coverage)
  self.assertTrue(all(1<=x["request_count"]<=6 for x in p["batches"]))
 def test_offline_plan_never_authorizes_training_or_fetch(self):
  p=compile_plan(self.rows,self.coverage)
  self.assertFalse(p["extraction_authorized"]);self.assertFalse(p["training_ready"])
  self.assertFalse(p["historical_asof_reconstruction_authorized"])
 def test_reproducible(self):
  self.assertEqual(compile_plan(self.rows,self.coverage),compile_plan(self.rows,self.coverage))
 def test_bad_host_refused(self):
  rows=copy.deepcopy(self.rows);rows[1]["profile_href"]="https://example.com/JRADB/accessU.html?CNAME=fake"
  with self.assertRaises(PlanningError):compile_plan(rows,self.coverage)
 def test_fake_pending_history_refused(self):
  rows=copy.deepcopy(self.rows);rows[1]["performance_features"]={"future_finish":1}
  with self.assertRaises(PlanningError):compile_plan(rows,self.coverage)
 def test_duplicate_refused(self):
  rows=copy.deepcopy(self.rows);rows[1]["horse_number"]=rows[0]["horse_number"]
  with self.assertRaises(PlanningError):compile_plan(rows,self.coverage)
 def test_resume_missing_are_outstanding(self):
  p=compile_plan(self.rows,self.coverage)
  r=resume_candidates(p,{})
  self.assertEqual(len(r["outstanding"]),23)
 def test_mismatched_receipt_is_rejected(self):
  p=compile_plan(self.rows,self.coverage)
  with self.assertRaises(PlanningError):
   resume_candidates(p,{"batch_01":{"batch_content_sha256":"bad","state":"COMPLETED_WITH_SOURCE_EVIDENCE","verified_count":6,"sources_retained":True}})
 def test_completed_receipt_requires_provenance(self):
  p=compile_plan(self.rows,self.coverage)
  key=p["batches"][0]
  with self.assertRaises(PlanningError):
   resume_candidates(p,{key["batch_id"]:{"batch_content_sha256":key["batch_content_sha256"],"state":"COMPLETED_WITH_SOURCE_EVIDENCE","verified_count":6,"sources_retained":False}})
if __name__=="__main__":unittest.main()
