"""Destructive audit of immutable 16-gate readiness scoring and evidence."""
import copy
import json
import tempfile
from pathlib import Path
import unittest
from diagnostics.kyoto_predata_readiness import (
    CHECKS,IDS,ReadinessRejected,evaluate,verify_rubric,RUBRIC)
ROOT=Path(__file__).resolve().parents[1]
class ReadinessTests(unittest.TestCase):
 def setUp(self):
    self.rubric=json.loads((ROOT/RUBRIC).read_text(encoding="utf-8"))
    self.receipts={name:True for name in CHECKS}
 def test_frozen_sixteen_denominator(self):
    self.assertEqual(len(IDS),16)
    self.assertTrue(verify_rubric(self.rubric))
 def test_all_eight_evidenced_suites_score_exactly_50(self):
    r=evaluate(ROOT,results=self.receipts)
    self.assertEqual(r["total_gates"],16)
    self.assertEqual(r["passed_gates"],8)
    self.assertEqual(r["remaining_gates"],8)
    self.assertEqual(r["completion_percent"],50.0)
    self.assertEqual(r["accepted_gate_ids"],["R01","R03","R05","R06","R09","R11","R12","R13"])
    self.assertFalse(r["revert_to_original_scoring_now"])
    self.assertFalse(r["live_paper_trading_authorized"])
 def test_failing_suite_cannot_get_credit(self):
    self.receipts["R12"]=False
    r=evaluate(ROOT,results=self.receipts)
    self.assertEqual(r["passed_gates"],7)
    self.assertEqual(r["completion_percent"],43.75)
 def test_no_suite_results_means_no_credit(self):
    self.assertEqual(evaluate(ROOT,run_tests=False)["passed_gates"],0)
 def test_fake_added_gate_refused(self):
    self.rubric["gates"].append(copy.deepcopy(self.rubric["gates"][-1]))
    with self.assertRaisesRegex(ReadinessRejected,"fixed_rubric_identity"):
        verify_rubric(self.rubric)
 def test_reordered_gate_refused(self):
    self.rubric["gates"][0],self.rubric["gates"][1]=self.rubric["gates"][1],self.rubric["gates"][0]
    with self.assertRaises(ReadinessRejected):verify_rubric(self.rubric)
 def test_changed_denominator_refused(self):
    self.rubric["denominator"]=15
    with self.assertRaises(ReadinessRejected):verify_rubric(self.rubric)
 def test_receipt_must_be_exactly_boolean(self):
    self.receipts["R03"]=1
    with self.assertRaisesRegex(ReadinessRejected,"test_attestation_schema"):
        evaluate(ROOT,results=self.receipts)
 def test_missing_receipt_refused(self):
    del self.receipts["R09"]
    with self.assertRaises(ReadinessRejected):evaluate(ROOT,results=self.receipts)
 def test_unverified_gates_stay_zero(self):
    r=evaluate(ROOT,results=self.receipts)
    for row in r["gates"]:
        if row["id"] not in CHECKS:self.assertEqual(row["state"],"UNVERIFIED")
 def test_report_is_deterministic(self):
    self.assertEqual(evaluate(ROOT,results=self.receipts),
                     evaluate(ROOT,results=self.receipts))
if __name__=="__main__":unittest.main()
