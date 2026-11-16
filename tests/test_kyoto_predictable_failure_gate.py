"""Adversarial tests prove omitted predictable risks and tests cannot earn PASS."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_predictable_failure_gate import MATRIX, MatrixRejected, verify_matrix

ROOT=Path(__file__).resolve().parents[1]

class PredictableFailureGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload=json.loads((ROOT/MATRIX).read_text(encoding="utf8"))

    def test_thirty_predeclared_cases_have_source_and_unittest_bindings(self):
        checks=verify_matrix(ROOT,self.payload)
        self.assertEqual(len(checks),30)
        self.assertEqual(len({c["id"] for c in checks}),30)

    def test_removed_case_does_not_pass_coverage(self):
        other=copy.deepcopy(self.payload)
        other["entries"].pop()
        with self.assertRaisesRegex(MatrixRejected,"insufficient_risk_coverage"):
            verify_matrix(ROOT,other)

    def test_duplicate_case_does_not_inflate_coverage(self):
        other=copy.deepcopy(self.payload)
        other["entries"][1]["id"]=other["entries"][0]["id"]
        with self.assertRaisesRegex(MatrixRejected,"duplicate_id"):
            verify_matrix(ROOT,other)

    def test_deleted_test_name_does_not_pass(self):
        other=copy.deepcopy(self.payload)
        other["entries"][7]["test"]="test_nonexistent_fake_success"
        with self.assertRaisesRegex(MatrixRejected,"test_method_missing_or_ambiguous"):
            verify_matrix(ROOT,other)

    def test_unimplemented_source_condition_does_not_pass(self):
        other=copy.deepcopy(self.payload)
        other["entries"][0]["source_token"]="UNREALISTIC_SOURCE_TOKEN_NOT_PRESENT"
        with self.assertRaisesRegex(MatrixRejected,"source_invariant_absent"):
            verify_matrix(ROOT,other)

    def test_cannot_remove_phase_or_test_mode(self):
        other=copy.deepcopy(self.payload)
        other["required_phases"].remove("storage")
        with self.assertRaisesRegex(MatrixRejected,"required_phases_missing"):
            verify_matrix(ROOT,other)
        other=copy.deepcopy(self.payload)
        other["required_kinds"].remove("destructive")
        with self.assertRaisesRegex(MatrixRejected,"required_kinds_missing"):
            verify_matrix(ROOT,other)

    def test_live_unverified_cannot_be_mislabelled_prediction_ready(self):
        other=copy.deepcopy(self.payload)
        other["explicit_deferred_gates"][0]["may_use_for_prediction"]=True
        with self.assertRaisesRegex(MatrixRejected,"live_deferred_gates_missing_or_weakened"):
            verify_matrix(ROOT,other)

    def test_weakening_policy_is_blocked(self):
        other=copy.deepcopy(self.payload)
        other["policy"]["runner_requires_execution_receipts"]=False
        with self.assertRaisesRegex(MatrixRejected,"policy_weakened"):
            verify_matrix(ROOT,other)

if __name__=="__main__":
    unittest.main()
