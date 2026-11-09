import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from diagnostics.jra_p1_fb_stage5_guarded_replay import RosterHorse
from diagnostics.jra_p1_fb_stage5_global_attempt_registry import GlobalAttemptRegistry, Blocked
from diagnostics.jra_p1_fb_stage5_ledger_replay import run_ledger_replay
from diagnostics.jra_p1_fb_stage4_mock_adapter import Response

T=datetime(2026,11,13,6,0,tzinfo=timezone.utc)
CUTOFF=datetime(2026,11,14,tzinfo=timezone.utc)
PC="https://jra.jp/JRADB/accessU.html?CNAME=pw01dud002020103876/AA"
SP="https://sp.jra.jp/JRADB/accessU.html?CNAME=sj01ude002020103876/AA"
ROSTER=RosterHorse("2026-11-14",11,1,"モンドプリューム","b"*64,PC,SP,True,True)
RAW=b"<html>OFFLINE REPLAY</html>"
def replay(channel,url): return Response(RAW,200,"text/html",url)
replay.offline_replay_only=True
def okay(body,horse):return {"horse_name":horse,"prior_rows":[{"date":"2026-10-01"}],"invalid_rows":[]}
def broken(body,horse):raise ValueError("synthetic_invalid_history")

class LedgerReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.db=self.base/"ledger.db"
    def run_case(self,name="one",**changes):
        kw=dict(folder=self.base/name,roster=ROSTER,now=T,cutoff=CUTOFF,
                replay_transport=replay,parsers={"PC":broken,"SP":okay},
                ledger_path=self.db)
        kw.update(changes)
        return run_ledger_replay(**kw)
    def test_fallback_two_reserved_receipted(self):
        result=self.run_case()
        self.assertEqual(result["selected"],"SP")
        self.assertEqual(result["global_reservations"],2)
        store=GlobalAttemptRegistry(self.db)
        self.assertEqual(len(store.inventory()),2)
        self.assertEqual(len(store.unresolved()),0)
        self.assertEqual([a["detail"] for a in store.inventory()],["QUARANTINED","VALIDATED"])

    def test_primary_success_consumes_one(self):
        result=self.run_case(parsers={"PC":okay,"SP":broken})
        self.assertEqual(result["global_reservations"],1)
        self.assertEqual(len(GlobalAttemptRegistry(self.db).inventory()),1)

    def test_same_url_replayed_elsewhere_refused_even_after_success(self):
        self.run_case(parsers={"PC":okay,"SP":broken})
        with self.assertRaisesRegex(Blocked,"url_already_reserved_in_global_ledger"):
            self.run_case(name="second",now=T+timedelta(minutes=1),
                parsers={"PC":okay,"SP":broken})

    def test_preexisting_global_gap_blocks_without_fallback(self):
        store=GlobalAttemptRegistry(self.db)
        store.reserve(channel="PC",
          url="https://jra.jp/JRADB/accessU.html?CNAME=pw01dud002020103876/BB",
          race_key="2026-11-14_KYOTO_10R",horse_number=2,
          roster_sha="a"*64,now=T-timedelta(seconds=1),
          cutoff=CUTOFF,official_roster_observed=True)
        with self.assertRaisesRegex(Blocked,"global_gap_or_clock_rollback"):
            self.run_case()
        receipt=json.loads((self.base/"one"/"receipt.json").read_text())
        self.assertEqual(len(receipt["attempts"]),1)
        self.assertTrue(receipt["incidents"][0]["open"])
        self.assertFalse((self.base/"one"/"original_sp.html").exists())
        self.assertEqual(len(store.inventory()),1)

    def test_failed_parser_keeps_record_and_allows_one_distinct_source(self):
        result=self.run_case(parsers={"PC":broken,"SP":broken})
        self.assertEqual(result["status"],"BOTH_FAILED_QUARANTINED")
        self.assertEqual(len(GlobalAttemptRegistry(self.db).inventory()),2)

    def test_old_event_timestamp_rejected(self):
        with self.assertRaisesRegex(ValueError,"prerace_cutoff_expired"):
            self.run_case(now=datetime(2026,11,15,tzinfo=timezone.utc))
        self.assertEqual(GlobalAttemptRegistry(self.db).inventory(),[])

    def test_non_offline_transport_rejected(self):
        with self.assertRaisesRegex(Blocked,"offline_replay_transport_only"):
            self.run_case(replay_transport=lambda a,b:replay(a,b))
        self.assertFalse(self.db.exists())

    def test_invalid_second_channel_not_in_official_roster_rejected(self):
        from dataclasses import replace
        invalid=replace(ROSTER,sp_observed=False)
        with self.assertRaisesRegex(ValueError,"unverified_official_roster_link"):
            self.run_case(roster=invalid)
        self.assertFalse(self.db.exists())

if __name__=="__main__":
    unittest.main()
