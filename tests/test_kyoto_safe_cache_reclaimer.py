"""Destructive boundaries: disposable cache only, no protected data."""
import os
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_safe_cache_reclaimer import (
    ReclaimRejected, initialize_cache, reclaim_disposable_cache,
)
NOW = 1_800_000_000 * 1_000_000_000

class ReclaimerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name) / "managed_cache"
        initialize_cache(self.cache)

    def make(self, name, content=b"ABC", age=2 * 86400):
        p = self.cache / name
        p.write_bytes(content)
        t = NOW // 1_000_000_000 - age
        os.utime(p, (t, t))
        return p

    def reclaim(self, **kwargs):
        cfg = dict(cache_dir=self.cache, now_ns=NOW)
        cfg.update(kwargs)
        return reclaim_disposable_cache(**cfg)

    def test_dry_run_no_delete(self):
        p = self.make("tmp_a.cache")
        r = self.reclaim()
        self.assertEqual(r["projected_bytes"], 3)
        self.assertEqual(r["freed_bytes"], 0)
        self.assertTrue(p.exists())

    def test_expired_cache_deleted(self):
        p = self.make("tmp_a.cache")
        r = self.reclaim(dry_run=False)
        self.assertEqual(r["freed_bytes"], 3)
        self.assertFalse(p.exists())
        self.assertTrue((self.cache / ".kyoto_disposable_cache_v1").exists())

    def test_source_and_ledger_never_deleted(self):
        source = self.make("race_original.html")
        ledger = self.make("ledger.sqlite")
        self.make("tmp_a.cache")
        self.reclaim(dry_run=False)
        self.assertTrue(source.exists())
        self.assertTrue(ledger.exists())

    def test_new_file_not_deleted(self):
        p = self.make("tmp_recent.cache", age=10)
        self.reclaim(dry_run=False)
        self.assertTrue(p.exists())

    def test_symlink_not_deleted(self):
        out = Path(self.temp.name) / "important.dat"
        out.write_text("important")
        (self.cache / "tmp_link.cache").symlink_to(out)
        self.reclaim(dry_run=False)
        self.assertEqual(out.read_text(), "important")
        self.assertTrue((self.cache / "tmp_link.cache").is_symlink())

    def test_hard_link_not_deleted(self):
        out = Path(self.temp.name) / "important.dat"
        out.write_bytes(b"SAFE")
        os.link(out, self.cache / "tmp_hardlink.cache")
        self.reclaim(dry_run=False)
        self.assertEqual(out.read_bytes(), b"SAFE")

    def test_uninitialized_directory_denied(self):
        other = Path(self.temp.name) / "foreign"
        other.mkdir()
        (other / "tmp_a.cache").write_bytes(b"ABC")
        with self.assertRaises(ReclaimRejected):
            reclaim_disposable_cache(cache_dir=other, now_ns=NOW, dry_run=False)
        self.assertTrue((other / "tmp_a.cache").exists())

    def test_idempotent(self):
        self.make("tmp_a.cache")
        self.reclaim(dry_run=False)
        r = self.reclaim(dry_run=False)
        self.assertEqual(r["freed_bytes"], 0)
        self.assertEqual(r["deleted"], [])

    def test_oldest_first_and_bounded(self):
        self.make("tmp_newer.cache", b"12345", age=2 * 86400)
        self.make("tmp_older.cache", b"ABCD", age=4 * 86400)
        r = self.reclaim(dry_run=False, requested_free_bytes=4)
        self.assertEqual(r["deleted"], ["tmp_older.cache"])
        self.assertTrue((self.cache / "tmp_newer.cache").exists())

    def test_symlink_directory_denied(self):
        link = Path(self.temp.name) / "shortcut"
        link.symlink_to(self.cache, target_is_directory=True)
        with self.assertRaises(ReclaimRejected):
            reclaim_disposable_cache(cache_dir=link, now_ns=NOW, dry_run=False)

    def test_invalid_ttl_denied(self):
        self.make("tmp_x.cache")
        with self.assertRaises(ReclaimRejected):
            self.reclaim(ttl_seconds=0, dry_run=False)

    def test_cannot_reinitialize_existing(self):
        with self.assertRaises(ReclaimRejected):
            initialize_cache(self.cache)

if __name__ == "__main__":
    unittest.main()
