"""Independent adversarial probes of source-first foreseeable-risk enumeration."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_reverse_fmea_gate import LEDGER,inspect,AuditCoverageRejected

ROOT=Path(__file__).resolve().parents[1]
class SourceFirstCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads((ROOT/LEDGER).read_text(encoding="utf8"))
    def test_twenty_reachable_modules_seventy_six_functions_not_declared_complete(self):
        r=inspect(ROOT,self.doc)
        self.assertEqual(r["critical_modules"],26)
        self.assertEqual(r["top_level_functions_discovered"],92)
        self.assertEqual(r["top_level_functions_unregistered"],0)
        self.assertEqual(r["top_level_functions_not_yet_independently_reviewed"],63)
        self.assertGreater(r["class_methods_discovered_but_not_yet_independently_reviewed"],0)
        self.assertEqual(r["additional_predictable_failure_families"],23)
        self.assertGreater(r["high_severity_unresolved"],0)
        self.assertIs(r["completeness_demonstrated"],False)
    def test_transitive_source_dependencies_are_enumerated_and_registered(self):
        from diagnostics.kyoto_reverse_fmea_gate import reachable_local_modules
        seed={item["source"] for item in self.doc["surfaces"]}
        seen=reachable_local_modules(ROOT,seed)
        self.assertEqual(seen,seed)
        result=inspect(ROOT,self.doc)
        self.assertEqual(result["additional_reachable_modules_not_yet_reviewed"],0)
        self.assertEqual(result["top_level_functions_not_yet_independently_reviewed"],63)
        self.assertIs(result["completeness_demonstrated"],False)

    def test_function_omission_rejected(self):
        d=copy.deepcopy(self.doc)
        d["surfaces"].pop()
        with self.assertRaisesRegex(AuditCoverageRejected,"source_module_inventory_incomplete"):
            inspect(ROOT,d,verify_git=False)
    def test_fake_function_rejected(self):
        d=copy.deepcopy(self.doc)
        d["surfaces"][0]["function"]="not_existing_method"
        with self.assertRaisesRegex(AuditCoverageRejected,"unreviewed_or_stale_functions"):
            inspect(ROOT,d,verify_git=False)
    def test_issue_deletion_rejected(self):
        d=copy.deepcopy(self.doc)
        d["risks"].pop()
        with self.assertRaisesRegex(AuditCoverageRejected,"known_predictable_risk_missing"):
            inspect(ROOT,d,verify_git=False)
    def test_risk_claimed_fixed_without_evidence_rejected(self):
        d=copy.deepcopy(self.doc)
        d["risks"][0]["remediated"]=True
        with self.assertRaisesRegex(AuditCoverageRejected,"silently_marked_fixed"):
            inspect(ROOT,d,verify_git=False)
    def test_risk_references_nonexistent_function_rejected(self):
        d=copy.deepcopy(self.doc)
        d["risks"][0]["affected_surfaces"][1]="kyoto_weekend_capture.py:missing_fn"
        with self.assertRaisesRegex(AuditCoverageRejected,"risk_references_nonexistent"):
            inspect(ROOT,d,verify_git=False)
    def test_source_bytes_modified_without_new_fmea_rejected(self):
        import subprocess
        from unittest.mock import patch
        with patch("diagnostics.kyoto_reverse_fmea_gate.subprocess.check_output",
                   return_value=b"unauthorized altered historical byte stream"):
            with self.assertRaisesRegex(AuditCoverageRejected,"source_changed_requires_new_fmea"):
                inspect(ROOT,self.doc,verify_git=True)
    def test_source_first_fmea_never_promotes_unverified_live_market(self):
        self.assertEqual(self.doc["adjudication"]["result"],"STRUCTURALLY_ENUMERATED_BUT_FMEA_REVIEW_INCOMPLETE")
        self.assertFalse(self.doc["adjudication"]["live_data_authoritative"])
        self.assertTrue(self.doc["adjudication"]["claims_of_no_foreseeable_bugs_prohibited"])

if __name__=="__main__":
    unittest.main()
