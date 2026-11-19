"""Offline production coordinator activation safety checks: no Turso writes."""
import unittest
from diagnostics.kyoto_weekend_remote_claim_runtime import active_claims_for_weekend
from diagnostics.kyoto_turso_isolated_virtual_store import EXPECTED_HOST
from diagnostics.kyoto_shared_capture_reservation import ReservationError

PROD="kyoto-claims-prod.example.turso.io"
class NoNetwork:
    def post(self,**kwargs):
        raise AssertionError("unexpected network access")

def environment():
    return {
      "KYOTO_SHARED_CLAIM_ACTIVATE":"YES",
      "KYOTO_SHARED_CLAIM_TARGET":"PRODUCTION",
      "KYOTO_SHARED_CLAIM_PRODUCTION_APPROVED":"YES",
      "KYOTO_SHARED_CLAIM_APPROVED_PRODUCTION_HOST":PROD,
      "KYOTO_SHARED_CLAIM_TURSO_URL":"libsql://"+PROD,
      "KYOTO_SHARED_CLAIM_TURSO_TOKEN":"synthetic_no_live_secret",
      "GITHUB_EVENT_NAME":"schedule",
      "GITHUB_EVENT_SCHEDULE":"15 0 21 11 *",
      "GITHUB_RUN_ID":"44444444000",
      "GITHUB_JOB":"pc-originals-independent",
    }

class Tests(unittest.TestCase):
    def test_production_mode_requires_independent_approval(self):
        env=environment()
        del env["KYOTO_SHARED_CLAIM_PRODUCTION_APPROVED"]
        with self.assertRaisesRegex(ReservationError,"approval_required"):
            active_claims_for_weekend("20261121",environ=env,transport=NoNetwork())
    def test_production_mode_never_uses_lab_database(self):
        env=environment()
        env["KYOTO_SHARED_CLAIM_APPROVED_PRODUCTION_HOST"]=EXPECTED_HOST
        env["KYOTO_SHARED_CLAIM_TURSO_URL"]="libsql://"+EXPECTED_HOST
        with self.assertRaisesRegex(ReservationError,"host_not_approved"):
            active_claims_for_weekend("20261121",environ=env,transport=NoNetwork())
    def test_production_mode_requires_host_match(self):
        env=environment()
        env["KYOTO_SHARED_CLAIM_TURSO_URL"]="libsql://other-prod.turso.io"
        with self.assertRaisesRegex(ReservationError,"target_mismatch"):
            active_claims_for_weekend("20261121",environ=env,transport=NoNetwork())
    def test_production_mode_returns_g06_runtime_context_without_io(self):
        env=environment()
        ctx=active_claims_for_weekend("20261121",environ=env,
                                      transport=NoNetwork(),now_epoch=12345)
        self.assertTrue(ctx["enabled"])
        self.assertEqual(ctx["claim_slot"],0)
        self.assertEqual(ctx["claim_now_epoch"],12345)
        self.assertEqual(ctx["claim_client"].endpoint,"https://"+PROD+"/v2/pipeline")
        self.assertNotIn(env["KYOTO_SHARED_CLAIM_TURSO_TOKEN"],repr(ctx))
    def test_target_typo_is_rejected(self):
        env=environment()
        env["KYOTO_SHARED_CLAIM_TARGET"]="PROD"
        with self.assertRaisesRegex(ReservationError,"target_invalid"):
            active_claims_for_weekend("20261121",environ=env,transport=NoNetwork())
    def test_unactivated_production_does_not_block_capture(self):
        env=environment()
        del env["KYOTO_SHARED_CLAIM_ACTIVATE"]
        self.assertFalse(active_claims_for_weekend("20261121",environ=env)["enabled"])

if __name__=="__main__":unittest.main()
