"""Run: python -m unittest discover -s tests -p 'test_scheduler_core.py' -v"""
import unittest
from datetime import datetime, timedelta, timezone
from diagnostics.scheduler_core import GateError, RaceJob, Stage, advance, dry_run, job_key

UTC = timezone.utc
START = datetime(2026, 11, 7, 6, 0, tzinfo=UTC)
NOW = START - timedelta(minutes=30)
RACE = "20261107:KYOTO:01:01:01"

def prepare():
    job = RaceJob(RACE, START)
    for stage, token in [(Stage.ENTRIES_READY, "entries_verified"),
                         (Stage.DRAW_READY, "draw_verified"),
                         (Stage.PRE_RACE_INPUT_READY, "prerace_inputs_verified")]:
        job = advance(job, stage, {token: True}, NOW)
    return job

def freeze(job, at=NOW, fetched=None):
    return advance(job, Stage.PREDICTION_FROZEN,
                   {"prediction_receipt": "receipt-0001", "model_sha256": "a"*64,
                    "source_fetched_at_utc": fetched or NOW-timedelta(minutes=1)}, at)

class SchedulerTests(unittest.TestCase):
    def test_success_and_duplicate(self):
        job = prepare()
        frozen = freeze(job)
        self.assertEqual(freeze(job), frozen)
        self.assertEqual(advance(frozen, Stage.PREDICTION_FROZEN, {}, NOW), frozen)
        result = advance(frozen, Stage.OFFICIAL_RESULT_READY,
                         {"official_result_verified": True, "payout_finalized": True}, START+timedelta(minutes=12))
        scored = advance(result, Stage.SCORED, {"score_receipt": "hash"}, START+timedelta(minutes=13))
        self.assertEqual(scored.stage, Stage.SCORED)

    def test_missing_gate_and_skip(self):
        with self.assertRaises(GateError):
            advance(RaceJob(RACE, START), Stage.DRAW_READY, {"draw_verified": True}, NOW)
        with self.assertRaises(GateError):
            advance(RaceJob(RACE, START), Stage.ENTRIES_READY, {}, NOW)

    def test_late_freeze(self):
        with self.assertRaisesRegex(GateError, "deadline"):
            freeze(prepare(), at=START-timedelta(minutes=9))

    def test_future_data(self):
        with self.assertRaisesRegex(GateError, "future_or_late"):
            freeze(prepare(), fetched=START-timedelta(minutes=5))

    def test_delayed_start_never_extends_original_deadline(self):
        with self.assertRaisesRegex(GateError, "deadline"):
            advance(prepare(), Stage.PREDICTION_FROZEN,
                    {"prediction_receipt":"receipt-0001","model_sha256":"a"*64,
                     "source_fetched_at_utc":NOW}, START-timedelta(minutes=9),
                    confirmed_start_utc=START+timedelta(minutes=30))

    def test_earlier_start_shortens_deadline(self):
        with self.assertRaisesRegex(GateError, "deadline"):
            advance(prepare(), Stage.PREDICTION_FROZEN,
                    {"prediction_receipt":"receipt-0001","model_sha256":"a"*64,
                     "source_fetched_at_utc":NOW}, START-timedelta(minutes=25),
                    confirmed_start_utc=START-timedelta(minutes=20))

    def test_result_not_final(self):
        with self.assertRaisesRegex(GateError, "payout"):
            advance(freeze(prepare()), Stage.OFFICIAL_RESULT_READY,
                    {"official_result_verified":True}, START+timedelta(minutes=10))

    def test_no_backdated_or_naive_clock(self):
        with self.assertRaisesRegex(GateError, "timezone"):
            freeze(prepare(), at=datetime(2026,11,7,5,30))

    def test_offline_replay_resume(self):
        job, audit = dry_run([
            {"stage":Stage.ENTRIES_READY,"evidence":{"entries_verified":True},"at":NOW},
            {"stage":Stage.ENTRIES_READY,"evidence":{},"at":NOW},
            {"stage":Stage.DRAW_READY,"evidence":{"draw_verified":True},"at":NOW}
        ], RaceJob(RACE,START))
        self.assertEqual(job.stage, Stage.DRAW_READY)
        self.assertEqual([r["status"] for r in audit],["accepted","duplicate","accepted"])

    def test_keys(self):
        self.assertEqual(job_key(RACE, Stage.SCORED, "final", "v1").count("|"),3)

if __name__ == "__main__":
    unittest.main()
