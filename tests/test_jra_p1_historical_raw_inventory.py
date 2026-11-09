"""SHA-based inventory tests against the actual archived 148-horse registry."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from diagnostics.jra_p1_historical_raw_inventory import audit

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs/diagnostics/jra_p1_batch14_96_profiles_20261106/feature_rows_148.json"


class RawInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads(REGISTRY.read_text(encoding="utf-8"))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)

    def test_actual_registry_without_originals_blocks(self):
        result = audit(self.rows, self.directory)
        self.assertEqual(result["target_profile_count"], 96)
        self.assertEqual(result["matched_profile_count"], 0)
        self.assertEqual(result["missing_profile_count"], 96)
        self.assertEqual(result["status"], "RAW_ORIGINALS_INCOMPLETE")
        self.assertFalse(result["prediction_ready"])

    def test_existing_matching_bytes_are_recognized(self):
        rows = copy.deepcopy(self.rows)
        raw = b"<html>offline fixture, not JRA</html>"
        row = next(x for x in rows if x["source_coverage"]["horse_profile"] == "VERIFIED_SOURCE_ROWS")
        row["profile_source_sha256"] = hashlib.sha256(raw).hexdigest()
        (self.directory / "saved.html").write_bytes(raw)
        result = audit(rows, self.directory)
        self.assertEqual(result["matched_profile_count"], 1)
        self.assertEqual(result["missing_profile_count"], 95)

    def test_different_bytes_not_accepted_as_proof(self):
        (self.directory / "saved.html").write_bytes(b"<html>unrelated</html>")
        self.assertEqual(audit(self.rows,self.directory)["matched_profile_count"], 0)

    def test_rejects_148_to_147_truncation(self):
        with self.assertRaisesRegex(ValueError, "expected_148_historical_rows"):
            audit(self.rows[:-1], self.directory)

    def test_rejects_bad_profile_hash(self):
        rows = copy.deepcopy(self.rows)
        row = next(x for x in rows if x["source_coverage"]["horse_profile"] == "VERIFIED_SOURCE_ROWS")
        row["profile_source_sha256"] = "bad"
        with self.assertRaisesRegex(ValueError, "invalid_original_hash"):
            audit(rows, self.directory)

    def test_symlink_is_never_followed(self):
        (self.directory / "real.html").write_bytes(b"raw")
        (self.directory / "alias.html").symlink_to(self.directory / "real.html")
        with self.assertRaisesRegex(ValueError, "unsafe_source_candidate"):
            audit(self.rows, self.directory)

if __name__ == "__main__":
    unittest.main()
