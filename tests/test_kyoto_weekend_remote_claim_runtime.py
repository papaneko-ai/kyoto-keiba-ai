"""Runtime activation: explicitly opted-in test Turso claims, eight schedules."""
import unittest
from diagnostics.kyoto_weekend_remote_claim_runtime import (
    active_claims_for_weekend,CRON_SLOTS)
from diagnostics.kyoto_turso_isolated_virtual_store import EXPECTED_HOST
from diagnostics.kyoto_shared_capture_reservation import ReservationError
class Dummy:
    def post(self,**kwargs):raise RuntimeError("never called by activation")
def variables(day,cron):
    return {"KYOTO_SHARED_CLAIM_ACTIVATE":"YES",
            "GITHUB_EVENT_NAME":"schedule",
            "GITHUB_EVENT_SCHEDULE":cron,
            "GITHUB_RUN_ID":"44255500001",
            "GITHUB_JOB":"pc-originals-independent",
            "KYOTO_SHARED_CLAIM_TURSO_URL":"libsql://"+EXPECTED_HOST,
            "KYOTO_SHARED_CLAIM_TURSO_TOKEN":"synthetic_token_not_real_12345"}
class Tests(unittest.TestCase):
    def test_unconfigured_is_inert_for_every_observation(self):
        for day in CRON_SLOTS:
            for cron in CRON_SLOTS[day]:
                e=variables(day,cron)
                e.pop("KYOTO_SHARED_CLAIM_ACTIVATE")
                self.assertFalse(active_claims_for_weekend(day,environ=e)["enabled"])
    def test_actual_eight_slots_map_without_interfering(self):
        for day in CRON_SLOTS:
            for cron,index in CRON_SLOTS[day].items():
                with self.subTest(day=day,cron=cron):
                    res=active_claims_for_weekend(day,environ=variables(day,cron),
                           transport=Dummy(),now_epoch=10000)
                    self.assertTrue(res["enabled"])
                    self.assertEqual(res["claim_slot"],index)
                    self.assertEqual(res["claim_now_epoch"],10000)
                    self.assertNotIn("synthetic_token_not_real",str(res))
    def test_manual_dispatch_cannot_invent_schedule_slot(self):
        day="20261121";e=variables(day,next(iter(CRON_SLOTS[day])))
        e["GITHUB_EVENT_NAME"]="workflow_dispatch"
        self.assertFalse(active_claims_for_weekend(day,environ=e)["enabled"])
    def test_remote_service_must_be_isolated_test_target(self):
        day="20261121";e=variables(day,next(iter(CRON_SLOTS[day])))
        e["KYOTO_SHARED_CLAIM_TURSO_URL"]="libsql://some-prod.turso.io"
        with self.assertRaisesRegex(ReservationError,"isolated_remote"):
            active_claims_for_weekend(day,environ=e,transport=Dummy())
    def test_wrong_cron_rejected_only_when_opted_in(self):
        day="20261121";e=variables(day,"0 0 21 11 *")
        with self.assertRaisesRegex(ReservationError,"scheduled_slot"):
            active_claims_for_weekend(day,environ=e,transport=Dummy())
    def test_missing_secret_rejected_only_when_opted_in(self):
        day="20261121";e=variables(day,next(iter(CRON_SLOTS[day])))
        e.pop("KYOTO_SHARED_CLAIM_TURSO_TOKEN")
        with self.assertRaisesRegex(ReservationError,"token_missing"):
            active_claims_for_weekend(day,environ=e,transport=Dummy())
if __name__=="__main__":unittest.main()
