"""Independent limited regression for 11-of-12 G03 recoverable data."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit,parse_qs

from diagnostics.kyoto_g03_all_races import acquire_all
from diagnostics.kyoto_g03_independent_partial import verify_partial, PartialProofRejected
from diagnostics.kyoto_g03_proof_verify import verify as verify_all,G03ProofRejected
from diagnostics.kyoto_g04_all_horse_profiles import capture
from diagnostics.kyoto_g05_conditions import compile_saved
from tests.test_kyoto_g03_all_races import DAY,PARENT,meeting,source_race
from tests.test_kyoto_g04_all_horse_profiles import horse_card,profile
from tests.test_kyoto_g05_conditions import source

class PartialSourceTests(unittest.TestCase):
    def setUp(self):
        td=tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.home=Path(td.name)
        self.root=self.home/"saved";self.root.mkdir()

    def originals(self,mode):
        raw=lambda url:(horse_card(source_race(url)) if mode=="G04"
                         else source(source_race(url)))
        stage=self.home/"stage"
        report=acquire_all(day=DAY,root=stage,meeting_raw=meeting(),
            meeting_url=PARENT,fetch=raw,
            captured_at_utc=lambda:"2026-11-21T00:00:00Z",allowed=True)
        self.assertTrue(report["complete"])
        for p in stage.iterdir():p.rename(self.root/("g03_"+p.name))
        shutil.copyfile(self.root/"g03_official_meeting.html",
                        self.root/"official_meeting.html")
        self.report=report
        self.write()

    def write(self):
        (self.root/"g03_receipt.json").write_text(json.dumps(self.report),encoding="utf8")

    def omit(self,race):
        self.report["complete"]=False
        self.report["missing_races"]=[race]
        self.report["races"][str(race)]={"state":"SOURCE_OR_PARSE_FAILED",
                                        "reason":"injected_failed_race"}
        (self.root/f"g03_official_racecard_{race:02d}.html").unlink()
        self.write()

    def test_11_proven_races_still_accepted_and_full_contract_rejected(self):
        self.originals("G04");self.omit(7)
        r=verify_partial(self.root,expected_day=DAY)
        self.assertEqual(r["verified_race_count"],11)
        self.assertNotIn(7,r["verified_race_numbers"])
        self.assertFalse(r["all_12_races_verified"])
        self.assertFalse(r["prediction_ready"])
        with self.assertRaisesRegex(G03ProofRejected,"partial_capture"):
            verify_all(self.root,expected_day=DAY)

    def test_11r_profiles_and_prior_form_no_missing_race_request(self):
        self.originals("G04");self.omit(7)
        urls=[]
        def fetch(url):
            urls.append(url)
            token=parse_qs(urlsplit(url).query)["CNAME"][0]
            n=int(token[-5:-3])
            return profile(f"競走馬{n}")
        r=capture(root=self.root,day=DAY,fetch=fetch,
            clock=lambda:"2026-11-21T00:01:00Z",
            allowed=True,allow_partial=True)
        self.assertEqual(r["verified_g03_races"],11)
        self.assertEqual(r["profile_verified_count"],33)
        self.assertEqual(r["expected_horses"],33)
        self.assertFalse(r["all_profiles_parsed"])
        self.assertFalse(r["prediction_ready"])
        self.assertFalse(any(p.name.startswith("g04_profile_r07") for p in self.root.iterdir()))
        self.assertEqual(len(urls),33)

    def test_11r_weather_and_body_weights_preserved(self):
        self.originals("G05");self.omit(7)
        r=compile_saved(self.root,day=DAY,allow_partial=True)
        self.assertEqual(r["g03_races_verified"],11)
        self.assertEqual(len(r["races"]),11)
        self.assertNotIn("7",r["races"])
        self.assertEqual(r["observed_field_values"],11*(3+4*2))
        self.assertFalse(r["full_twelve_race_data_verified"])
        self.assertFalse(r["prediction_ready"])

    def test_modified_sha_skips_bad_race_but_keeps_11(self):
        self.originals("G05")
        p=self.root/"g03_official_racecard_07.html"
        p.write_bytes(p.read_bytes()+b" ")
        r=verify_partial(self.root,expected_day=DAY)
        self.assertEqual(r["verified_race_count"],11)
        self.assertEqual([x["race"] for x in r["excluded_races"]],[7])

    def test_forged_roster_skips_bad_race(self):
        self.originals("G04")
        self.report["races"]["7"]["runners"][0]["name"]="FAKE"
        self.write()
        r=verify_partial(self.root,expected_day=DAY)
        self.assertNotIn(7,r["verified_race_numbers"])

    def test_after_start_capture_not_promoted(self):
        self.originals("G05")
        self.report["races"]["7"]["captured_at_utc"]="2026-11-21T23:00:00Z"
        self.write()
        r=verify_partial(self.root,expected_day=DAY)
        self.assertNotIn(7,r["verified_race_numbers"])

    def test_wrong_day_rejects_all(self):
        self.originals("G04")
        with self.assertRaisesRegex(PartialProofRejected,"day_mismatch"):
            verify_partial(self.root,expected_day="20261122")

    def test_all_12_still_valid_for_original_full_verifier(self):
        self.originals("G05")
        self.assertEqual(verify_partial(self.root,expected_day=DAY)["verified_race_count"],12)
        self.assertEqual(verify_all(self.root,expected_day=DAY)["races_verified"],12)

if __name__=="__main__":unittest.main()
