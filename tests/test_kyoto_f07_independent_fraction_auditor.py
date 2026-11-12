"""Independent auditor's negative witnesses without any JRA network."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from diagnostics.kyoto_f07_independent_fraction_auditor import audit,AuditRejected,canonical,digest
from diagnostics.kyoto_f07_offline_pair_acceptance import calculate_f07

def fixture():
    runners=[dict(number=i,frame=(i+1)//2,status="ACTIVE",strength=float(i)) for i in range(1,17)]
    q=[[i,j] for i in range(1,17) for j in range(i+1,17)]
    b=[[i,j] for i in range(1,9) for j in range(i,9)]
    r=calculate_f07(runners=runners,market_status={"QUINELLA":"OPEN","BRACKET":"OPEN"},quoted_pairs={"QUINELLA":q,"BRACKET":b})
    r.update(ci_run_id="43132839820",
        ci_head_sha="1f002d8572a16aa60f269f8f8bad3859165582e7",
        f07_fixed_acceptance_verified_by="independent_github_actions_unit_and_exception_tests",
        live_market_source_accepted=False,production_deployment_authorized=False)
    return r

class IndependentFractionAuditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rubric=Path("docs/diagnostics/kyoto_final_completion_criteria_v1.json").read_bytes()
    def test_complete_rational_independent_validation(self):
        r=audit(fixture(),self.rubric)
        self.assertEqual(r["accepted_points"],5)
        self.assertEqual(r["gate"],"F07")
        self.assertFalse(r["final_completion_certified"])
    def test_tampered_witness_content_is_refused(self):
        w=fixture();w["quinella"][0]["probability"]+=0.01
        with self.assertRaises(AuditRejected):audit(w,self.rubric)
    def test_even_rehashed_wrong_probability_is_refused(self):
        w=fixture();w["quinella"][0]["probability"]+=0.01
        copy_w={k:v for k,v in w.items() if k not in (
         "ci_run_id","ci_head_sha","f07_fixed_acceptance_verified_by","live_market_source_accepted","production_deployment_authorized","sha256")}
        w["sha256"]=digest(copy_w)
        with self.assertRaisesRegex(AuditRejected,"independent_fraction_probability_mismatch"):
            audit(w,self.rubric)
    def test_wrong_run_rejected(self):
        w=fixture();w["ci_run_id"]="wrong"
        with self.assertRaises(AuditRejected):audit(w,self.rubric)
    def test_wrong_rubric_rejected(self):
        with self.assertRaises(AuditRejected):audit(fixture(),self.rubric+b" ")
    def test_live_claim_rejected(self):
        w=fixture();w["live_source_authenticated"]=True
        with self.assertRaises(AuditRejected):audit(w,self.rubric)

if __name__=="__main__":unittest.main()
