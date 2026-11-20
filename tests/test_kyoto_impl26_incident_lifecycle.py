import unittest
from diagnostics.kyoto_impl26_incident_lifecycle import advance,same_cause_candidates,STAGES
A="a"*40
B="b"*40
class IncidentLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.initial={"incident_id":"INC-20261121-123-abc","status":"DETECTED","risk_ids":["R05"],
                      "failure_stage":"PRE_HTTP_STOP","error_class":"AssertionError"}
    def test_evidence_required_and_no_stage_jump(self):
        with self.assertRaisesRegex(ValueError,"state_jump_forbidden"):
            advance(self.initial,"CANDIDATE_PATCH",{"commit_sha":A})
        with self.assertRaisesRegex(ValueError,"transition_evidence_required"):
            advance(self.initial,"EVIDENCE_LOCKED",{})
        with self.assertRaisesRegex(ValueError,"source_hash"):
            advance(self.initial,"EVIDENCE_LOCKED",{"run_id":"1"})
    def test_idempotence_and_conflicting_duplicate_rejected(self):
        evidence={"source_hash":"abc","run_id":"123"}
        next_=advance(self.initial,"EVIDENCE_LOCKED",evidence)
        self.assertEqual(next_,advance(next_,"EVIDENCE_LOCKED",evidence))
        with self.assertRaisesRegex(ValueError,"non_idempotent"):
            advance(next_,"EVIDENCE_LOCKED",{"source_hash":"def","run_id":"123"})
    def test_root_cause_requires_repro_and_counterexample(self):
        x=advance(self.initial,"EVIDENCE_LOCKED",{"source_hash":"a","run_id":"123"})
        x=advance(x,"ROOT_CAUSE_CANDIDATE",{"hypothesis":"h","same_cause_search":"none"})
        with self.assertRaisesRegex(ValueError,"counterexample"):
            advance(x,"ROOT_CAUSE_PROVED",{"reproducer":"test","root_cause":"cause"})
    def test_promote_different_sha_is_blocked(self):
        x=self.initial
        data=[
            ("EVIDENCE_LOCKED",{"source_hash":"abc","run_id":"123"}),
            ("ROOT_CAUSE_CANDIDATE",{"hypothesis":"h","same_cause_search":"none found"}),
            ("ROOT_CAUSE_PROVED",{"reproducer":"t","counterexample":"n","root_cause":"c"}),
            ("CANDIDATE_PATCH",{"branch":"fix/b","commit_sha":A,"protected_diff":"zero"}),
            ("OFFLINE_REGRESSION_PASSED",{"ci_run_id":"99","reproducer_pass":True,"negative_test_pass":True}),
        ]
        for stage,proof in data:
            x=advance(x,stage,proof)
        with self.assertRaisesRegex(ValueError,"approved_sha_mismatch"):
            advance(x,"APPROVED_FOR_PRODUCTION",{"approved_commit_sha":B,
                "approver_evidence":"review","rollback_sha":A})
        y=advance(x,"APPROVED_FOR_PRODUCTION",{"approved_commit_sha":A,
            "approver_evidence":"review","rollback_sha":B})
        self.assertEqual(y["status"],"APPROVED_FOR_PRODUCTION")
        with self.assertRaisesRegex(ValueError,"state_jump_forbidden"):
            advance(y,"CLOSED",{"closure_evidence":"proof","regression_added":True})
    def test_same_cause_search_is_candidate_only(self):
        prior={"incident_id":"INC-prior","risk_ids":["R05"],
               "failure_stage":"PRE_HTTP_STOP","error_class":"AssertionError"}
        result=same_cause_candidates(self.initial,[prior,self.initial])
        self.assertEqual(result,[{"incident_id":"INC-prior","confidence":"CANDIDATE_NOT_PROVED"}])
        self.assertEqual(same_cause_candidates(self.initial,[]),[])
if __name__=="__main__":
    unittest.main()
