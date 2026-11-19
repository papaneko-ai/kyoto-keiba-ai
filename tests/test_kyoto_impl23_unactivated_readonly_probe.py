"""Proof that disabled production capture still permits a separate SELECT-only probe."""
import tempfile, unittest
from pathlib import Path
from diagnostics.kyoto_impl23_unactivated_readonly_probe import probe,CONFIRM
from diagnostics.kyoto_turso_capture_claims import TursoCaptureClaims
from diagnostics.kyoto_shared_capture_reservation import ReservationError
from tests.test_kyoto_turso_capture_claims import FakeRemote,URL,TOKEN
HOST='kyoto-ai-test-fixture.turso.io'

def env():
    return {'GITHUB_EVENT_NAME':'workflow_dispatch','KYOTO_READONLY_PROBE_CONFIRMATION':CONFIRM,
            'KYOTO_SHARED_CLAIM_ACTIVATE':'NO',
            'KYOTO_SHARED_CLAIM_APPROVED_PRODUCTION_HOST':HOST,
            'KYOTO_SHARED_CLAIM_TURSO_URL':'libsql://'+HOST,
            'KYOTO_SHARED_CLAIM_TURSO_TOKEN':TOKEN}
class Tests(unittest.TestCase):
    def test_missing_configuration_reported_without_network_or_secret_value(self):
        e=env()
        e.pop('KYOTO_SHARED_CLAIM_TURSO_TOKEN')
        result=probe('20261121',environ=e)
        self.assertEqual(result['status'],'READ_ONLY_CONFIGURATION_INCOMPLETE_NO_REMOTE_IO')
        self.assertEqual(result['missing_variable_names'],['KYOTO_SHARED_CLAIM_TURSO_TOKEN'])
        self.assertNotIn(TOKEN,str(result))
    def test_wrong_event_and_confirmation_rejected(self):
        e=env()
        e['GITHUB_EVENT_NAME']='schedule'
        with self.assertRaises(ReservationError):probe('20261121',environ=e)
        e=env()
        e['KYOTO_READONLY_PROBE_CONFIRMATION']='WRONG'
        with self.assertRaises(ReservationError):probe('20261121',environ=e)
    def test_disabled_capture_can_run_select_only(self):
        with tempfile.TemporaryDirectory() as path:
            remote=FakeRemote(Path(path)/'test.sqlite')
            client=TursoCaptureClaims(url=URL,token=TOKEN,transport=remote)
            client.prepare_schema()
            before=len(remote.history)
            for day in ('20261121','20261122'):
                e=env()
                result=probe(day,environ=e,transport=remote)
                self.assertTrue(result['remote_schema_verified'])
                self.assertFalse(result['remote_write_verified'])
                self.assertFalse(result['production_claim_certified'])
                self.assertTrue(result['capture_activation_unchanged'])
                self.assertEqual(e['KYOTO_SHARED_CLAIM_ACTIVATE'],'NO')
            statements=[req['requests'][0]['stmt']['sql'].strip().upper()
                        for req in remote.history[before:]]
            self.assertEqual(len(statements),2)
            self.assertTrue(all(sql.startswith('SELECT ') for sql in statements))
    def test_wrong_host_rejected_without_network(self):
        e=env()
        e['KYOTO_SHARED_CLAIM_APPROVED_PRODUCTION_HOST']='other.turso.io'
        with self.assertRaises(ReservationError):probe('20261121',environ=e)
if __name__=='__main__':unittest.main()
