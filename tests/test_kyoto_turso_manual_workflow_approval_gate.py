"""Prevent unintended isolated Turso writes from push events."""
from pathlib import Path
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/kyoto-weekend-turso-manual-two-runner-proof.yml"

class ApprovalGateTests(unittest.TestCase):
    def test_write_workflow_is_manual_only(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        header = content.split("permissions:", 1)[0]
        self.assertIn("workflow_dispatch:", header)
        self.assertNotIn("  push:", header)
        self.assertNotIn("ISOLATED_TURSO_CLAIM_WRITE_APPROVED", content)
        self.assertIn("github.event_name == 'workflow_dispatch'", content)
        self.assertEqual(content.count("${{ inputs.confirm_isolated_test_db_only }}"), 4)
        self.assertEqual(content.count("secrets.TURSO_AUTH_TOKEN"), 4)

if __name__ == "__main__":
    unittest.main()
