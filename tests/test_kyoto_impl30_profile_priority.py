import unittest
from datetime import datetime,timezone,timedelta
from diagnostics.kyoto_impl30_profile_priority import profile_deadline,MARKET_RESERVE_SECONDS

class PriorityTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,28,0,15,tzinfo=timezone.utc)

    def plan(self, offsets, *, original=1600):
        records={r:{"verified_start_utc":(self.now+timedelta(seconds=delta)).isoformat()}
                 for r,delta in offsets.items()}
        return profile_deadline(records,wall_utc=self.now,mono_now=1000,original_deadline=original)

    def test_near_market_yields_profile_budget(self):
        p=self.plan({1:720,2:1500})
        self.assertEqual(p["deadline_monotonic"],1000)
        self.assertEqual(p["earliest_race"],1)
        self.assertEqual(p["reason"],"MARKET_CUTOFF_PRIORITY")

    def test_far_market_retains_existing_cap(self):
        p=self.plan({1:2400})
        self.assertEqual(p["deadline_monotonic"],1600)

    def test_expired_market_does_not_steal_later_race_budget(self):
        p=self.plan({1:120,3:1000,2:500})
        self.assertEqual(p["earliest_race"],3)
        self.assertEqual(p["deadline_monotonic"],1000+400-MARKET_RESERVE_SECONDS)

    def test_none_available_preserves_profile_opportunity(self):
        self.assertEqual(self.plan({1:0})["deadline_monotonic"],1600)

    def test_never_extends_existing_cap(self):
        self.assertEqual(self.plan({2:900},original=980)["deadline_monotonic"],980)

    def test_naive_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            profile_deadline({1:{"verified_start_utc":"2026-11-28T01:00:00"}},
                             wall_utc=self.now,mono_now=1000,original_deadline=1600)

if __name__=="__main__":unittest.main()
