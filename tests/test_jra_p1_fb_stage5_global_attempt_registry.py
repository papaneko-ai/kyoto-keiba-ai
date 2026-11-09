import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from diagnostics.jra_p1_fb_stage5_global_attempt_registry import (
    Blocked, GlobalAttemptRegistry)

T=datetime(2026,11,13,1,0,tzinfo=timezone.utc)
CUTOFF=datetime(2026,11,14,0,0,tzinfo=timezone.utc)
RACE="2026-11-14_KYOTO_11R"
SHA="a"*64
def url(i,channel="PC"):
    host="jra.jp" if channel=="PC" else "sp.jra.jp"
    token="pw" if channel=="PC" else "sj"
    return f"https://{host}/JRADB/accessU.html?CNAME={token}01dud002020103876/{i:02d}"

def _other_process_reserve(path):
    db=GlobalAttemptRegistry(path,max_attempts=4)
    try:
        db.reserve(channel="PC",url=url(1),race_key=RACE,horse_number=1,
                   roster_sha=SHA,now=T,cutoff=CUTOFF,official_roster_observed=True)
        return "ok"
    except Blocked:
        return "blocked"

class GlobalAttemptRegistryTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.path=Path(self.t.name)/"attempts.sqlite"
        self.store=GlobalAttemptRegistry(self.path,max_attempts=4)
    def reserve(self,i=1,*,when=T,channel="PC",**kwargs):
        args=dict(channel=channel,url=url(i,channel),race_key=RACE,
                  horse_number=i,roster_sha=SHA,now=when,cutoff=CUTOFF,
                  official_roster_observed=True)
        args.update(kwargs)
        return self.store.reserve(**args)

    def test_one_reservation_and_persistent_reload(self):
        rid=self.reserve()
        other=GlobalAttemptRegistry(self.path,max_attempts=4)
        self.assertEqual(len(other.inventory()),1)
        self.assertEqual(other.unresolved()[0]["state"],"RESERVED")
        other.attach_receipt(attempt_id=rid,detail="HTTP_FAILED")
        self.assertEqual(len(self.store.unresolved()),0)
        with self.assertRaisesRegex(Blocked,"attempt_missing_or_receipt_already_recorded"):
            other.attach_receipt(attempt_id=rid,detail="second")

    def test_duplicate_globally_even_after_receipt(self):
        r=self.reserve()
        self.store.attach_receipt(attempt_id=r,detail="parser_error")
        with self.assertRaisesRegex(Blocked,"url_already_attempted_globally"):
            self.reserve(1,when=T+timedelta(seconds=5))

    def test_other_channel_is_allowed_after_gap_but_not_automatically_authorized(self):
        self.reserve()
        self.reserve(1,channel="SP",when=T+timedelta(seconds=2))
        self.assertEqual([x["channel"] for x in self.store.inventory()],["PC","SP"])

    def test_same_channel_different_url_same_horse_blocked(self):
        self.reserve()
        with self.assertRaisesRegex(Blocked,"same_horse_channel_already_consumed"):
            self.reserve(1,when=T+timedelta(seconds=3),url=url(9))

    def test_rate_interval_and_backward_clock(self):
        self.reserve()
        with self.assertRaisesRegex(Blocked,"global_gap_or_clock_rollback"):
            self.reserve(2,when=T+timedelta(seconds=1))
        with self.assertRaisesRegex(Blocked,"global_gap_or_clock_rollback"):
            self.reserve(2,when=T-timedelta(seconds=1))
        self.assertEqual(len(self.store.inventory()),1)

    def test_budget(self):
        for i in range(1,5):
            self.reserve(i,when=T+timedelta(seconds=i*2))
        with self.assertRaisesRegex(Blocked,"global_request_budget_exhausted"):
            self.reserve(5,when=T+timedelta(seconds=20))

    def test_cutoff_and_untrusted_clock(self):
        with self.assertRaisesRegex(Blocked,"prediction_cutoff_passed"):
            self.reserve(1,when=CUTOFF)
        with self.assertRaisesRegex(Blocked,"naive_or_missing_clock"):
            self.reserve(1,when=datetime(2026,11,13))

    def test_invalid_endpoint_and_nonobserved_link(self):
        with self.assertRaisesRegex(Blocked,"untrusted_official_url_or_roster"):
            self.reserve(url="https://example.com/fake")
        with self.assertRaisesRegex(Blocked,"missing_new_official_roster_evidence"):
            self.reserve(official_roster_observed=False)

    def test_bad_race_key(self):
        with self.assertRaisesRegex(Blocked,"invalid_race_key"):
            self.reserve(race_key="2026-11-14_KYOTO_99R_WRONG")

    def test_thread_concurrency_allows_only_one_url(self):
        def worker(_):
            try:
                return ("ok",self.reserve())
            except Blocked as e:
                return ("blocked",str(e))
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(worker,range(8)))
        self.assertEqual(sum(x[0]=="ok" for x in results),1)
        self.assertEqual(len(self.store.inventory()),1)


    def test_independent_processes_compete_on_same_global_url(self):
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=4) as pool:
            outcomes=list(pool.map(_other_process_reserve,[str(self.path)]*4))
        self.assertEqual(outcomes.count("ok"),1)
        self.assertEqual(outcomes.count("blocked"),3)
        self.assertEqual(len(self.store.inventory()),1)

    def test_crash_like_unresolved_reservation_not_released(self):
        self.reserve()
        reloaded=GlobalAttemptRegistry(self.path,max_attempts=4)
        self.assertEqual(len(reloaded.unresolved()),1)
        with self.assertRaisesRegex(Blocked,"url_already_attempted_globally"):
            reloaded.reserve(channel="PC",url=url(1),race_key=RACE,
                horse_number=1,roster_sha=SHA,now=T+timedelta(seconds=5),
                cutoff=CUTOFF,official_roster_observed=True)

    def test_rejected_attempt_does_not_consume_budget(self):
        with self.assertRaises(Blocked):
            self.reserve(1,official_roster_observed=False)
        self.assertEqual(self.store.inventory(),[])

    def test_no_recovery_can_rewrite_success(self):
        rid=self.reserve()
        self.store.attach_receipt(attempt_id=rid,detail="VALIDATED")
        with self.assertRaisesRegex(Blocked,"attempt_missing_or_receipt_already_recorded"):
            self.store.attach_receipt(attempt_id=rid,detail="FAILED")

if __name__=="__main__":
    unittest.main()
