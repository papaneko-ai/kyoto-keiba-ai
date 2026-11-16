"""No-network fault-injection regression for incident evidence persistence."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from diagnostics.kyoto_safe_stop_artifact import record_pre_http_stop


class SafeStopFaultTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.target = self.base / "missing" / "evidence"

    def test_missing_directory_is_created_and_saved(self):
        result = record_pre_http_stop(self.target, race_day="20261121", reason="PREFLIGHT_FAILURE")
        self.assertEqual(json.loads((self.target / "safe_stop.json").read_text()), result)

    def test_zero_real_http_and_no_authentication_claim(self):
        result = record_pre_http_stop(self.target, race_day="20261122", reason="SIMULATED_PC_FAILURE")
        self.assertEqual(result["actual_jra_http_requests"], 0)
        self.assertFalse(result["JRA_success"])
        self.assertFalse(result["official_originals_authenticated"])
        self.assertEqual(result["operational_credit"], 0)

    def test_receipt_time_is_utc(self):
        result = record_pre_http_stop(self.target, race_day="20261121", reason="SIMULATED_STOP")
        stamp = datetime.fromisoformat(result["saved_at_utc"])
        self.assertEqual(stamp.utcoffset(), timezone.utc.utcoffset(None))

    def test_no_rewrite_of_prior_evidence(self):
        record_pre_http_stop(self.target, race_day="20261121", reason="FIRST")
        original = (self.target / "safe_stop.json").read_bytes()
        with self.assertRaises(FileExistsError):
            record_pre_http_stop(self.target, race_day="20261121", reason="SECOND")
        self.assertEqual((self.target / "safe_stop.json").read_bytes(), original)

    def test_reject_symlink_destination(self):
        actual = self.base / "actual"
        actual.mkdir()
        self.target.parent.mkdir()
        self.target.symlink_to(actual, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "destination_symlink"):
            record_pre_http_stop(self.target, race_day="20261121", reason="SIMULATED")

    def test_reject_symlink_receipt(self):
        self.target.mkdir(parents=True)
        victim = self.base / "victim.txt"
        victim.write_text("do not overwrite")
        (self.target / "safe_stop.json").symlink_to(victim)
        with self.assertRaisesRegex(ValueError, "target_symlink"):
            record_pre_http_stop(self.target, race_day="20261122", reason="SIMULATED")
        self.assertEqual(victim.read_text(), "do not overwrite")

    def test_non_directory_fails_closed(self):
        self.target.parent.mkdir()
        self.target.write_text("not a directory")
        with self.assertRaises((FileExistsError, ValueError)):
            record_pre_http_stop(self.target, race_day="20261121", reason="SIMULATED")


if __name__ == "__main__":
    unittest.main()
