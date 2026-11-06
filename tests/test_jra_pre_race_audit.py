import unittest,copy
from diagnostics.jra_pre_race_audit import AuditError,validate_snapshot,reconcile
PRE={"source_type":"PRE_RACE_RACECARD","source_url":"https://www.jra.go.jp/JRADB/accessD.html",
 "source_sha256":"a"*64,"raw_sha256_verified":True,"racecard_structure_verified":True,
 "fetched_at_utc":"2026-10-31T02:30:00Z","race_id":"synthetic-race","race_number":1,
 "scratch_evidence_verified":True,"runners":[
 {"horse_number":5,"frame_number":3,"horse_name":"試験馬","status":"STARTER",
  "permanent_jra_horse_id":"1234567890","permanent_id_source_verified":True},
 {"horse_number":8,"frame_number":4,"horse_name":"取消馬","status":"SCRATCHED"}]}
RESULT={"source_type":"POST_RACE_RESULT","source_sha256":"b"*64,"raw_sha256_verified":True,
 "race_id":"synthetic-race","race_number":1,
 "runners":[{"horse_number":5,"frame_number":3,"horse_name":"試験馬"}]}
CUTOFF="2026-10-31T05:30:00Z"
def go(p=None,r=None):return reconcile(p or PRE,r or RESULT,cutoff_utc=CUTOFF)
class TestGate(unittest.TestCase):
 def test_synthetic_pass(self):self.assertEqual(go()["status"],"PASS")
 def test_never_predict_from_result(self):self.assertFalse(go()["ready_for_prediction"])
 def test_future(self):
  p=copy.deepcopy(PRE);p["fetched_at_utc"]="2026-10-31T06:00:00Z"
  with self.assertRaises(AuditError):go(p)
 def test_index_not_racecard(self):
  p=copy.deepcopy(PRE);p["racecard_structure_verified"]=False
  with self.assertRaises(AuditError):go(p)
 def test_unverified_bytes(self):
  p=copy.deepcopy(PRE);p["raw_sha256_verified"]=False
  with self.assertRaises(AuditError):go(p)
 def test_duplicate(self):
  p=copy.deepcopy(PRE);p["runners"].append(dict(p["runners"][0]))
  with self.assertRaises(AuditError):go(p)
 def test_wrong_horse(self):
  r=copy.deepcopy(RESULT);r["runners"][0]["horse_name"]="別の馬"
  self.assertEqual(go(r=r)["status"],"BLOCKED")
 def test_missing_scratch_proof(self):
  p=copy.deepcopy(PRE);p["scratch_evidence_verified"]=False
  self.assertEqual(go(p)["status"],"BLOCKED")
 def test_unverified_id(self):
  p=copy.deepcopy(PRE);p["runners"][0]["permanent_id_source_verified"]=False
  with self.assertRaises(AuditError):go(p)
 def test_missing_id(self):
  p=copy.deepcopy(PRE);p["runners"][0]["permanent_jra_horse_id"]=None
  self.assertEqual(go(p)["status"],"BLOCKED")
 def test_unconfirmed(self):
  p=copy.deepcopy(PRE);p["runners"][1]["status"]="UNCONFIRMED"
  self.assertEqual(go(p)["status"],"BLOCKED")
 def test_missing_result(self):
  r=copy.deepcopy(RESULT);r["runners"]=[]
  self.assertEqual(go(r=r)["status"],"BLOCKED")
 def test_repeat(self):self.assertEqual(go(),go())
 def test_untrusted_domain(self):
  p=copy.deepcopy(PRE);p["source_url"]="https://example.org/"
  with self.assertRaises(AuditError):go(p)
if __name__=="__main__":unittest.main()
