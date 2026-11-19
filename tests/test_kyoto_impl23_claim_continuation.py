"""Evidence: a remote coordinator failure affects only its race, not the next one."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from diagnostics.kyoto_g06_all12_capture import run_twelve
from diagnostics.kyoto_shared_capture_reservation import SharedLedger
from tests.test_kyoto_g06_full_twelve_reparse_e2e import records, capture_mock

class Tests(unittest.TestCase):
    def test_unconfirmed_race_does_not_prevent_next_race_real_collector_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            ledger=SharedLedger(path/'ledger.sqlite')
            self.addCleanup(ledger.close)
            selected=records()
            selected={r:selected[r] if r in (10,11) else None for r in range(1,13)}
            captured=[]
            class Intermittent:
                def claim(self,**kw):
                    if ':10:' in kw['claim_key']:
                        raise ConnectionError('synthetic uncertain coordinator response')
                    return ledger.claim(**kw)
                def complete(self,**kw):
                    return ledger.complete(**kw)
                def abandon(self,**kw):
                    return ledger.abandon(**kw)
            def collector(out,**kwargs):
                captured.append(kwargs['race_spec'].race_number)
                return capture_mock(out,**kwargs)
            with patch('diagnostics.kyoto_g06_all12_capture.capture_hybrid',side_effect=collector):
                result=run_twelve(path/'capture',records=selected,authorized_live_http=True,
                    claim_client=Intermittent(),claim_slot=0,
                    claim_owner='github_actions_12345',claim_now_epoch=10000)
            self.assertEqual(result['records'][9]['claim_state'],'COORDINATOR_UNCONFIRMED')
            self.assertEqual(result['records'][9]['state'],'INPUT_OR_CAPTURE_REJECTED')
            self.assertEqual(result['records'][10]['claim_commit_state'],'COMMITTED')
            self.assertEqual(captured,[11])
            self.assertEqual(result['verified_dual_market_races'],1)
            self.assertTrue((path/'capture'/'g06_batch_receipt.json').is_file())

if __name__=='__main__':unittest.main()
