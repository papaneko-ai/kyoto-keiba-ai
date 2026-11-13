import unittest
from datetime import datetime, timezone, timedelta
from diagnostics.kyoto_race_day_http_gate import require_race_day_window, DayGateRejected
Z=timezone.utc
class RaceDayGateTests(unittest.TestCase):
    def gate(self, when, race_day="20261114", **kw):
        return require_race_day_window(now=when,race_day=race_day,
            not_before_utc=datetime(2026,11,14,0,0,tzinfo=Z),
            latest_utc=datetime(2026,11,14,9,0,tzinfo=Z),
            run_attempt=kw.get("run_attempt","1"),event_name=kw.get("event_name","push"))
    def test_previous_2026_nov12_run_blocked(self):
        with self.assertRaises(DayGateRejected):
            self.gate(datetime(2026,11,12,2,34,tzinfo=Z))
    def test_start_in_kyoto_nov14(self):
        self.assertTrue(self.gate(datetime(2026,11,14,0,0,tzinfo=Z))["date_gate_passed"])
    def test_utc_end_exclusive(self):
        with self.assertRaises(DayGateRejected):self.gate(datetime(2026,11,14,9,0,tzinfo=Z))
    def test_no_cross_day_approval(self):
        with self.assertRaises(DayGateRejected):self.gate(datetime(2026,11,14,1,0,tzinfo=Z),race_day="20261115")
    def test_no_rerun(self):
        with self.assertRaises(DayGateRejected):self.gate(datetime(2026,11,14,1,0,tzinfo=Z),run_attempt="2")
    def test_invalid_event(self):
        with self.assertRaises(DayGateRejected):self.gate(datetime(2026,11,14,1,0,tzinfo=Z),event_name="pull_request")
    def test_naive_clock(self):
        with self.assertRaises(DayGateRejected):self.gate(datetime(2026,11,14,1,0))
    def test_bad_day(self):
        with self.assertRaises(DayGateRejected):self.gate(datetime(2026,11,14,1,0,tzinfo=Z),race_day="20261116")
if __name__=="__main__":unittest.main()
