import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from diagnostics.jra_p1_fb_stage5_registry_binding import load_roster_horse
from diagnostics.jra_p1_fb_stage5_guarded_replay import preflight

REGISTRY=Path("docs/diagnostics/jra_p1_batch14_96_profiles_20261106/feature_rows_148.json")

class ArchivedRegistryBinding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=REGISTRY.read_bytes()
        cls.rows=json.loads(cls.raw)
        cls.pending=next(x for x in cls.rows if x["source_coverage"]["horse_profile"]=="NOT_QUERIED")
        cls.completed=next(x for x in cls.rows if x["source_coverage"]["horse_profile"]=="VERIFIED_SOURCE_ROWS")

    def make(self, rows):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        p=Path(temp.name)/"registry.json"
        p.write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
        return p

    def bind(self, rows=None, meeting_date="2026-11-07", **changes):
        path=REGISTRY if rows is None else self.make(rows)
        kw=dict(registry_file=path, meeting_date=meeting_date,
                race=self.pending["race_number"],number=self.pending["horse_number"])
        kw.update(changes)
        return load_roster_horse(**kw)

    def test_archived_real_registry_has_148_horses_and_52_unqueried(self):
        self.assertEqual(len(self.rows),148)
        self.assertEqual(sum(r["source_coverage"]["horse_profile"]=="NOT_QUERIED" for r in self.rows),52)
        r=self.bind()
        self.assertEqual(r.horse_name,self.pending["horse_name"])
        self.assertEqual(r.pc_url,"https://jra.jp"+self.pending["profile_href"])
        self.assertTrue(r.pc_observed)
        self.assertIsNone(r.sp_url)
        self.assertFalse(r.sp_observed)

    def test_one_pc_source_preflight_historical_only(self):
        r=self.bind()
        gate=preflight(roster=r,prior_attempts=(),
          now=datetime(2026,11,6,6,40,tzinfo=timezone.utc),
          cutoff=datetime(2026,11,7,tzinfo=timezone.utc),channels=("PC",))
        self.assertEqual(len(gate["channels"]),1)
        self.assertFalse(gate["live_automatic_fallback_authorized"])

    def test_same_archived_card_now_expired(self):
        r=self.bind()
        with self.assertRaisesRegex(ValueError,"prerace_cutoff_expired"):
            preflight(roster=r,prior_attempts=(),
              now=datetime(2026,11,9,tzinfo=timezone.utc),
              cutoff=datetime(2026,11,7,tzinfo=timezone.utc),channels=("PC",))

    def test_duplicate_qualified_horse_record_refused(self):
        rows=copy.deepcopy(self.rows)
        rows.append(copy.deepcopy(self.pending))
        with self.assertRaisesRegex(ValueError,"horse_not_unique_in_registry"):
            self.bind(rows)

    def test_mismatched_race_identity_refused(self):
        rows=copy.deepcopy(self.rows)
        row=next(x for x in rows if x["race_number"]==self.pending["race_number"] and x["horse_number"]==self.pending["horse_number"])
        row["race"]="2026-11-07_KYOTO_01R"
        with self.assertRaisesRegex(ValueError,"race_identity_conflict"):
            self.bind(rows,meeting_date="2026-11-07")

    def test_unverified_official_racecard_refused(self):
        rows=copy.deepcopy(self.rows)
        row=next(x for x in rows if x["race_number"]==self.pending["race_number"] and x["horse_number"]==self.pending["horse_number"])
        row["source_coverage"]["racecard"]="MISSING"
        with self.assertRaisesRegex(ValueError,"racecard_not_confirmed"):
            self.bind(rows)

    def test_edited_archive_hash_refused(self):
        with self.assertRaisesRegex(ValueError,"registry_bytes_changed"):
            self.bind(expected_registry_sha256="a"*64)

    def test_already_confirmed_profile_cannot_reacquire(self):
        row=self.completed
        with self.assertRaisesRegex(ValueError,"horse_already_has_source_record"):
            load_roster_horse(registry_file=REGISTRY,meeting_date="2026-11-07",race=row["race_number"],number=row["horse_number"])

    def test_forged_url_refused(self):
        rows=copy.deepcopy(self.rows)
        row=next(x for x in rows if x["race_number"]==self.pending["race_number"] and x["horse_number"]==self.pending["horse_number"])
        row["profile_href"]="https://example.com/spoof"
        with self.assertRaises(ValueError):
            self.bind(rows)

    def test_future_roster_capture_refused(self):
        rows=copy.deepcopy(self.rows)
        row=next(x for x in rows if x["race_number"]==self.pending["race_number"] and x["horse_number"]==self.pending["horse_number"])
        row["racecard_captured_at_utc"]="2026-11-08T01:00:00Z"
        with self.assertRaisesRegex(ValueError,"roster_captured_after_race_day"):
            self.bind(rows)
if __name__=="__main__":
    unittest.main()
