"""Four stage inboxes are transferred, hashed and never claim predictions."""
import json
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_g06_all12_capture import run_twelve
from diagnostics.kyoto_g06_downstream_intake import prepare_intake
from diagnostics.kyoto_g06_four_stage_inboxes import read_inboxes,NAMES
from diagnostics.jra_one_shot_market_capture import DEFAULT_RACE_SPEC
from diagnostics.jra_market_source_chain import SourceChainError
from tests.test_kyoto_g06_item_level_recovery import setup,RUNNERS,START
def records():
    x={i:None for i in range(1,13)}
    x[11]={"race_spec":DEFAULT_RACE_SPEC,"verified_start_utc":START,
           "active_runners":RUNNERS,"primary_channel":"PC",
           "expected_named_runners":tuple((n,f,"馬"+str(n)) for n,f in RUNNERS)}
    return x
def capture(out,**kw):
    setup(out,"PC",["quinella"])
    setup(out,"SP",["bracket_quinella"])
    return {"state":"SAFE_STOP","selected_channel":None}
class InboxTests(unittest.TestCase):
    def test_four_stage_receiver_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"batch"
            run_twelve(root,records=records(),runner=capture)
            received=prepare_intake(root,records=records())
            inbox=read_inboxes(root)
            self.assertEqual(set(inbox),set(NAMES))
            self.assertEqual(received["paired_source_races"],1)
            self.assertEqual(len(inbox["G07"]["races"][10]["payload"]["horses"]),6)
            self.assertEqual(len(inbox["P4"]["races"][10]["payload"]["markets"]),2)
            self.assertEqual(inbox["P5"]["races"][10]["state"],"WAIT_CALIBRATED_MODEL_AND_P4")
            self.assertEqual(inbox["P6"]["races"][10]["state"],"WAIT_PRE_RESULT_FROZEN_P5")
            self.assertFalse(any(inbox[k]["prediction_or_trade_authorized"] for k in NAMES))
            self.assertTrue(received["four_stage_handoff_manifest_sha256"])
    def test_tampered_p4_inbox_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"batch"
            run_twelve(root,records=records(),runner=capture)
            prepare_intake(root,records=records())
            (root/"next_stage_inboxes"/NAMES["P4"]).write_text("{}")
            with self.assertRaisesRegex(SourceChainError,"tampered"):
                read_inboxes(root)
    def test_cannot_overwrite_existing_stage_inboxes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"batch"
            run_twelve(root,records=records(),runner=capture)
            prepare_intake(root,records=records())
            with self.assertRaisesRegex(SourceChainError,"already_published"):
                prepare_intake(root,records=records())
    def test_missing_market_stays_missing_for_p4_but_keeps_g07(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"batch"
            run_twelve(root,records=records(),runner=capture)
            (root/"r11"/"sp"/"bracket_quinella_original.html").write_bytes(b"corrupted")
            prepare_intake(root,records=records())
            inbox=read_inboxes(root)
            self.assertEqual(set(inbox["P4"]["races"][10]["payload"]["markets"]),{"quinella"})
            self.assertEqual(inbox["P4"]["races"][10]["state"],"WAIT_PAIR_MARKETS")
            self.assertEqual(len(inbox["G07"]["races"][10]["payload"]["horses"]),6)
if __name__=="__main__":unittest.main()
