"""R31 targeted artifact retry outcome regression; no network, secrets or JRA HTTP."""
from pathlib import Path
import re
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/kyoto-20261121-22-two-source-production-observer.yml"


def upload_steps(text, lane):
    prefix = r"^      - name: "
    blocks = re.split(r"(?="+prefix+r")", text, flags=re.M)
    primary = next(b for b in blocks if f"id: upload_{lane}_primary" in b)
    retry = next(b for b in blocks if
                 f"steps.upload_{lane}_primary.outcome == 'failure'" in b)
    return primary, retry


def job_outcome(primary_failed, retry_failed):
    """Model GitHub Actions conclusion with the primary step continue-on-error."""
    if not primary_failed:
        return "success", False
    return ("failure" if retry_failed else "success"), True


class ArtifactRetryOutcomeRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_primary_failed_then_retry_success_does_not_fail_job(self):
        self.assertEqual(job_outcome(True, False), ("success", True))

    def test_primary_success_does_not_retry(self):
        self.assertEqual(job_outcome(False, False), ("success", False))

    def test_both_uploads_failed_still_fail_closed(self):
        self.assertEqual(job_outcome(True, True), ("failure", True))

    def test_pc_and_sp_actual_workflow_wires_failure_outcome(self):
        for lane in ("pc", "sp"):
            with self.subTest(lane=lane):
                primary, retry = upload_steps(self.workflow, lane)
                self.assertRegex(primary, r"(?m)^        if: always\(\)$")
                self.assertRegex(primary, r"(?m)^        continue-on-error: true$")
                self.assertIn("uses: actions/upload-artifact@v4", primary)
                self.assertIn(f"name: kyoto-{lane}-", primary)
                self.assertIn(f"path: {lane}_sealed/", primary)
                self.assertIn("if-no-files-found: error", primary)
                self.assertIn("uses: actions/upload-artifact@v4", retry)
                self.assertIn(f"path: {lane}_sealed/", retry)
                self.assertIn("overwrite: true", retry)
                self.assertIn("if-no-files-found: error", retry)
                self.assertNotIn("continue-on-error: true", retry)

    def test_protected_sources_not_modified_for_r31(self):
        for value in ("cancel-in-progress: false",
                      "needs: pc-originals-independent",
                      "DAY22_CANDIDATE_NOT_PREFLIGHT_VERIFIED_NO_HTTP",
                      "KYOTO_JRA_ARCHIVE_AES256_HEX"):
            self.assertIn(value, self.workflow)
        self.assertEqual(len(re.findall(r"(?m)^    - cron:", self.workflow)), 8)


if __name__ == "__main__":
    unittest.main()
