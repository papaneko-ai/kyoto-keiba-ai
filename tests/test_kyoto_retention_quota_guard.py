"""Guards must never delete historical source or research evidence."""
import unittest

from diagnostics.kyoto_retention_quota_guard import (
    DEFAULT_QUOTA_BYTES, PROTECTED, RetentionRejected,
    retention_action, storage_status,
)


class StorageBudgetTests(unittest.TestCase):
    def test_thresholds(self):
        cases = (
            (0.0, "NORMAL"),
            (0.60, "WARNING"),
            (0.75, "ARCHIVE_REVIEW"),
            (0.85, "HARD_STOP_UNNECESSARY_RAW_WRITES"),
            (0.99, "HARD_STOP_UNNECESSARY_RAW_WRITES"),
        )
        for ratio, expected in cases:
            with self.subTest(ratio=ratio):
                report = storage_status(
                    used_bytes=round(DEFAULT_QUOTA_BYTES * ratio)
                )
                self.assertEqual(report["stage"], expected)
                self.assertFalse(report["automatic_deletion_permitted"])

    def test_reject_unknown_and_negative_quota(self):
        for args in (
            {"used_bytes": -1},
            {"used_bytes": 5, "quota_bytes": 0},
            {"used_bytes": 0, "remaining_write_rows": -1},
            {"used_bytes": True},
            {"used_bytes": 0, "quota_bytes": False},
        ):
            with self.subTest(args=args), self.assertRaises(RetentionRejected):
                storage_status(**args)


class RetentionTests(unittest.TestCase):
    def action(self, kind, **overrides):
        data = dict(
            kind=kind, captured_on="2018-01-01", today="2026-11-11",
            archive_verified=True, still_needed_for_recheck=False,
            model_depends_on_it=False, provenance_available=True,
        )
        data.update(overrides)
        return retention_action(**data)

    def test_every_protected_record_retained(self):
        for kind in PROTECTED:
            with self.subTest(kind=kind):
                r = self.action(kind)
                self.assertEqual(r["action"], "KEEP_LONG_TERM")
                self.assertFalse(r["delete_now"])

    def test_old_raw_is_never_automatically_deleted(self):
        r = self.action("RAW_HTML")
        self.assertEqual(r["action"], "MANUAL_DELETION_CANDIDATE")
        self.assertFalse(r["delete_now"])
        self.assertTrue(r["manual_approval_required_for_deletion"])

    def test_no_restore_or_provenance_blocks_old_raw(self):
        for override in (
            {"archive_verified": False},
            {"provenance_available": False},
            {"still_needed_for_recheck": True},
            {"model_depends_on_it": True},
        ):
            with self.subTest(override=override):
                self.assertEqual(
                    self.action("RAW_HTML", **override)["action"],
                    "PROTECT_PENDING_ARCHIVE_REVIEW",
                )

    def test_recent_raw_hot(self):
        self.assertEqual(
            self.action("RAW_SNAPSHOT", captured_on="2026-10-01")["action"],
            "KEEP_HOT",
        )

    def test_unknown_is_preserved(self):
        r = self.action("EXPERIMENTAL_IMPORTANT_CATEGORY")
        self.assertEqual(r["action"], "PROTECT_UNKNOWN_KIND")
        self.assertFalse(r["delete_now"])

    def test_future_date_rejected(self):
        with self.assertRaises(RetentionRejected):
            self.action("CACHE", captured_on="2027-01-01")

    def test_invalid_types_rejected(self):
        with self.assertRaises(RetentionRejected):
            self.action("RAW_HTML", archive_verified=1)


if __name__ == "__main__":
    unittest.main()
