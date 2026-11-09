import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

from diagnostics.jra_p1_fb_stage5_guarded_replay import RosterHorse
from diagnostics.jra_p1_fb_stage5_global_attempt_registry import Blocked,GlobalAttemptRegistry
from diagnostics.jra_p1_fb_stage5_offline_http_envelope import ScriptedResponse,ScriptedOfflineTransport
from diagnostics.jra_p1_fb_stage5_scheduled_offline_replay import (
    OfflineScheduledTransport,run_scheduled_offline_replay)

T=datetime(2026,11,13,6,0,tzinfo=timezone.utc)
CUT=datetime(2026,11,14,0,0,tzinfo=timezone.utc)
PC="https://jra.jp/JRADB/accessU.html?CNAME=pw01dud002020103876/AA"
SP="https://sp.jra.jp/JRADB/accessU.html?CNAME=sj01ude002020103876/AA"
HORSE=RosterHorse("2026-11-14",11,1,"モンドプリューム","a"*64,PC,SP,True,True)
RAW=b"<html>scripted only</html>"

def scripted():
    return ScriptedOfflineTransport({(c,u):ScriptedResponse(u,200,"text/html",u,RAW)
                                    for c,u in (("PC",PC),("SP",SP))})
def good(b,n):
    return {"horse_name":n,"prior_rows":[{"date":"2026-10-01"}],"invalid_rows":[]}
def bad(b,n):
    raise ValueError("parser_fault")
class FakeClock:
    def __init__(self,start=T,tick=100):
        self.now=start
        self.tick=tick
        self.sleeps=[]
        self.freeze_sleep=False
    def wall(self):return self.now
    def mono(self):return self.tick
    def sleep(self,seconds):
        self.sleeps.append(seconds)
        if not self.freeze_sleep:
            self.tick+=seconds
            self.now+=timedelta(seconds=seconds)

class ScheduledTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.clock=FakeClock()
    def run_case(self,**changes):
        kw=dict(folder=self.root/"incident",roster=HORSE,now=T,cutoff=CUT,
                scripted_transport=scripted(),parsers={"PC":bad,"SP":good},
                ledger_path=self.root/"ledger.sqlite",
                wall_clock=self.clock.wall,monotonic_clock=self.clock.mono,
                sleep=self.clock.sleep)
        kw.update(changes)
        return run_scheduled_offline_replay(**kw)
    def inventory(self):
        return GlobalAttemptRegistry(self.root/"ledger.sqlite").inventory()
    def test_two_sources_obey_actual_injected_monotonic_gap(self):
        result=self.run_case()
        self.assertEqual(result["selected"],"SP")
        self.assertEqual(len(result["measured_monotonic_seconds"]),2)
        self.assertGreaterEqual(result["measured_monotonic_seconds"][1]-
                                result["measured_monotonic_seconds"][0],2)
        self.assertEqual(len(self.clock.sleeps),1)
        self.assertEqual(len(self.inventory()),2)
        self.assertEqual((self.root/"incident"/"original_pc.html").read_bytes(),RAW)
        self.assertEqual((self.root/"incident"/"original_sp.html").read_bytes(),RAW)
        self.assertEqual(result["network_requests"],0)
    def test_good_pc_only_no_sleep(self):
        result=self.run_case(parsers={"PC":good,"SP":bad})
        self.assertEqual(result["selected"],"PC")
        self.assertEqual(self.clock.sleeps,[])
        self.assertEqual(len(self.inventory()),1)
    def test_no_progressing_monotonic_clock_aborts_backup(self):
        self.clock.freeze_sleep=True
        with self.assertRaisesRegex(Blocked,"monotonic_gap_not_satisfied"):
            self.run_case()
        self.assertEqual(len(self.inventory()),1)
        self.assertFalse((self.root/"incident"/"original_sp.html").exists())
        receipt=json.loads((self.root/"incident"/"receipt.json").read_text())
        self.assertTrue(receipt["incidents"][0]["open"])
    def test_cutoff_reached_while_sleeping_blocks_backup(self):
        self.clock.now=CUT-timedelta(seconds=1)
        with self.assertRaisesRegex(Blocked,"cutoff_during_request_scheduling"):
            self.run_case()
        self.assertEqual(len(self.inventory()),1)
    def test_cutoff_initial_preflight(self):
        with self.assertRaisesRegex(ValueError,"prerace_cutoff_expired"):
            self.run_case(now=CUT)
        self.assertFalse((self.root/"ledger.sqlite").exists())
    def test_fake_clock_initially_after_cutoff_blocks_pre_reserve(self):
        self.clock.now=CUT
        with self.assertRaisesRegex(Blocked,"cutoff_during_request_scheduling"):
            self.run_case()
        self.assertEqual(self.inventory(),[])
    def test_untrusted_transport_rejected(self):
        with self.assertRaisesRegex(Blocked,"strict_in_memory_scripted_transport_required"):
            self.run_case(scripted_transport=lambda a,b:None)
        self.assertFalse((self.root/"ledger.sqlite").exists())
    def test_unsupported_sp_link_blocks_before_ledger(self):
        from dataclasses import replace
        with self.assertRaisesRegex(ValueError,"unverified_official_roster_link"):
            self.run_case(roster=replace(HORSE,sp_observed=False))
        self.assertFalse((self.root/"ledger.sqlite").exists())
    def test_call_transport_without_observation_refused(self):
        runner=OfflineScheduledTransport(scripted(),wall_clock=self.clock.wall,
                 monotonic_clock=self.clock.mono,sleep=self.clock.sleep,cutoff=CUT)
        with self.assertRaisesRegex(Blocked,"unobserved_scripted_request"):
            runner("PC",PC)
    def test_sleep_does_not_make_time_go_backward(self):
        runner=OfflineScheduledTransport(scripted(),wall_clock=self.clock.wall,
                 monotonic_clock=self.clock.mono,sleep=self.clock.sleep,cutoff=CUT)
        runner.observe("PC",PC,0)
        self.clock.now-=timedelta(seconds=10)
        self.clock.tick+=2
        with self.assertRaisesRegex(Blocked,"wall_clock_rolled_backward"):
            runner.observe("SP",SP,1)
    def test_untrustworthy_monotonic_nan(self):
        runner=OfflineScheduledTransport(scripted(),wall_clock=self.clock.wall,
                 monotonic_clock=lambda:float("nan"),sleep=self.clock.sleep,cutoff=CUT)
        with self.assertRaisesRegex(Blocked,"untrustworthy_monotonic_clock"):
            runner.observe("PC",PC,0)
    def test_minimum_gap_cannot_be_shortened(self):
        with self.assertRaisesRegex(Blocked,"unsafe_requested_gap"):
            OfflineScheduledTransport(scripted(),wall_clock=self.clock.wall,
                monotonic_clock=self.clock.mono,sleep=self.clock.sleep,cutoff=CUT,
                minimum_gap_seconds=1)
    def test_timestamp_consumed_ledger_as_observed(self):
        result=self.run_case()
        saved=self.inventory()
        self.assertEqual(saved[0]["reserved_utc"],T.timestamp())
        self.assertEqual(saved[1]["reserved_utc"],(T+timedelta(seconds=2)).timestamp())
        self.assertEqual(len(result["measured_monotonic_seconds"]),2)
    def test_exhausted_budget_stops_backup(self):
        with self.assertRaisesRegex(Blocked,"global_request_budget_exhausted"):
            self.run_case(global_attempt_limit=1)
        self.assertEqual(len(self.inventory()),1)
    def test_real_monotonic_sleep_two_seconds_without_network(self):
        import time
        now=datetime.now(timezone.utc)
        from dataclasses import replace
        tomorrow=(now+timedelta(days=1)).date().isoformat()
        fresh=replace(HORSE,meeting_date=tomorrow)
        began=time.monotonic()
        result=self.run_case(roster=fresh,now=now,
            cutoff=now+timedelta(hours=1),wall_clock=lambda:datetime.now(timezone.utc),
            monotonic_clock=time.monotonic,sleep=time.sleep)
        elapsed=time.monotonic()-began
        self.assertGreaterEqual(elapsed,2.0)
        ticks=result["measured_monotonic_seconds"]
        self.assertEqual(len(ticks),2)
        self.assertGreaterEqual(ticks[1]-ticks[0],2.0)
        self.assertEqual(result["network_requests"],0)
    def test_previous_run_cannot_revisit_attempted_url(self):
        self.run_case(parsers={"PC":good,"SP":bad})
        with self.assertRaisesRegex(Blocked,"url_already_reserved_in_global_ledger"):
            self.run_case(folder=self.root/"another",parsers={"PC":good,"SP":bad})
if __name__=="__main__":
    unittest.main()
