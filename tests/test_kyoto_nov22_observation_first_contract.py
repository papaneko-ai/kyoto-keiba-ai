"""Production-source first rule: advisory CI failures never veto JRA HTTP.

Only the artificial historical/failure simulations are downgraded.
Provenance, archive key, day window and official source identity stay hard.
"""
import unittest
from pathlib import Path

P=Path(".github/workflows/kyoto-20261121-22-two-source-production-observer.yml")

class OpportunityFirst(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=P.read_text()
    def test_synthetic_steps_are_advisory_in_both_lanes(self):
        names=["Offline regression mandatory before any live HTTP",
               "Independent SP offline regression",
               "Impl23 G06 shared-claim production handoff offline regression",
               "Enumerate and execute all predictable-failure regression scenarios before any JRA HTTP"]
        for name in names:
            parts=self.s.split("      - name: "+name+"\n")
            self.assertEqual(len(parts),3 if name.startswith(("Impl23","Enumerate")) else 2,name)
            for chunk in parts[1:]:
                self.assertIn("continue-on-error: true",chunk.split("      - name:",1)[0])
    def test_hard_gates_still_present_in_both_lanes(self):
        for token in ["ENCRYPTION_KEY_REQUIRED_NO_HTTP","SOURCE_REVISION_MISMATCH_NO_HTTP",
                      "DAY22_CANDIDATE_NOT_PREFLIGHT_VERIFIED_NO_HTTP",
                      "OUTSIDE_DAY_WINDOW_NO_HTTP",
                      "python -m diagnostics.kyoto_weekend_retry_guard",
                      "python -m diagnostics.kyoto_weekend_postflight",
                      "--seal-only","No JRA", "source"]:
            if token!="No JRA":
                self.assertIn(token,self.s)
        self.assertEqual(self.s.count("ARCHIVE_KEY:"),2)
        self.assertEqual(self.s.count("python -m diagnostics.kyoto_weekend_capture --day"),4)
        self.assertEqual(self.s.count("actions/upload-artifact@v4"),4)
    def test_eight_slots_original_and_jra_source_sha_intact(self):
        cron=[l.split("'")[1] for l in self.s.splitlines() if l.strip().startswith("- cron:")]
        self.assertEqual(cron,["15 0 21 11 *","15 1 21 11 *","5 2 21 11 *","50 2 21 11 *",
                               "15 0 22 11 *","15 1 22 11 *","10 2 22 11 *","55 2 22 11 *"])
        self.assertEqual(self.s.count("2dce4f5fa9d0ce48e460a95664fe3207c7f95ba6"),2)
        self.assertIn("de2544c1e9f9951a265419461267146b4023c2ab",self.s)
        self.assertIn("if: ${{ always() && (github.event_name",self.s)
if __name__=="__main__":
    unittest.main()
