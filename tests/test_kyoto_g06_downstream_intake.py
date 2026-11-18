"""Downstream contract uses actual source bytes, not asserted success flags."""
import json
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_g06_all12_capture import run_twelve
from diagnostics.kyoto_g06_downstream_intake import prepare_intake
from diagnostics.jra_one_shot_market_capture import DEFAULT_RACE_SPEC
from tests.test_kyoto_g06_item_level_recovery import setup,RUNNERS,START
from diagnostics.jra_market_source_chain import SourceChainError
def records():
    x={r:None for r in range(1,13)}
    x[11]={"race_spec":DEFAULT_RACE_SPEC,"verified_start_utc":START,
        "active_runners":RUNNERS,
        "expected_named_runners":tuple((n,f,"馬"+str(n)) for n,f in RUNNERS),
        "primary_channel":"PC"}
    return x
def dual_capture(out,**kw):
    setup(out,"PC",["quinella"])
    setup(out,"SP",["bracket_quinella"])
    return {"state":"SAFE_STOP","selected_channel":None}
class Tests(unittest.TestCase):
    def test_cross_channel_prices_reparsed_into_p4_and_g07(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"batch"
            run_twelve(root,records=records(),runner=dual_capture)
            r=prepare_intake(root,records=records())
            self.assertEqual(r["paired_source_races"],1)
            self.assertFalse(r["eligible_for_prediction"])
            row=r["races"][10]
            self.assertEqual(row["G07"]["state"],"ROSTER_IDENTITIES_STAGED_FIELDS_PENDING")
            self.assertEqual(len(row["G07"]["horses"]),6)
            self.assertEqual(row["P4"]["state"],"SOURCE_MARKETS_STAGED_AWAIT_MODEL_AND_TEMPORAL_RECHECK")
            self.assertEqual(len(row["P4"]["markets"]["quinella"]["pairs"]),15)
            self.assertEqual(len(row["P4"]["markets"]["bracket_quinella"]["pairs"]),6)
            self.assertEqual(row["P4"]["markets"]["quinella"]["channel"],"PC")
            self.assertEqual(row["P4"]["markets"]["bracket_quinella"]["channel"],"SP")
            self.assertEqual(row["P5"]["state"],"WAIT_CALIBRATED_MODEL_AND_P4")
            self.assertEqual(row["P6"]["state"],"WAIT_PRE_RESULT_FROZEN_P5")
            self.assertTrue((root/"g06_downstream_input_receipt.json").is_file())
    def test_tampered_market_is_not_used(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"batch"
            run_twelve(root,records=records(),runner=dual_capture)
            (root/"r11"/"sp"/"bracket_quinella_original.html").write_bytes(b"tampered")
            r=prepare_intake(root,records=records())
            self.assertEqual(r["paired_source_races"],0)
            self.assertEqual(r["partial_source_races"],1)
            self.assertEqual(set(r["races"][10]["P4"]["markets"]),{"quinella"})
    def test_batch_claim_alone_does_not_create_p4_data(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"batch"
            run_twelve(root,records=records(),runner=dual_capture)
            file=root/"r11"/"pc"/"receipt.json"
            data=json.loads(file.read_text());data["race_id"]="WRONG";file.write_text(json.dumps(data))
            r=prepare_intake(root,records=records())
            self.assertEqual(r["paired_source_races"],0)
    def test_unknown_race_is_explicitly_unobserved(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"batch"
            run_twelve(root,records=records(),runner=dual_capture)
            r=prepare_intake(root,records=records())
            self.assertEqual(sum(x["state"]=="OFFICIAL_LINK_UNOBSERVED" for x in r["races"]),11)
            self.assertEqual(r["races"][0]["P4"]["state"],"WAIT_PAIR_MARKETS")
    def test_missing_receipt_fails(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SourceChainError):
                prepare_intake(td,records=records())
    def test_refuses_duplicate_publication(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"batch"
            run_twelve(root,records=records(),runner=dual_capture)
            prepare_intake(root,records=records())
            with self.assertRaises(FileExistsError):
                prepare_intake(root,records=records())
if __name__=="__main__":unittest.main()
