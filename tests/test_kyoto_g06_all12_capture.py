import json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from hashlib import sha256
from diagnostics.jra_one_shot_market_capture import ObservedRaceSpec
from diagnostics.kyoto_g06_all12_capture import run_twelve
from diagnostics.jra_market_integrity_gate import normal_sales_open
from datetime import date

DAY="20261121"
def spec(r):
    # Test-only observed-token *shapes*; never passed to live HTTP.
    pc=f"https://jra.jp/JRADB/accessD.html?CNAME=pw01dde010820260501{r:02d}{DAY}%2FAB"
    return ObservedRaceSpec(DAY,r,f"2026-11-21_KYOTO_{r}R","京都",pc,"",
             normal_sales_open(date(2026,11,21)).isoformat())
def slot(r):
    return {"race_spec":spec(r),"verified_start_utc":"2026-11-21T05:00:00Z",
        "active_runners":((1,1),(2,2)),
        "expected_named_runners":((1,1,"馬A"),(2,2,"馬B")),
        "primary_channel":"PC"}
def samples():
    return {r:slot(r) for r in range(1,13)}
def mock_collector(out,*,primary_channel,race_spec,**kwargs):
    folder=Path(out)/"pc";folder.mkdir(parents=True)
    data={}
    steps=[]
    for k in ("odds_menu","quinella","bracket_quinella"):
        name={"odds_menu":"official_odds_menu.html",
              "quinella":"quinella_original.html","bracket_quinella":"bracket_quinella_original.html"}[k]
        raw=(f"<html>{race_spec.race_number}-{k}</html>").encode()
        (folder/name).write_bytes(raw)
        data[k]=raw
        steps.append({"step":k,"bytes":len(raw),"sha256":sha256(raw).hexdigest(),
                      "captured_at_utc":"2026-11-21T01:00:00Z"})
    receipt={"state":"SOURCE_FROZEN","pre_race_prices_accepted":True,"request_receipts":steps}
    (folder/"receipt.json").write_text(json.dumps(receipt))
    return {"state":"SOURCE_ONLY_PRIMARY","selected_channel":"PC"}
class Tests(unittest.TestCase):
    def test_twelve_races_verified_originals_not_model_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            got=run_twelve(Path(tmp)/"proof",records=samples(),runner=mock_collector)
            self.assertEqual(got["verified_dual_market_races"],12)
            self.assertFalse(got["g06_certified"])
            self.assertFalse(got["prediction_ready"])
            self.assertTrue((Path(tmp)/"proof"/"g06_batch_receipt.json").is_file())
    def test_missing_observed_link_does_not_abort_other_races(self):
        records=samples();records[4]=None
        with tempfile.TemporaryDirectory() as tmp:
            got=run_twelve(Path(tmp)/"proof",records=records,runner=mock_collector)
            self.assertEqual(got["verified_dual_market_races"],11)
            self.assertEqual(got["unobserved_link_races"],1)
    def test_cross_race_spec_blocked_without_aborting(self):
        records=samples();records[2]["race_spec"]=spec(3)
        with tempfile.TemporaryDirectory() as tmp:
            got=run_twelve(Path(tmp)/"proof",records=records,runner=mock_collector)
            self.assertEqual(got["verified_dual_market_races"],11)
            self.assertEqual(got["records"][1]["state"],"INPUT_OR_CAPTURE_REJECTED")
    def test_no_partial_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"proof";p.mkdir()
            with self.assertRaises(ValueError):
                run_twelve(p,records=samples(),runner=mock_collector)
    def test_no_missing_slots_silently_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                run_twelve(Path(tmp)/"proof",records={1:slot(1)},runner=mock_collector)
    def test_original_mismatch_is_detected(self):
        def corrupt(out,**kwargs):
            x=mock_collector(out,**kwargs)
            (Path(out)/"pc"/"quinella_original.html").write_bytes(b"tampered")
            return x
        with tempfile.TemporaryDirectory() as tmp:
            got=run_twelve(Path(tmp)/"proof",records=samples(),runner=corrupt)
            self.assertEqual(got["verified_dual_market_races"],0)
            self.assertTrue(all(x["evidence_check"]["state"]=="ORIGINAL_RECEIPT_MISMATCH"
                                for x in got["records"]))
if __name__=="__main__":unittest.main()
