"""Independent 12R G03 proof tests: synthetic originals are NOT JRA network proof."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_g03_all_races import acquire_all
from diagnostics.kyoto_g03_proof_verify import verify, G03ProofRejected
from tests.test_kyoto_g03_all_races import DAY,PARENT,meeting,card,source_race

class ReceiptProof(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)/"originals"
        self.root.mkdir()
        staging=Path(temp.name)/"staging"
        self.report=acquire_all(
            day=DAY,root=staging,meeting_raw=meeting(),meeting_url=PARENT,
            fetch=lambda url:card(3+source_race(url),race=source_race(url)),
            captured_at_utc=lambda:"2026-11-21T00:00:00Z",allowed=True)
        for p in staging.iterdir():
            p.rename(self.root/("g03_"+p.name))
        self.root.joinpath("g03_receipt.json").write_text(
            json.dumps(self.report,ensure_ascii=False),encoding="utf8")
        # The existing observer stores its meeting original at this name.
        shutil.copyfile(self.root/"g03_official_meeting.html",
                        self.root/"official_meeting.html")

    def test_all_twelve_sha_reparse_verified(self):
        result=verify(self.root,expected_day=DAY)
        self.assertTrue(result["complete_source_originals"])
        self.assertEqual(result["races_verified"],12)
        self.assertEqual(result["runner_count"],sum(3+i for i in range(1,13)))
        self.assertFalse(result["live_jra_network_observed_by_this_verifier"])
        self.assertFalse(result["prediction_ready"])

    def test_original_byte_tampering_rejected(self):
        p=self.root/"g03_official_racecard_04.html"
        p.write_bytes(p.read_bytes()+b" ")
        with self.assertRaisesRegex(G03ProofRejected,"sha_mismatch"):
            verify(self.root,expected_day=DAY)

    def test_changed_url_in_receipt_rejected(self):
        self.report["races"]["4"]["source_url"]=self.report["races"]["5"]["source_url"]
        self._write()
        with self.assertRaisesRegex(G03ProofRejected,"source_url_or_filename"):
            verify(self.root,expected_day=DAY)

    def test_forged_runner_name_rejected(self):
        self.report["races"]["2"]["runners"][0]["name"]="forged"
        self._write()
        with self.assertRaisesRegex(G03ProofRejected,"content_mismatch"):
            verify(self.root,expected_day=DAY)

    def test_partial_capture_not_certified(self):
        self.report["complete"]=False
        self.report["missing_races"]=[7]
        self._write()
        with self.assertRaisesRegex(G03ProofRejected,"partial_capture"):
            verify(self.root,expected_day=DAY)

    def test_missing_12r_original_not_certified(self):
        (self.root/"g03_official_racecard_12.html").unlink()
        with self.assertRaisesRegex(G03ProofRejected,"original_missing"):
            verify(self.root,expected_day=DAY)

    def test_wrong_day_not_certified(self):
        with self.assertRaisesRegex(G03ProofRejected,"day_mismatch"):
            verify(self.root,expected_day="20261122")

    def _write(self):
        (self.root/"g03_receipt.json").write_text(
            json.dumps(self.report,ensure_ascii=False),encoding="utf8")

if __name__=="__main__":
    unittest.main()
