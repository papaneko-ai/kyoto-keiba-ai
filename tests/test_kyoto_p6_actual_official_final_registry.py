"""Tests use genuine source ZIP retrieved from previous official JRA capture CI.

No synthetic substitute for authentic final-source success. Failure injection
never creates fictitious JRA races, odds, stakes, or returns.
"""
import json,os,sqlite3,tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_p6_actual_official_final_registry import (
    register_actual_final_sources,replay_official_sources,OfficialSourceRegistryRejected
)
from diagnostics.kyoto_p6_real_historical_final_payout_reaudit import RealHistoricalPayoutRejected

class RealResultRegistryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    name=os.environ.get("KYOTO_ACTUAL_2DAY_ORIGINAL_ARCHIVE")
    if not name:raise RuntimeError("official_original_artifact_required_no_synthetic_fallback")
    cls.raw=Path(name).read_bytes()
 def setUp(self):
    self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
    self.db=Path(self.t.name)/"official_postrace_only.db"
    self.at="2026-11-12T02:20:30Z"
 def put(self,**kw):
    return register_actual_final_sources(self.db,self.raw,observed_at_utc=kw.get("at",self.at))
 def test_real_two_source_registry(self):
    r=self.put()
    self.assertEqual(r["new_final_sources"],2)
    self.assertEqual(r["total_final_sources"],2)
    self.assertFalse(r["real_paper_trading_verified"])
 def test_real_final_quinella_replay(self):
    self.put();r=replay_official_sources(self.db)
    self.assertEqual(r["races"][0]["quinella"],{"pair":[10,12],"yen_per_100":15090})
    self.assertEqual(r["races"][1]["quinella"],{"pair":[8,11],"yen_per_100":1670})
 def test_real_bracket_final_replay(self):
    self.put();r=replay_official_sources(self.db)
    self.assertEqual(r["races"][0]["bracket"],{"pair":[6,7],"yen_per_100":1540})
    self.assertEqual(r["races"][1]["bracket"],{"pair":[4,6],"yen_per_100":1330})
 def test_same_source_idempotent(self):
    first=self.put()
    second=self.put()
    self.assertEqual(second["new_final_sources"],0)
    self.assertEqual(second["already_present"],2)
    self.assertEqual(second["chain_head"],first["chain_head"])
 def test_second_session_restore(self):
    self.put()
    a=replay_official_sources(self.db)
    self.assertEqual(a,replay_official_sources(self.db))
    self.assertEqual(a["count"],2)
 def test_no_stakes_or_profit_in_real_results(self):
    self.put();r=replay_official_sources(self.db)
    self.assertFalse(r["pre_race_investment_or_profit_proven"])
    self.assertFalse(any("stake" in k or "profit" in k or "roi" in k for item in r["races"] for k in item))
 def test_invalid_archive_not_admitted(self):
    with self.assertRaises(RealHistoricalPayoutRejected):
        register_actual_final_sources(self.db,self.raw+b"x",observed_at_utc=self.at)
 def test_future_timestamp_rejected(self):
    with self.assertRaises(OfficialSourceRegistryRejected):
        self.put(at="2025-10-12T00:00:00Z")
 def test_missing_timezone_rejected(self):
    with self.assertRaises(OfficialSourceRegistryRejected):
        self.put(at="2026-11-12T02:20:30")
 def test_retroactive_first_observation_rejected(self):
    self.put()
    with self.assertRaises(OfficialSourceRegistryRejected):
        self.put(at="2026-11-09T00:00:00Z")
 def test_sql_update_trigger_refuses(self):
    self.put()
    with sqlite3.connect(self.db) as c:
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("UPDATE official_postrace_observations SET raw_payload='{}'")
 def test_sql_delete_trigger_refuses(self):
    self.put()
    with sqlite3.connect(self.db) as c:
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("DELETE FROM official_postrace_observations")
 def test_tampered_payload_with_rehashed_source_refuses(self):
    self.put()
    with sqlite3.connect(self.db) as c:
        c.execute("DROP TRIGGER official_postrace_no_update")
        c.execute("UPDATE official_postrace_observations SET raw_payload='{}' WHERE seq=1")
    with self.assertRaises(OfficialSourceRegistryRejected):
        replay_official_sources(self.db)
 def test_broken_source_chain_refuses(self):
    self.put()
    with sqlite3.connect(self.db) as c:
        c.execute("DROP TRIGGER official_postrace_no_update")
        c.execute("UPDATE official_postrace_observations SET prior_sha256=? WHERE seq=2",("0"*64,))
    with self.assertRaises(OfficialSourceRegistryRejected):
        replay_official_sources(self.db)
 def test_wrong_file_path_refuses(self):
    with self.assertRaises(OfficialSourceRegistryRejected):
        replay_official_sources(self.db)
 def test_readback_does_not_create_data(self):
    self.put()
    with sqlite3.connect(self.db) as c:
        before=c.execute("SELECT count(*) FROM official_postrace_observations").fetchone()[0]
    replay_official_sources(self.db)
    with sqlite3.connect(self.db) as c:
        after=c.execute("SELECT count(*) FROM official_postrace_observations").fetchone()[0]
    self.assertEqual(before,after)
if __name__=="__main__":unittest.main()
