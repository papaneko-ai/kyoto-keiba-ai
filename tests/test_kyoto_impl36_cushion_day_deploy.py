import unittest
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]/".github/workflows"
class SidecarContract(unittest.TestCase):
    def setUp(self):
        self.raw=(ROOT/"kyoto-20261128-29-result-handoff.yml").read_text()
        self.doc=yaml.load(self.raw,Loader=yaml.BaseLoader)
        self.job=self.doc["jobs"]["cushion-day-reconciliation"]
    def test_isolated_after_original_handoff(self):
        self.assertEqual(self.job["needs"],"authenticated-handoff")
        self.assertIn("needs.authenticated-handoff.result == 'success'",self.job["if"])
        self.assertEqual(self.job["timeout-minutes"],"4")
        self.assertEqual(self.job["env"]["KYOTO_WEEKEND_HTTP_APPROVED"],"NO")
        self.assertEqual(self.job["env"]["KYOTO_CUSHION_HTTP_APPROVED"],"NO")
        self.assertEqual(self.job["steps"][0]["with"]["ref"],"301916719e5bc0e3a8e392368434f952c16c05db")
    def test_exact_same_run_and_integrity(self):
        cmd=self.job["steps"][3]["run"]
        self.assertIn('gh run download "$GITHUB_RUN_ID"',cmd)
        self.assertIn('kyoto-handoff-$GITHUB_RUN_ID-$KYOTO_TARGET_DAY',cmd)
        self.assertIn("sha256sum --check handoff/report.sha256",cmd)
        self.assertIn("kyoto_impl36_cushion_day",cmd)
        self.assertIn("--out cushion_day/report.json",cmd)
    def test_separate_artifact_retry(self):
        a,b=[x for x in self.job["steps"] if x.get("uses","").startswith("actions/upload-artifact@")]
        self.assertEqual(a["with"]["path"],"cushion_day/")
        self.assertTrue(a["with"]["name"].startswith("kyoto-cushion-day-"))
        self.assertEqual(b["with"],dict(a["with"],overwrite="true"))
    def test_two_existing_handoff_slots(self):
        self.assertNotIn("schedule",self.doc["on"])
if __name__=="__main__":unittest.main()
