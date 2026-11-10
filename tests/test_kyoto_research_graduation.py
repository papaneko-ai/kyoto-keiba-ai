import copy
import json
import unittest
from pathlib import Path
from diagnostics.kyoto_research_graduation import evaluate, GraduationRejected

ROOT=Path(__file__).resolve().parents[1]
RUBRIC=json.loads((ROOT/"docs/diagnostics/kyoto_research_graduation_rubric_v1.json").read_text(encoding="utf-8"))
EVIDENCE=json.loads((ROOT/"docs/diagnostics/kyoto_progress_evidence_v1.json").read_text(encoding="utf-8"))
CLAIMS={"schema":"kyoto_research_graduation_integration_claims.v1","claims":[]}
def verified():
    return {"schema":"kyoto_progress_result.v1",
            "scope_id":"KYOTO_P1_P8_FIXED_20261110",
            "passed_ids":[x["id"] for x in EVIDENCE["claims"]],
            "score_percent":64,"source_commit":"TEST_SHA"}

class ResearchGraduationTests(unittest.TestCase):
    def test_all_six_existing_individual_prerequisites_counted(self):
        result=evaluate(RUBRIC,verified(),CLAIMS)
        self.assertEqual(result["graduation_passed_conditions"],6)
        self.assertEqual(result["graduation_percent"],50.0)
        self.assertEqual(result["integration_passed"],0)
        self.assertFalse(result["graduation_eligible"])
        self.assertEqual(result,evaluate(RUBRIC,verified(),CLAIMS))
    def test_not_p1_p8_score(self):
        r=evaluate(RUBRIC,verified(),CLAIMS)
        self.assertEqual(r["progress_score_percent"],64)
        self.assertEqual(r["graduation_percent"],50.0)
        self.assertNotIn("operational_readiness",r)
    def test_removed_progress_evidence_reduces_credit(self):
        p=verified();p["passed_ids"].remove("P7-02")
        r=evaluate(RUBRIC,p,CLAIMS)
        self.assertEqual(r["graduation_passed_conditions"],5)
        self.assertEqual(r["graduation_percent"],41.7)
    def test_duplicate_integration_claims_fail(self):
        c={"id":"RG-01B","proof_run_id":1,"proof_job_id":1,
           "proof_head_sha":"0"*40,"source_paths":[],"acceptance_test":"x"}
        with self.assertRaises(GraduationRejected):
            evaluate(RUBRIC,verified(),{**CLAIMS,"claims":[c,c]})
    def test_unverified_integration_must_fail(self):
        c={"id":"RG-01B","proof_run_id":1,"proof_job_id":1,
           "proof_head_sha":"0"*40,"source_paths":[],"acceptance_test":"x"}
        with self.assertRaisesRegex(GraduationRejected,"unverified_integration"):
            evaluate(RUBRIC,verified(),{**CLAIMS,"claims":[c]})
    def test_modified_prerequisites_rejected(self):
        r=copy.deepcopy(RUBRIC)
        r["areas"][0]["component"]["requires_progress_ids"]=["P1-01","P1-02"]
        with self.assertRaisesRegex(GraduationRejected,"criterion_mutation"):
            evaluate(r,verified(),CLAIMS)
    def test_no_unverified_synthetic_pass(self):
        p=verified();p["passed_ids"]=[]
        x=evaluate(RUBRIC,p,CLAIMS)
        self.assertEqual(x["graduation_percent"],0.0)
        self.assertEqual(x["integration_passed"],0)
    def test_wrong_progress_report_rejected(self):
        p=verified();p["scope_id"]="WRONG"
        with self.assertRaisesRegex(GraduationRejected,"validated_P1_P8"):
            evaluate(RUBRIC,p,CLAIMS)
    def test_schema_change_rejected(self):
        r=copy.deepcopy(RUBRIC);r["criterion_count"]=10
        with self.assertRaisesRegex(GraduationRejected,"fixed_graduation"):
            evaluate(r,verified(),CLAIMS)
    def test_all_components_not_graduated(self):
        p=verified()
        for a in RUBRIC["areas"]:
            for k in a["component"]["requires_progress_ids"]:
                if k not in p["passed_ids"]:p["passed_ids"].append(k)
        x=evaluate(RUBRIC,p,CLAIMS)
        self.assertFalse(x["graduation_eligible"])
        self.assertEqual(x["integration_passed"],0)

if __name__=="__main__": unittest.main()
