"""Regression: each G06 race uses its fresh current time, never batch-start time."""
import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_g06_all12_capture import run_twelve
from diagnostics.kyoto_shared_capture_reservation import SharedLedger
from tests.test_kyoto_g06_full_twelve_reparse_e2e import records, capture_mock

class Tests(unittest.TestCase):
    def test_late_race_refreshes_timestamp_and_uses_maximum_lease(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            ledger=SharedLedger(root/'claims.sqlite')
            self.addCleanup(ledger.close)
            selected=records()
            selected={r: selected[r] if r in (10,11) else None for r in range(1,13)}
            times=iter([10000,10350])
            seen=[]
            class Coordinator:
                def claim(self,**kw):
                    seen.append((kw['claim_key'],kw['now_epoch'],kw['lease_seconds']))
                    return ledger.claim(**kw)
                def complete(self,**kw):return ledger.complete(**kw)
                def abandon(self,**kw):return ledger.abandon(**kw)
            with patch('diagnostics.kyoto_g06_all12_capture.capture_hybrid',side_effect=capture_mock):
                result=run_twelve(root/'out',records=selected,
                    authorized_live_http=True,claim_client=Coordinator(),
                    claim_slot=0,claim_owner='github_actions_owner',
                    claim_now_epoch=10000,claim_clock=lambda:next(times))
            self.assertEqual([x[1:] for x in seen],[(10000,600),(10350,600)])
            self.assertEqual(result['verified_dual_market_races'],2)

if __name__=='__main__': unittest.main()
