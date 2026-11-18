import json,tempfile,unittest
from hashlib import sha256
from pathlib import Path
from diagnostics.kyoto_g03_to_g06_input_adapter import records_from_g03
from diagnostics.jra_market_source_chain import SourceChainError
from tests.test_kyoto_g06_all12_capture import spec as test_spec
DAY="20261121"
RAW=b"OFFLINE_G03_ORIGINAL_R11"
def build(root,*,tamper=False,missing=False):
    root.mkdir()
    source=test_spec(11).pc_racecard_url
    row={"state":"ROSTER_AND_START_VERIFIED_OFFLINE",
         "original_file":"official_racecard_11.html",
         "source_url":source,"original_sha256":sha256(RAW).hexdigest(),
         "start_time_jst":"15:45","captured_at_utc":"2026-11-21T00:10:00Z",
         "runners":[{"number":i,"frame":i,"name":f"Horse{i}"} for i in range(1,7)]}
    races={str(i):{"state":"OFFICIAL_LINK_NOT_OBSERVED"} for i in range(1,13)}
    if not missing:races["11"]=row
    (root/"g03_official_racecard_11.html").write_bytes(b"altered" if tamper else RAW)
    (root/"g03_receipt.json").write_text(json.dumps({
        "schema":"kyoto_g03_all_races.v1","day":DAY,"races":races}))
class Tests(unittest.TestCase):
    def test_saved_official_g03_source_is_executable_g06_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"source";build(root)
            records=records_from_g03(root,day=DAY)
            self.assertEqual(set(records),set(range(1,13)))
            self.assertEqual(sum(x is not None for x in records.values()),1)
            self.assertEqual(records[11]["race_spec"].pc_racecard_url,test_spec(11).pc_racecard_url)
            self.assertEqual(records[11]["race_spec"].sp_racecard_url,"")
            self.assertEqual(records[11]["active_runners"][0],(1,1))
            self.assertEqual(records[11]["verified_start_utc"],"2026-11-21T06:45:00+00:00")
    def test_tampered_g03_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"source";build(root,tamper=True)
            with self.assertRaisesRegex(SourceChainError,"sha_mismatch"):
                records_from_g03(root,day=DAY)
    def test_missing_g03_slot_keeps_other_races_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"source";build(root,missing=True)
            out=records_from_g03(root,day=DAY)
            self.assertTrue(all(x is None for x in out.values()))
    def test_wrong_day_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"source";build(root)
            with self.assertRaises(SourceChainError):records_from_g03(root,day="20261122")
    def test_wrong_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"source";build(root)
            file=root/"g03_receipt.json"
            data=json.loads(file.read_text())
            data["races"]["11"]["original_file"]="unsafe.html"
            file.write_text(json.dumps(data))
            with self.assertRaisesRegex(SourceChainError,"filename"):
                records_from_g03(root,day=DAY)
if __name__=="__main__":unittest.main()
