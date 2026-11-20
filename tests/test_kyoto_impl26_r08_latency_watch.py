import unittest
from diagnostics.kyoto_impl26_r08_latency_watch import assess_delay,incident_from_assessment,PC,SP,PC_CAPTURE,SP_CAPTURE

class R08LatencyTests(unittest.TestCase):
    def jobs(self,pc_end="2026-11-21T00:20:00Z",sp_start="2026-11-21T00:21:00Z"):
        return [{"name":PC,"steps":[{"name":PC_CAPTURE,"completed_at":pc_end}]},
                {"name":SP,"steps":[{"name":SP_CAPTURE,"started_at":sp_start}]}]

    def test_normal_delay_no_incident(self):
        result=assess_delay(self.jobs(),123,"20261121")
        self.assertEqual(result["state"],"OBSERVED_WITHIN_THRESHOLD")
        self.assertEqual(result["delay_seconds"],60)
        self.assertIsNone(incident_from_assessment(result))
    def test_prolonged_pc_tail_records_stable_incident(self):
        result=assess_delay(self.jobs(sp_start="2026-11-21T00:29:00Z"),123,"20261121")
        self.assertEqual(result["delay_seconds"],540)
        a=incident_from_assessment(result)
        self.assertEqual(a["risk_ids"],["R08"])
        self.assertEqual(a,incident_from_assessment(result))
        self.assertEqual(a["root_cause_status"],"UNKNOWN")
    def test_sp_overlaps_pc_capture_flags_double_fetch_risk(self):
        result=assess_delay(self.jobs(sp_start="2026-11-21T00:19:00Z"),123,"20261121")
        self.assertTrue(result["overlap_detected"])
        self.assertEqual(result["state"],"OVERLAP_REQUIRES_REVIEW")
        self.assertIsNotNone(incident_from_assessment(result))
    def test_missing_step_never_claims_no_delay(self):
        result=assess_delay([{"name":PC,"steps":[]}],123,"20261121")
        self.assertEqual(result["state"],"UNMEASURABLE")
        self.assertIsNone(result["delay_seconds"])
    def test_malformed_timestamp_fail_closed(self):
        result=assess_delay(self.jobs(pc_end="not-a-time"),123,"20261121")
        self.assertEqual(result["state"],"UNMEASURABLE")
    def test_wrong_day_and_invalid_threshold_rejected(self):
        with self.assertRaises(ValueError):
            assess_delay(self.jobs(),123,"20261123")
        with self.assertRaises(ValueError):
            assess_delay(self.jobs(),123,"20261121",threshold_seconds=0)
    def test_same_time_not_overlap(self):
        result=assess_delay(self.jobs(sp_start="2026-11-21T00:20:00Z"),123,"20261121")
        self.assertFalse(result["overlap_detected"])
        self.assertEqual(result["delay_seconds"],0)

if __name__=="__main__":
    unittest.main()
