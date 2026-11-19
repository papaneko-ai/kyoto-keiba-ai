"""No write and no JRA requests in manual diagnostic, including failures."""
import tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_impl23_claim_preflight import manual_read_only,CONFIRM
from diagnostics.kyoto_turso_capture_claims import TursoCaptureClaims
from diagnostics.kyoto_shared_capture_reservation import ReservationError
from tests.test_kyoto_turso_capture_claims import FakeRemote,URL,TOKEN
HOST='kyoto-ai-test-fixture.turso.io'

def env(active='YES'):
    return {'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ID':'444555333',
    'KYOTO_READONLY_PROBE_CONFIRMATION':CONFIRM,
    'KYOTO_SHARED_CLAIM_ACTIVATE':active,'KYOTO_SHARED_CLAIM_TARGET':'PRODUCTION',
    'KYOTO_SHARED_CLAIM_PRODUCTION_APPROVED':'YES',
    'KYOTO_SHARED_CLAIM_APPROVED_PRODUCTION_HOST':HOST,
    'KYOTO_SHARED_CLAIM_TURSO_URL':'libsql://'+HOST,
    'KYOTO_SHARED_CLAIM_TURSO_TOKEN':TOKEN}
class Tests(unittest.TestCase):
    def test_disabled_never_uses_network(self):
        r=manual_read_only('20261121',environ=env('NO'))
        self.assertFalse(r['remote_schema_verified'])
    def test_exact_confirmation_required(self):
        e=env();e['KYOTO_READONLY_PROBE_CONFIRMATION']='WRONG'
        with self.assertRaises(ReservationError):manual_read_only('20261121',environ=e)
    def test_schedule_cannot_use_manual_probe(self):
        e=env();e['GITHUB_EVENT_NAME']='schedule'
        with self.assertRaises(ReservationError):manual_read_only('20261121',environ=e)
    def test_read_only_remote_table_for_both_days(self):
        with tempfile.TemporaryDirectory() as p:
            remote=FakeRemote(Path(p)/'store.sqlite')
            cli=TursoCaptureClaims(url=URL,token=TOKEN,transport=remote)
            cli.prepare_schema()
            before=len(remote.history)
            for day in ('20261121','20261122'):
                result=manual_read_only(day,environ=env(),transport=remote,now_epoch=10000)
                self.assertTrue(result['remote_schema_verified'])
                self.assertFalse(result['remote_write_verified'])
                self.assertFalse(result['real_scheduled_slot_proven'])
                self.assertFalse(result['production_claim_certified'])
            statements=[v['requests'][0]['stmt']['sql'].lstrip().upper()
                        for v in remote.history[before:]]
            self.assertEqual(len(statements),2)
            self.assertTrue(all(v.startswith('SELECT ') for v in statements))
if __name__=='__main__':unittest.main()
