"""Nov22 rescue gate: retain all safety guards while preventing known Nov21 fixture veto."""
import unittest
from pathlib import Path

WF=Path(".github/workflows/kyoto-20261121-22-two-source-production-observer.yml")
EXPECTED=["15 0 21 11 *","15 1 21 11 *","5 2 21 11 *","50 2 21 11 *",
          "15 0 22 11 *","15 1 22 11 *","10 2 22 11 *","55 2 22 11 *"]

class Day22Recovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.raw=WF.read_text()
    def test_eight_slots_exactly_unchanged(self):
        actual=[x.split("'")[1] for x in self.raw.splitlines() if x.strip().startswith("- cron:")]
        self.assertEqual(actual,EXPECTED)
        self.assertIn("cancel-in-progress: false",self.raw)
        self.assertIn("queue: max",self.raw)
    def test_full_safe_preflight_without_legacy_bridge_fixture(self):
        pre=self.raw.split("      - name: Offline regression mandatory before any live HTTP",1)[1].split("      - name: Impl23 G06",1)[0]
        self.assertIn("tests.test_kyoto_g05_conditions",pre)
        self.assertIn("tests.test_kyoto_g05_official_track",pre)
        self.assertIn("tests.test_kyoto_weekend_capture",pre)
        self.assertNotIn("tests.test_kyoto_g05_weekend_bridge",pre)
        self.assertIn("set -euo pipefail",pre)
    def test_fixture_remains_executed_after_live_capture_and_provenance(self):
        pc=self.raw.split("  pc-originals-independent:",1)[1].split("  sp-originals-independent:",1)[0]
        observed=pc.index("      - name: Capture official PC observed originals")
        postflight=pc.index("      - name: Offline postflight verify saved original SHA")
        legacy=pc.index("      - name: Archive Saturday synthetic bridge regression")
        seal=pc.index("      - name: Always encrypt any source originals")
        self.assertLess(observed,postflight)
        self.assertLess(postflight,legacy)
        self.assertLess(legacy,seal)
        self.assertIn("continue-on-error: true",pc[legacy:seal])
        self.assertIn("tests.test_kyoto_g05_weekend_bridge",pc[legacy:seal])
        self.assertIn("if: always()",pc[legacy:seal])
    def test_unchanged_source_key_and_postflight_safety(self):
        self.assertEqual(self.raw.count("COLLECTOR_SHA:"),2)
        self.assertIn("de2544c1e9f9951a265419461267146b4023c2ab",self.raw)
        self.assertIn("989aaba017c5450fed91b383421f5d2da53c6c69",self.raw)
        self.assertIn("DAY22_CANDIDATE_NOT_PREFLIGHT_VERIFIED_NO_HTTP",self.raw)
        self.assertEqual(self.raw.count("actions/upload-artifact@v4"),4)
        self.assertEqual(self.raw.count("path: pc_sealed/"),2)
        self.assertEqual(self.raw.count("path: sp_sealed/"),2)
        self.assertNotIn("path: pc_raw/",self.raw)
        self.assertNotIn("path: sp_raw/",self.raw)
        self.assertEqual(self.raw.count("needs: pc-originals-independent"),1)
        self.assertEqual(self.raw.count("AES-GCM ciphertext or safe-stop receipt"),2)

if __name__=="__main__":unittest.main()
