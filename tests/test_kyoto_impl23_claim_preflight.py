"""Offline preflight refuses to mistake read access for production write proof."""
import tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_impl23_claim_preflight import check
from diagnostics.kyoto_shared_capture_reservation import key
from tests.test_kyoto_turso_capture_claims import FakeRemote,TOKEN
HOST='kyoto-ai-test-fixture.turso.io'
class Tests(unittest.TestCase):
    def env(self):
        return {'KYOTO_SHARED_CLAIM_ACTIVATE':'YES','KYOTO_SHARED_CLAIM_TARGET':'PRODUCTION',
                'KYOTO_SHARED_CLAIM_PRODUCTION_APPROVED':'YES',
                'KYOTO_SHARED_CLAIM_APPROVED_PRODUCTION_HOST':HOST,
                'KYOTO_SHARED_CLAIM_TURSO_URL':'libsql://'+HOST,
                'KYOTO_SHARED_CLAIM_TURSO_TOKEN':TOKEN,
                'GITHUB_EVENT_NAME':'schedule','GITHUB_EVENT_SCHEDULE':'15 0 21 11 *',
                'GITHUB_RUN_ID':'444555333','GITHUB_JOB':'pc-originals-independent'}
    def test_inactive_never_accesses_database(self):
        env=self.env();env['KYOTO_SHARED_CLAIM_ACTIVATE']='NO'
        a=check('20261121',environ=env)
        self.assertEqual(a['status'],'COORDINATOR_INACTIVE_EXISTING_CAPTURE_PRESERVED')
    def test_missing_schema_blocks_before_jra_http(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(Exception):
                check('20261121',environ=self.env(),
                      transport=FakeRemote(Path(root)/'remote.sqlite'))
    def test_existing_schema_read_only_pass_is_not_write_certification(self):
        from diagnostics.kyoto_turso_capture_claims import TursoCaptureClaims
        with tempfile.TemporaryDirectory() as root:
            transport=FakeRemote(Path(root)/'remote.sqlite')
            client=TursoCaptureClaims(url='libsql://'+HOST,token=TOKEN,transport=transport)
            client.prepare_schema()
            result=check('20261121',environ=self.env(),transport=transport)
            self.assertTrue(result['remote_schema_verified'])
            self.assertFalse(result['remote_write_verified'])
            self.assertFalse(result['production_claim_certified'])
            self.assertIsNone(client.observe(key(day='20261121',slot=0,race=1,channel='PC',market='racecard')))
if __name__=='__main__':unittest.main()
