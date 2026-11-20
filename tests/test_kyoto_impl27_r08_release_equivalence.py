"""Strict safety equivalence for the proposed R08 early-SP GitHub release gate.

This complements, not bypasses, the pre-existing serialized-production gate.
"""
import unittest
from pathlib import Path
from audit.impl27_r08_pc_source_barrier import classify,PC_JOB,PC_SOURCE_STEP

WORKFLOW=Path(".github/workflows/kyoto-20261121-22-two-source-production-observer.yml")
EXPECTED=[
    "15 0 21 11 *","15 1 21 11 *","5 2 21 11 *","50 2 21 11 *",
    "15 0 22 11 *","15 1 22 11 *","10 2 22 11 *","55 2 22 11 *",
]
def step(jobs):
    return [{"name":PC_JOB,"status":"in_progress","steps":[
        {"name":PC_SOURCE_STEP,"status":"in_progress","conclusion":None}]}]

class EquivalentR08ReleaseGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow=WORKFLOW.read_text()
        cls.pc,cls.sp=cls.workflow.split("  sp-originals-independent:",1)
    def test_all_eight_exact_scheduled_slots(self):
        lines=[line.strip().split("'")[1] for line in self.workflow.splitlines()
               if line.strip().startswith("- cron:")]
        self.assertEqual(lines,EXPECTED)
        self.assertIn("cancel-in-progress: false",self.workflow)
        self.assertIn("queue: max",self.workflow)
    def test_immutable_collector_and_day22_approval_remain_protected(self):
        self.assertEqual(self.workflow.count("COLLECTOR_SHA:"),2)
        self.assertEqual(self.workflow.count("de2544c1e9f9951a265419461267146b4023c2ab"),4)
        self.assertEqual(self.workflow.count("vars.KYOTO_NOV22_VERIFIED_COLLECTOR_SHA || '989aaba017c5450fed91b383421f5d2da53c6c69'"),2)
        self.assertIn("DAY22_CANDIDATE_NOT_PREFLIGHT_VERIFIED_NO_HTTP",self.workflow)
    def test_encrypted_originals_only_and_still_retried(self):
        self.assertEqual(self.workflow.count("actions/upload-artifact@v4"),4)
        self.assertEqual(self.workflow.count("overwrite: true"),2)
        for lane in ("pc","sp"):
            self.assertEqual(self.workflow.count("path: "+lane+"_sealed/"),2)
            self.assertNotIn("path: "+lane+"_raw/",self.workflow)
            self.assertIn("steps.upload_"+lane+"_primary.outcome == 'failure'",self.workflow)
        self.assertEqual(self.workflow.count("KYOTO_JRA_ARCHIVE_AES256_HEX"),2)
    def test_no_early_official_http_without_verified_pc_end(self):
        self.assertNotIn("needs: pc-originals-independent",self.sp)
        proof=self.sp.index("impl27_r08_pc_source_barrier.py")
        capture=self.sp.index("--channel SP --source sp_raw")
        self.assertLess(proof,capture)
        self.assertIn("ref: ${{ github.sha }}",self.sp)
        self.assertIn("timeout-minutes: 35",self.sp)
        self.assertIn("timeout-minutes: 20",self.pc)
    def test_barrier_fail_closed_if_missing_or_running(self):
        self.assertEqual(classify(None)[0],"BLOCK")
        self.assertNotEqual(classify([])[0],"ALLOW")
        self.assertEqual(classify(step([]))[0],"WAIT")
        other=step([])
        other[0]["steps"][0]["status"]="completed"
        other[0]["steps"][0]["conclusion"]="success"
        self.assertEqual(classify(other)[0],"BLOCK")  # no actual end UTC
    def test_pc_source_ends_before_only_non_jra_tail(self):
        end=self.pc.index("      - name: Capture official PC observed originals")
        tail=self.pc.split("      - name: Offline postflight verify saved original SHA and UTC before evidence sealing",1)[1]
        self.assertIn("--channel PC --root pc_raw",tail)
        self.assertIn("--seal-only",tail)
        self.assertNotIn(" --channel PC --source pc_raw --destination pc_sealed\n",tail)

if __name__=="__main__":
    unittest.main()
