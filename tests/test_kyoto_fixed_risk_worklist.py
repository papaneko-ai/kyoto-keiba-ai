import hashlib,json,unittest,os,tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone
from diagnostics.kyoto_fixed_risk_worklist import worklist,IDS,continuity_worklist,REGISTER_BLOB
class FixedRiskTests(unittest.TestCase):
 def fixture(self):
  risks=[{"id":r,"severity":"BLOCKER" if i<13 else "OPEN","affected_surfaces":[],"required_evidence":"independent proof"} for i,r in enumerate(IDS)]
  raw=json.dumps({"risks":risks}).encode()
  return raw,hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
 def test_all_fixed_risks_with_distinct_obligations(self):
  raw,h=self.fixture()
  w=worklist({"workflows":{"two-source-production-observer.yml":{"index_complete":True,"runs":[{"id":1,"artifacts":{"pc":{"ids":[7]}}}]}},"coverage":{"all_reviewed_cells_present":True}},raw,h)
  self.assertEqual([r["id"] for r in w["rows"]],list(IDS))
  self.assertEqual(w["independently_closed"],0)
  self.assertEqual(len({r["specific_proof"] for r in w["rows"]}),25)
  self.assertEqual(w["rows"][0]["evidence"][0]["artifact_ids"],[7])
  self.assertTrue(all(not r["closed"] for r in w["rows"]))
 def test_register_mutation_rejected(self):
  raw,h=self.fixture()
  with self.assertRaises(ValueError):worklist({"workflows":{}},raw+b" ",h)
 def test_actual_pinned_register(self):
  path=os.environ.get("KYOTO_TEST_FIXED_RISK_REGISTER")
  if not path:self.skipTest("actual pinned register is provided by release CI")
  raw=Path(path).read_bytes()
  w=worklist({"workflows":{}},raw)
  self.assertEqual(w["register_blob"],REGISTER_BLOB)
  self.assertEqual((w["total"],w["blockers"],w["independently_closed"]),(25,13,0))
  self.assertEqual(tuple(x["id"] for x in w["rows"]),IDS)
 def test_dispatch_and_runner_evidence_not_closed(self):
  w={"postrace-evidence.yml":{"index_complete":True,"external_dispatch_slots":[
      {"state":"DISPATCH_NOT_OBSERVED","due_utc":"2026-11-28T13:02:00+00:00","run_ids":[]},
      {"state":"NOT_DUE","due_utc":"2026-11-29T13:02:00+00:00","run_ids":[]},
      {"state":"DISPATCH_COMPLETED","due_utc":"2026-11-28T10:02:00+00:00","run_ids":[3]}],
      "native_slots":[{"state":"NATIVE_SLOT_NOT_OBSERVED"}],
      "runs":[{"id":3,"head_sha":"a"*40,"artifacts":{"postrace":{"state":"MISSING_AFTER_JOB_UNSUCCESSFUL","ids":[],"job_id":5}}}]},
      "cushion-source.yml":{"index_complete":True,"runs":[{"id":4,"artifacts":{"cushion":{"state":"JOB_SKIPPED_NO_ARTIFACT","ids":[],"job_id":6}}}]}}
  a=continuity_worklist("20261128",w)
  self.assertEqual(a,continuity_worklist("20261128",w))
  self.assertEqual({r["observed_code"] for r in a["rows"]},{"DISPATCH_NOT_OBSERVED","MISSING_AFTER_JOB_UNSUCCESSFUL","JOB_SKIPPED_NO_ARTIFACT"})
  self.assertTrue(all(not r["root_cause_proved"] and not r["source_success_certified"] for r in a["rows"]))
  self.assertEqual(a["independently_closed"],0)
  self.assertEqual(next(r for r in a["rows"] if r["run_id"]==3)["job_id"],5)
 def test_index_failure_does_not_assert_absence_and_checkpoint_is_bound(self):
  from diagnostics.kyoto_weekend_closure_review import collect_metadata,write_checkpoint,load_checkpoint
  day="20261128";now=datetime(2026,11,28,13,30,tzinfo=timezone.utc)
  with patch("diagnostics.kyoto_weekend_closure_review.gh",side_effect=TimeoutError):
   metadata,errors=collect_metadata(day,now)
  self.assertTrue(errors)
  rows=continuity_worklist(day,metadata)["rows"]
  self.assertTrue(any(x["observed_code"]=="DISPATCH_INDEX_UNAVAILABLE" for x in rows))
  self.assertFalse(any(x["observed_code"]=="DISPATCH_NOT_OBSERVED" for x in rows))
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{"GITHUB_RUN_ID":"123"}):
   with patch("diagnostics.kyoto_weekend_closure_review.collect_metadata",return_value=(metadata,errors)):
    d=write_checkpoint(day,now,tmp)
   self.assertEqual(load_checkpoint(day,tmp),d)
   with self.assertRaises(ValueError):load_checkpoint("20261129",tmp)
   with patch.dict(os.environ,{"GITHUB_RUN_ID":"124"}):
    with self.assertRaises(ValueError):load_checkpoint(day,tmp)
   p=Path(tmp)/"continuity_worklist.json";p.write_bytes(p.read_bytes()+b" ")
   with self.assertRaises(ValueError):load_checkpoint(day,tmp)
if __name__=="__main__":unittest.main()
