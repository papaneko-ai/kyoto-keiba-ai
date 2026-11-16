"""Execute the actual production stop steps with no JRA HTTP.

Quarantine is deliberate: green dry-run or a user-set variable must never
authorize live requests while the independent critical issues remain open.
"""
import json
import subprocess
import unittest
from pathlib import Path

WF=Path(".github/workflows/kyoto-20261121-22-two-source-production-observer.yml")
REG=Path("docs/diagnostics/KYOTO_20261116_INDEPENDENT_RELEASE_BLOCKERS.json")
STOP="RELEASE_BLOCKED_OPEN_CRITICAL_INCIDENTS_KW001_KW002_NO_JRA_HTTP"

class ContainmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=WF.read_text(encoding="utf8")
        cls.ledger=json.loads(REG.read_text(encoding="utf8"))
    def test_open_findings_cannot_be_relabelled_as_passing(self):
        self.assertEqual(self.ledger["status"],"RELEASE_BLOCKED")
        self.assertGreaterEqual(len(self.ledger["issues"]),6)
        self.assertGreaterEqual(len([x for x in self.ledger["issues"] if x["state"]=="OPEN" and x["severity"]=="CRITICAL"]),2)
    def test_both_jobs_have_immutable_release_stop_before_live_capture(self):
        key="      - name: Critical incident containment - never contact JRA until independently cleared"
        parts=self.source.split(key)
        self.assertEqual(len(parts),3)
        for block in parts[1:]:
            self.assertIn(STOP,block)
            self.assertLess(block.index(STOP),block.index("Capture official PC") if "Capture official PC" in block else block.index("Independently verified SP link"))
    def test_execute_both_actual_quarantine_commands_offline(self):
        key="      - name: Critical incident containment - never contact JRA until independently cleared"
        for block in self.source.split(key)[1:]:
            stage=block.split("      - name: Race date, immutable commit, secret, first attempt and non-replay guard",1)[0]
            script="\n".join(x[10:] for x in stage.splitlines() if x.startswith("          "))
            result=subprocess.run(["bash","-e","-c",script],capture_output=True,text=True,timeout=5)
            self.assertNotEqual(result.returncode,0)
            self.assertIn(STOP,result.stdout)
    def test_schedule_retained_and_no_unapproved_release(self):
        self.assertIn("cron: '5 2 21 11 *'",self.source)
        self.assertIn("cron: '10 2 22 11 *'",self.source)
        self.assertEqual(self.source.count(STOP),2)
        self.assertNotIn("RELEASE_AUTHORIZED",self.source)
if __name__=="__main__":
    unittest.main()
