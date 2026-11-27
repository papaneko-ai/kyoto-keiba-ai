import unittest,hashlib
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]/".github/workflows"
PIN="47cd7f9e881aa989b9f932373cfaf5278dea223a"
FILE="kyoto-20261128-29-cushion-source.yml"
class CushionDeployment(unittest.TestCase):
    def setUp(self):
        self.raw=(ROOT/FILE).read_text()
        self.doc=yaml.load(self.raw,Loader=yaml.BaseLoader)
        self.job=self.doc["jobs"]["cushion-source-only"]
    def test_no_new_cron_or_pr_execution(self):
        self.assertEqual(set(self.doc["on"]),{"workflow_run","workflow_dispatch"})
        self.assertEqual(self.doc["on"]["workflow_run"]["types"],["completed"])
        self.assertEqual(self.doc["on"]["workflow_run"]["branches"],["main"])
        self.assertEqual(self.doc["on"]["workflow_run"]["workflows"],["Kyoto Nov28-29 independent encrypted original collection","Kyoto Nov28-29 afternoon auxiliary refresh"])
    def test_guard_and_source_identity(self):
        c=self.job["if"]
        for token in ("github.repository == 'papaneko-ai/kyoto-keiba-ai'","github.ref == 'refs/heads/main'","github.event.workflow_run.head_repository.full_name == github.repository","github.event.workflow_run.head_branch == 'main'","NOV28-29-CUSHION-SOURCE-ONLY","2026-11-28","2026-11-29"):
            self.assertIn(token,c)
        self.assertNotIn("conclusion == 'success'",c)
        self.assertEqual(c.count("kyoto-native:"),6)
        self.assertEqual(self.doc["on"]["workflow_dispatch"]["inputs"]["race_day"]["options"],["20261128","20261129"])
    def test_shared_lock_and_exact_target(self):
        c=self.job["concurrency"]
        self.assertEqual(c["cancel-in-progress"],"false");self.assertEqual(c["queue"],"max")
        self.assertEqual(c["group"],"kyoto-20261128-29-source-"+self.job["env"]["KYOTO_TARGET_DAY"])
        self.assertEqual(self.job["timeout-minutes"],"4")
    def test_pinned_source_only_and_existing_key(self):
        self.assertEqual(self.doc["permissions"],{"contents":"read"})
        self.assertEqual(self.job["steps"][0]["with"]["ref"],PIN)
        self.assertIn('test "$(git rev-parse HEAD)" = '+repr(PIN),self.raw)
        self.assertEqual(self.job["env"]["KYOTO_CUSHION_HTTP_APPROVED"],"YES")
        self.assertEqual(self.job["env"]["KYOTO_WEEKEND_HTTP_APPROVED"],"NO")
        self.assertEqual(self.job["env"]["KYOTO_AUX_HTTP_APPROVED"],"NO")
        self.assertEqual(self.raw.count("secrets.KYOTO_JRA_ARCHIVE_AES256_HEX"),1)
        self.assertNotIn("TURSO",self.raw)
        self.assertIn("kyoto_impl36_cushion_capture --day",self.raw)
    def test_encrypted_upload_and_retry(self):
        a,b=[s for s in self.job["steps"] if s.get("uses","").startswith("actions/upload-artifact@")]
        self.assertEqual(a["with"]["path"],"cushion_sealed/")
        self.assertEqual(b["with"],dict(a["with"],overwrite="true"))
        self.assertEqual(a["continue-on-error"],"true")
        self.assertIn("outcome == 'failure'",b["if"])
        self.assertNotIn("continue-on-error",b)
    def test_native_26_unchanged(self):
        names=("two-source-production-observer","auxiliary-refresh","postrace-evidence","result-handoff","workout-source")
        count=0
        for n in names:
            p=ROOT/("kyoto-20261128-29-"+n+".yml")
            count+=len(yaml.load(p.read_text(),Loader=yaml.BaseLoader)["on"]["schedule"])
        self.assertEqual(count,26)
if __name__=="__main__":unittest.main()
