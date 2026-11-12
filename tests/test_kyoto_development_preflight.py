import copy
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_development_preflight import verify, PreflightBlocked, REQUIRED


class ContinuityGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "existing.py").write_text("pass")
        (self.root / "proof.json").write_text("{}")
        self.inventory = {"schema":"kyoto_feature_reuse_inventory.v1","features":[
            {"id":key,"status":"IMPLEMENTED_PARTIAL","code_paths":["existing.py"],
             "evidence_paths":["proof.json"],"remaining":"Implementation exists; integrate it."}
            for key in sorted(REQUIRED)]}
        self.intent = {"schema":"kyoto_change_intent.v1","changes":[
            {"feature_id":"PC_RACECARD","action":"INTEGRATE",
             "rationale":"Reuse the existing PC racecard collection rather than rewrite it."}]}

    def audit(self):
        return verify(self.root, self.inventory, intent=self.intent)

    def test_reuse_passes(self):
        self.assertTrue(self.audit()["intent_checked"])

    def test_duplicate_new_rejected(self):
        self.intent["changes"][0]["action"] = "NEW"
        with self.assertRaisesRegex(PreflightBlocked,"duplicate_new_implementation"):
            self.audit()

    def test_deleted_code_rejected(self):
        (self.root / "existing.py").unlink()
        with self.assertRaisesRegex(PreflightBlocked,"missing_evidence_file"):
            self.audit()

    def test_missing_feature_rejected(self):
        self.inventory["features"].pop()
        with self.assertRaisesRegex(PreflightBlocked,"inventory_incomplete|required_feature_missing"):
            self.audit()

    def test_missing_reason_rejected(self):
        self.intent["changes"][0]["rationale"]="skip"
        with self.assertRaisesRegex(PreflightBlocked,"missing_reuse_rationale"):
            self.audit()

    def test_research_scope_is_not_limited_to_odds(self):
        for name in ("P2_REAL_FEATURE_MATRIX", "P7_EVO01_INFORMATION_VALUE",
                     "P8_STORAGE_PROTECTION", "P1_FB_SHARED_LEDGER",
                     "P1_MULTIDAY_OFFICIAL_RESULTS", "P1_TRAINING_WORKOUTS",
                     "P1_JOCKEY_TRAINER_STATS", "P1_TRACK_WEATHER",
                     "PC_SP_MEASURED_ROUTING", "P1_ORIGINAL_BACKUP_RECOVERY"):
            self.assertIn(name, REQUIRED)

    def test_removed_history_and_evo_cannot_pass_preflight(self):
        self.inventory["features"] = [
            x for x in self.inventory["features"]
            if x["id"] != "P7_EVO01_INFORMATION_VALUE"]
        with self.assertRaisesRegex(PreflightBlocked,
                                   "inventory_incomplete|required_feature_missing"):
            self.audit()

    def test_existing_code_cannot_be_mislabeled_as_unimplemented(self):
        self.inventory["features"][0]["status"] = "DESIGNED_NOT_IMPLEMENTED"
        with self.assertRaisesRegex(PreflightBlocked,"designed_status_has_existing_code"):
            self.audit()

    def test_conflicting_intent_for_same_feature_is_rejected(self):
        self.intent["changes"].append({
            "feature_id":"PC_RACECARD","action":"NEW",
            "rationale":"Duplicated implementation declaration must never be accepted"})
        with self.assertRaisesRegex(PreflightBlocked,"duplicate_intent_feature"):
            self.audit()

    def test_three_runs_deterministic(self):
        a=self.audit()
        for _ in range(3):
            self.assertEqual(self.audit(),a)

    def test_verification_does_not_mutate_inputs(self):
        before=copy.deepcopy(self.inventory)
        self.audit()
        self.assertEqual(before,self.inventory)


if __name__ == "__main__":
    unittest.main()
