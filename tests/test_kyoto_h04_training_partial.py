import json,os,pathlib,unittest
from diagnostics.kyoto_h04_training_partial import parse_public_training,H04Error
from diagnostics.jra_pc_sp_benchmark import frozen
URL="https://race.netkeiba.com/race/oikiri.html?race_id=202608050102&rf=shutuba_submenu&type=2"
class ActualOriginalProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=pathlib.Path(os.environ.get("KYOTO_H04_EVIDENCE_DIR","h04_single_source_evidence"))
        cls.raw=(root/"observed_auxiliary_page.html").read_bytes()
        cls.receipt=json.loads((root/"receipt.json").read_text())
    def report(self):
        return parse_public_training(self.raw,observed_url=URL,race_id="202608050102",
            runners=frozen(2)["runners"],captured_utc=self.receipt["captured_at_utc"],
            cutoff_utc="2026-11-07T01:35:00Z")
    def test_sha_lock(self):
        self.assertEqual(self.report()["source_sha256"],self.receipt["source_sha256"])
    def test_three_of_fifteen_independent_roster(self):
        data=self.report()
        self.assertEqual((data["roster_count"],data["matched_training_count"]),(15,3))
        self.assertEqual(data["unavailable_horse_numbers"],list(range(4,16)))
        self.assertFalse(data["prediction_ready"])
        self.assertFalse(data["pre_race_original_verified"])
    def test_actual_training_fields(self):
        rows=self.report()["training_rows"]
        self.assertEqual(rows[0]["horse_name"],"ステラヴェント")
        self.assertEqual(rows[0]["training_date"],"2026-11-04")
        self.assertTrue(rows[0]["clock_samples"])
        self.assertEqual(rows[2]["rating"],"A")
    def test_conflicting_race_id_rejected(self):
        with self.assertRaises(H04Error):
            parse_public_training(self.raw,observed_url=URL,race_id="202608050103",
                runners=frozen(2)["runners"],captured_utc=self.receipt["captured_at_utc"],
                cutoff_utc="2026-11-07T01:35:00Z")
if __name__=="__main__":unittest.main()
