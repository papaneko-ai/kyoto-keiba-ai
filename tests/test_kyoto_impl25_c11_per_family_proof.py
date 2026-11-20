"""C11 verifies locally archived G03-G06 originals, UTC and missingness."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from tests.test_kyoto_g05_conditions import G05Tests,DAY
from tests.test_kyoto_g06_all12_capture import samples,mock_collector
from diagnostics.kyoto_g05_conditions import compile_saved
from diagnostics.kyoto_g06_all12_capture import run_twelve
from diagnostics.kyoto_g06_nested_bundle import bundle_g06
from diagnostics.kyoto_impl25_c11_per_family_proof import assess,save

class C11FamilyEvidenceTests(unittest.TestCase):
    def setUp(self):
        G05Tests.setUp(self)

    def test_12r_g03_g05_and_unknown_g04_g06_not_falsely_successful(self):
        compile_saved(self.root,day=DAY)
        report=save(self.root,DAY)
        self.assertEqual(report["g03_verified_races"],12)
        self.assertEqual(report["g05_bound_races"],12)
        self.assertEqual(report["g04_verified_profiles"],0)
        self.assertEqual(report["g06_paired_market_races_locally_verified"],0)
        self.assertEqual(len(report["races"]),12)
        one=report["races"]["1"]
        self.assertEqual(one["g05"]["track"]["weather"]["state"],"SHA_UTC_BOUND")
        self.assertEqual(len(one["g04"]["horses"]),4)
        self.assertEqual(one["g04"]["horses"]["1"]["fields"]["workout"]["state"],"MISSING_OR_UNVERIFIED")
        self.assertEqual(one["g04"]["horses"]["1"]["fields"]["workout"]["missing_reason"],
                         "SOURCE_NOT_INDEPENDENTLY_OBSERVED")
        self.assertFalse(report["prediction_ready"])
        self.assertFalse(report["jra_network_origin_authenticated_by_this_report"])

    def test_one_tampered_g03_race_does_not_certify_downstream(self):
        compile_saved(self.root,day=DAY)
        path=self.root/"g03_official_racecard_02.html"
        path.write_bytes(path.read_bytes()+b"tampered")
        result=assess(self.root,DAY)
        self.assertEqual(result["g03_verified_races"],11)
        self.assertEqual(result["g05_bound_races"],11)
        self.assertEqual(result["races"]["2"]["g03"]["state"],"MISSING_OR_UNVERIFIED")
        self.assertEqual(result["races"]["1"]["g03"]["state"],"SHA_UTC_PRESTART_VERIFIED")

    def test_profile_proof_must_match_horse_identity_cutoff_sha_utc(self):
        r=json.loads((self.root/"g03_receipt.json").read_text())
        horse=r["races"]["1"]["runners"][0]
        name="g04_profile_r01_h01.html"
        raw=b"sample profile source original"
        (self.root/name).write_bytes(raw)
        cutoff="2026-11-21T01:00:00+00:00"
        profile={"race":1,"horse_number":1,"horse_name":horse["name"],
                 "profile_verified":True,"raw_original_file":name,
                 "source_sha256":hashlib.sha256(raw).hexdigest(),
                 "captured_at_utc":"2026-11-21T00:01:00+00:00",
                 "race_cutoff_utc":cutoff}
        # Set cutoff based on actual independently verified racecard, rather
        # than assuming the fixture starts at a fixed hour.
        from diagnostics.kyoto_impl25_c11_per_family_proof import _cutoff
        profile["race_cutoff_utc"]=_cutoff(DAY,r["races"]["1"]["start_time_jst"])
        (self.root/"g04_receipt.json").write_text(json.dumps({
            "schema":"kyoto_g04_all_horses.v1","day":DAY,"profiles":[profile]}))
        self.assertEqual(assess(self.root,DAY)["g04_verified_profiles"],1)
        (self.root/name).write_bytes(b"tampered")
        self.assertEqual(assess(self.root,DAY)["g04_verified_profiles"],0)

    def test_paired_g06_market_proof_separate_from_bundle_sha(self):
        with tempfile.TemporaryDirectory() as t:
            inner=Path(t)/"markets"
            batch=run_twelve(inner,records=samples(),runner=mock_collector)
            self.assertEqual(batch["verified_dual_market_races"],12)
            bundle_g06(inner,self.root/"g06_source_bundle.tar.gz")
        report=assess(self.root,DAY)
        self.assertEqual(report["g03_verified_races"],12)
        self.assertEqual(report["g06_paired_market_races_locally_verified"],12)
        self.assertEqual(report["races"]["3"]["g06"]["markets"]["quinella"]["state"],
                         "SHA_UTC_PRESTART_MATCH")
        # Valid outer tar hash does not itself establish verified live markets.
        self.assertFalse(report["prediction_ready"])

    def test_corrupt_bundle_never_validates_markets(self):
        (self.root/"g06_source_bundle.tar.gz").write_bytes(b"not a tar")
        report=assess(self.root,DAY)
        self.assertEqual(report["g06_paired_market_races_locally_verified"],0)
        self.assertEqual(report["races"]["1"]["g06"]["state"],
                         "INVALID_G06_BUNDLE_OR_RECEIPT")

    def test_no_receipt_overwrite_or_wrong_day(self):
        save(self.root,DAY)
        with self.assertRaisesRegex(ValueError,"already_exists"):
            save(self.root,DAY)
        with self.assertRaisesRegex(ValueError,"invalid_day"):
            assess(self.root,"20261123")

if __name__=="__main__":
    unittest.main()
