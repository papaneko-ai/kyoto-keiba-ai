"""Targeted R08 early SP gate: no optimistic JRA requests."""
import unittest
from pathlib import Path
from audit.impl27_r08_pc_source_barrier import classify, PC_JOB, PC_SOURCE_STEP


def jobs(pc_status="in_progress", pc_conclusion=None,
         step_status="in_progress", step_conclusion=None, completed=None):
    return [{"name": PC_JOB, "status": pc_status,
             "conclusion": pc_conclusion, "steps": [
                 {"name": PC_SOURCE_STEP, "status": step_status,
                  "conclusion": step_conclusion, "completed_at": completed}
             ]},
            {"name":"sp-originals-independent","status":"in_progress","steps":[]}]


class R08BarrierTests(unittest.TestCase):
    def test_pc_capture_completed_success_allows_early_sp(self):
        decision,why=classify(jobs(step_status="completed",step_conclusion="success",
                                    completed="2026-11-21T00:20:00Z"))
        self.assertEqual(decision,"ALLOW")
        self.assertEqual(why,"pc_source_step_completed")

    def test_pc_capture_completed_failure_allows_fallback_after_stop(self):
        decision,_=classify(jobs(step_status="completed",step_conclusion="failure",
                                 completed="2026-11-21T00:20:00Z"))
        self.assertEqual(decision,"ALLOW")

    def test_pc_still_fetching_does_not_start_sp(self):
        self.assertEqual(classify(jobs())[0],"WAIT")

    def test_pc_skipped_before_http_terminal_allows_sp(self):
        self.assertEqual(classify(jobs(pc_status="completed",pc_conclusion="failure",
                          step_status="completed",step_conclusion="skipped"))[0],"ALLOW")

    def test_pc_skipped_but_job_still_running_must_wait(self):
        self.assertEqual(classify(jobs(step_status="completed",
                          step_conclusion="skipped"))[0],"WAIT")

    def test_pc_finished_but_source_step_unknown_is_blocked(self):
        self.assertEqual(classify(jobs(pc_status="completed",pc_conclusion="cancelled",
                          step_status="completed",step_conclusion="cancelled"))[0],"BLOCK")

    def test_missing_timestamp_is_blocked(self):
        self.assertEqual(classify(jobs(step_status="completed",
                          step_conclusion="success"))[0],"BLOCK")

    def test_missing_duplicate_or_invalid_metadata_no_go(self):
        self.assertNotEqual(classify([])[0],"ALLOW")
        self.assertNotEqual(classify(jobs()+jobs())[0],"ALLOW")
        self.assertEqual(classify(None)[0],"BLOCK")

    def test_workflow_places_barrier_before_sp_source_http(self):
        text=Path(".github/workflows/kyoto-20261121-22-two-source-production-observer.yml").read_text()
        sp=text.split("  sp-originals-independent:",1)[1]
        self.assertNotIn("needs: pc-originals-independent",sp)
        self.assertLess(sp.index("impl27_r08_pc_source_barrier.py"),
                        sp.index("python -m diagnostics.kyoto_weekend_capture --day \"$KYOTO_TARGET_DAY\" --channel SP"))
        self.assertIn("ref: ${{ github.sha }}",sp)
        self.assertIn("timeout-minutes: 35",sp)
        self.assertEqual(text.count("- cron: '"),8)
        self.assertIn("de2544c1e9f9951a265419461267146b4023c2ab",text)
        self.assertIn("KYOTO_JRA_ARCHIVE_AES256_HEX",text)

if __name__=="__main__":
    unittest.main()
