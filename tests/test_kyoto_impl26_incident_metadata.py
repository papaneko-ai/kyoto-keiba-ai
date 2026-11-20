import json
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_impl26_incident_metadata import classify, stable_id, ORDER
DAY="20261121"
NAME="Kyoto Nov21-22 independent encrypted original collection"
class IncidentMetadataTests(unittest.TestCase):
    def run_obj(self):
        return {"id":123,"name":NAME,"created_at":"2026-11-21T00:15:00Z",
                "run_started_at":"2026-11-21T00:17:00Z"}
    def jobs(self):
        return {"jobs":[
            {"id":1,"name":"pc-originals-independent","conclusion":"success","steps":[]},
            {"id":2,"name":"sp-originals-independent","conclusion":"success","steps":[]}]}
    def artifacts(self):
        return {"artifacts":[
            {"name":f"kyoto-pc-123-{DAY}","expired":False},
            {"name":f"kyoto-sp-123-{DAY}","expired":False}]}
    def test_complete_metadata_does_not_claim_verified_source(self):
        self.assertEqual(list(classify(self.run_obj(),self.jobs(),self.artifacts(),day=DAY)),[])
    def test_missing_run_stable_id_and_risk(self):
        a=list(classify(None,{"jobs":[]},{"artifacts":[]},day=DAY))
        b=list(classify(None,{"jobs":[]},{"artifacts":[]},day=DAY))
        self.assertEqual(len(a),1)
        self.assertEqual(a[0]["incident_id"],b[0]["incident_id"])
        self.assertEqual(a[0]["risk_ids"],["R01"])
        self.assertEqual(a[0]["failure_stage"],"NOT_TRIGGERED")
        self.assertEqual(a[0]["root_cause_status"],"UNKNOWN")
    def test_missing_artifact_is_separate_incident(self):
        artifacts=self.artifacts()
        artifacts["artifacts"]=artifacts["artifacts"][:1]
        a=list(classify(self.run_obj(),self.jobs(),artifacts,day=DAY))
        self.assertEqual(len(a),1)
        self.assertEqual(a[0]["channel"],"SP")
        self.assertEqual(a[0]["risk_ids"],["R31"])
    def test_failed_step_and_missing_artifact_both_preserved(self):
        jobs=self.jobs()
        jobs["jobs"][0]["conclusion"]="failure"
        jobs["jobs"][0]["steps"]=[{"name":"Always encrypt SP originals","conclusion":"failure"}]
        a=list(classify(self.run_obj(),jobs,{"artifacts":[]},day=DAY))
        self.assertEqual(len(a),3)
        self.assertTrue(any(x["failure_stage"]=="SEALING_FAILED" for x in a))
        self.assertTrue(all(x["status"]=="DETECTED" for x in a))
    def test_wrong_workflow_never_adopted(self):
        run=self.run_obj()
        run["name"]="lookalike"
        with self.assertRaises(ValueError):
            list(classify(run,self.jobs(),self.artifacts(),day=DAY))
    def test_date_mismatch_never_adopted(self):
        with self.assertRaises(ValueError):
            list(classify(self.run_obj(),self.jobs(),self.artifacts(),day="20261122"))
    def test_incident_id_safe_and_lifecycle_fixed(self):
        self.assertEqual(len(ORDER),9)
        self.assertEqual(stable_id(DAY,123,"PC","UNKNOWN"),
                         stable_id(DAY,123,"PC","UNKNOWN"))
        self.assertNotEqual(stable_id(DAY,123,"PC","UNKNOWN"),
                            stable_id(DAY,123,"SP","UNKNOWN"))
if __name__=="__main__":
    unittest.main()
