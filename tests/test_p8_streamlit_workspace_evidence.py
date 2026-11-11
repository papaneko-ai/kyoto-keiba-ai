"""Regression: workspace screenshots are evidence, not proof of billing or reboot."""
import json
import re
import unittest
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[1]/"docs/diagnostics/p8_streamlit_workspace_ui_evidence_20261111.json"
class WorkspaceEvidenceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=SOURCE.read_text(encoding="utf-8")
        cls.record=json.loads(cls.raw)
    def test_every_user_screen_has_sha256_not_raw_bytes(self):
        screens=self.record["screenshots"]
        self.assertEqual([x["id"] for x in screens],["937","938","939","940","941","942","943"])
        for item in screens:
            self.assertRegex(item["sha256"],r"^[0-9a-f]{64}$")
            self.assertNotIn("base64",str(item).lower())
    def test_no_credentials_or_account_email(self):
        for term in ("hisato@", "password", "auth_token", "eyJhbGci", "secret_value"):
            self.assertNotIn(term.lower(),self.raw.lower())
    def test_cannot_treat_free_service_as_zero_account_bill(self):
        o=self.record["interpretation"]
        self.assertTrue(o["official_free_service_policy_verified"])
        self.assertFalse(o["user_billing_transaction_history_independently_verified"])
        self.assertFalse(o["p8_04_award_authorized"])
        self.assertEqual(o["research_score_remains"],98)
    def test_no_current_reboot_operation_image(self):
        self.assertFalse(self.record["interpretation"]["cloud_reboot_event_independently_attested_in_current_screen_set"])
        self.assertTrue(self.record["interpretation"]["existing_prior_reboot_user_screen_claim"])
    def test_remote_evidence_distinct_from_user_screens(self):
        x=self.record["independent_remote_proof"]
        self.assertEqual(x["result"],"success")
        self.assertEqual(x["run_id"],42956087042)
        self.assertTrue(x["public_shadow_only"])

if __name__=="__main__":
    unittest.main()
