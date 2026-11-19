import unittest
from diagnostics.kyoto_impl22_readiness_gate import assess_step7,REQUIRED
class ReadinessGateTests(unittest.TestCase):
    def test_missing_evidence_cannot_be_upgraded(self):
        r=assess_step7({})
        self.assertEqual(r["weekend_pre_event_numerator"],9)
        self.assertFalse(r["complete"])
        self.assertEqual(len(r["missing"]),4)
    def test_success_workflow_without_real_connection_is_not_proof(self):
        self.assertFalse(assess_step7({"workflow_conclusion":"success","remote_readonly_status":"SKIPPED_TEST_DB_SECRETS_NOT_CONFIGURED"})["complete"])
    def test_one_unverified_environment_blocks_full_completion(self):
        evidence=dict.fromkeys(REQUIRED,True)
        evidence["github_streamlit_cross_environment_verified"]=False
        self.assertEqual(assess_step7(evidence)["missing"],["github_streamlit_cross_environment_verified"])
    def test_all_proof_categories_required(self):
        self.assertTrue(assess_step7(dict.fromkeys(REQUIRED,True))["complete"])
    def test_nonobject_rejected(self):
        with self.assertRaises(ValueError):assess_step7(None)
if __name__=="__main__":unittest.main()
