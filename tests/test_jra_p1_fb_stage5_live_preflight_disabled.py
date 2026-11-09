import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

from diagnostics.jra_p1_fb_stage5_global_attempt_registry import GlobalAttemptRegistry,Blocked
from diagnostics.jra_p1_fb_stage5_live_preflight_disabled import (
    RequestEvidence,strict_official_url,verify_request,
    reserve_offline_simulation,deny_network_execution,LiveNetworkDisabled)

T=datetime(2026,11,13,6,0,tzinfo=timezone.utc)
C=datetime(2026,11,14,0,0,tzinfo=timezone.utc)
URL="https://jra.jp/JRADB/accessU.html?CNAME=pw01dud002020103876/AA"
SP="https://sp.jra.jp/JRADB/accessU.html?CNAME=sj01ude002020103876/AA"
E=RequestEvidence("PC",URL,"2026-11-14_KYOTO_11R",1,"モンドプリューム","a"*64,True,C,T-timedelta(minutes=10))
class NetworkGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=GlobalAttemptRegistry(Path(self.tmp.name)/"gate.db",max_attempts=3)

    def e(self,**changes):
        from dataclasses import replace
        return replace(E,**changes)

    def test_original_official_pc_and_mobile_urls(self):
        self.assertTrue(strict_official_url("PC",URL))
        self.assertTrue(strict_official_url("SP",SP))

    def test_strict_endpoint_does_not_accept_query_injection(self):
        urls=[URL+"&CNAME=attack",URL+"&x=1",
              "https://jra.jp.evil.tld/JRADB/accessU.html?CNAME=pw01/AA",
              "http://jra.jp/JRADB/accessU.html?CNAME=pw01/AA",
              "https://jra.jp:444/JRADB/accessU.html?CNAME=pw01/AA",
              "https://evil@jra.jp/JRADB/accessU.html?CNAME=pw01/AA",
              "https://jra.jp/JRADB/accessU.html?CNAME=pw01/AA#fragment"]
        for u in urls:
            with self.subTest(u=u):
                self.assertFalse(strict_official_url("PC",u))

    def test_preflight_no_network_approval(self):
        g=verify_request(E,T)
        self.assertFalse(g["network_allowed"])
        self.assertEqual(g["actual_requests"],0)

    def test_unverified_mobile_url_refused(self):
        with self.assertRaisesRegex(Blocked,"missing_source_provenance"):
            verify_request(self.e(channel="SP",official_url=SP,roster_link_observed=False),T)

    def test_past_race_refused(self):
        with self.assertRaisesRegex(Blocked,"source_future_or_prediction_cutoff"):
            verify_request(E,datetime(2026,11,14,0,0,tzinfo=timezone.utc))

    def test_clock_rolls_before_archive(self):
        with self.assertRaisesRegex(Blocked,"source_future_or_prediction_cutoff"):
            verify_request(E,T-timedelta(hours=1))

    def test_missing_source_sha(self):
        with self.assertRaisesRegex(Blocked,"missing_source_provenance"):
            verify_request(self.e(source_roster_sha256="not-evidence"),T)

    def test_invalid_race_and_horse_number(self):
        with self.assertRaisesRegex(Blocked,"invalid_race_or_horse_identity"):
            verify_request(self.e(race_key="2026-11-14_KYOTO_99R"),T)
        with self.assertRaisesRegex(Blocked,"invalid_race_or_horse_identity"):
            verify_request(self.e(horse_number=0),T)

    def test_monotonic_elapsed_time_guard(self):
        with self.assertRaisesRegex(Blocked,"real_time_interval_not_elapsed"):
            reserve_offline_simulation(registry=self.db,evidence=E,
                clock=lambda:T,monotonic=lambda:101.0,last_call_monotonic=100.0)
        self.assertEqual(len(self.db.inventory()),0)

    def test_reservation_consumed_never_network(self):
        out=reserve_offline_simulation(registry=self.db,evidence=E,
                clock=lambda:T,monotonic=lambda:102.0,last_call_monotonic=100.0)
        self.assertFalse(out["network_allowed"])
        self.assertEqual(len(self.db.unresolved()),1)
        with self.assertRaisesRegex(Blocked,"url_already_attempted_globally"):
            reserve_offline_simulation(registry=self.db,evidence=E,
                clock=lambda:T+timedelta(seconds=3),monotonic=lambda:106,
                last_call_monotonic=102)

    def test_network_execution_always_disabled(self):
        with self.assertRaises(LiveNetworkDisabled):
            deny_network_execution(E)
        self.assertEqual(len(self.db.inventory()),0)

    def test_future_roster_uses_new_date_without_historical_hardcode(self):
        next_date=RequestEvidence("PC",URL,"2026-11-21_KYOTO_01R",1,
            "モンドプリューム","a"*64,True,
            datetime(2026,11,21,tzinfo=timezone.utc),
            datetime(2026,11,20,tzinfo=timezone.utc))
        result=verify_request(next_date,datetime(2026,11,20,1,tzinfo=timezone.utc))
        self.assertEqual(result["status"],"ELIGIBLE_FOR_OFFLINE_LEDGER_RESERVATION_ONLY")

    def test_naive_clock_rejected(self):
        with self.assertRaisesRegex(Blocked,"untrusted_wall_clock"):
            verify_request(E,datetime(2026,11,13))

if __name__=="__main__":
    unittest.main()
