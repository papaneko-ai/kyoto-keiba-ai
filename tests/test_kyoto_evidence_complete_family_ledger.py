"""Deterministic evidence-contract and destructive tests; no JRA traffic."""
import copy
import hashlib
import json
import unittest
from diagnostics.kyoto_evidence_complete_family_ledger import build, FAMILIES

DAY="20261122"
SHA="a"*64
UTC="2026-11-22T00:19:12Z"
SRC_SCHEMA="kyoto_nov22_observed_official_all12.v1"
G03_SCHEMA="kyoto_nov22_frozen_g03_on_actual_source.v1"

def fixtures():
    src={"schema":SRC_SCHEMA,"day":DAY,"races":{}}
    g03={"schema":G03_SCHEMA,"day":DAY,"races":{}}
    for race in range(1,13):
        src["races"][str(race)]={
           "PC":{"state":"REAL_OFFICIAL_ORIGINAL_SAVED_ROSTER_NOT_AUTHENTICATED",
                 "sha256":SHA,"captured_at_utc":UTC,"reused_existing_original":race==1},
           "SP":{"state":"PC_OFFICIAL_SOURCE_PRESENT_SP_DUPLICATE_NOT_NEEDED"}}
        g03["races"][str(race)]={
           "state":"G03_ROSTER_AND_START_PARSED_FROM_ACTUAL_ORIGINAL",
           "original_sha256":SHA,"captured_at_utc":UTC,
           "runner_count":14,"start_time_jst":"10:05",
           "horse_profiles_observed":14,"past_run_dates_observed":80}
    return src,g03

def item(data,race,family):
    return next(r for r in data["records"] if r["race"]==race and r["family"]==family)

class DurableLedger(unittest.TestCase):
    def test_complete_raw_plus_parser_never_claims_missing_families(self):
        a,b=fixtures()
        v=build(a,b,day=DAY)
        self.assertEqual(len(v["records"]),108)
        self.assertEqual(v["counts"]["racecard_original"]["ORIGINAL_VERIFIED"],12)
        self.assertEqual(v["counts"]["roster"]["STRUCTURED_VERIFIED"],12)
        for f in FAMILIES[2:]:
            self.assertEqual(v["counts"][f]["UNOBSERVED"],12)
        self.assertEqual(v["counts"]["quinella_odds"]["STRUCTURED_VERIFIED"],0)
        self.assertEqual(v["counts"]["bracket_quinella_odds"]["STRUCTURED_VERIFIED"],0)
        self.assertFalse(v["prediction_ready"])
        self.assertFalse(v["market_prices_verified"])
        self.assertEqual(len(v["missing_keys"]),7*12)
        self.assertTrue(any(x["event"]=="NAVIGATION_ONLY"
                            for x in item(v,1,"horse_profile")["observations"]))

    def test_success_and_failure_same_race_preserve_both(self):
        a,b=fixtures()
        a["races"]["5"]["PC"]={"state":"HTTP_OR_SOURCE_REJECTED",
                                   "error_class":"TimeoutError"}
        a["races"]["5"]["SP"]={"state":"REAL_OFFICIAL_ORIGINAL_SAVED_ROSTER_NOT_AUTHENTICATED",
                                   "sha256":SHA,"captured_at_utc":UTC}
        b["races"]["5"]={"state":"G03_SOURCE_PARSER_REJECTED","error_class":"G03Error"}
        v=build(a,b,day=DAY)
        raw=item(v,5,"racecard_original")
        self.assertEqual(raw["state"],"ORIGINAL_VERIFIED")
        self.assertEqual(raw["source_channel"],"SP")
        self.assertEqual(raw["failure_classes"],["TimeoutError"])
        self.assertEqual(item(v,5,"roster")["state"],"ATTEMPT_FAILED")
        self.assertEqual(len([x for x in raw["observations"] if x["event"]=="SOURCE_ATTEMPT_FAILED"]),1)

    def test_bad_provenance_must_raise(self):
        for change in [{"sha256":"xyz"}, {"captured_at_utc":"tomorrow"},
                       {"captured_at_utc":"2026-11-22T09:19:00+09:00"}]:
            a,b=fixtures()
            a["races"]["2"]["PC"].update(change)
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,"unverified_original_provenance"):
                build(a,b,day=DAY)

    def test_conflicting_g03_source_blocks_structured_promotion(self):
        a,b=fixtures()
        b["races"]["6"]["original_sha256"]="b"*64
        v=build(a,b,day=DAY)
        self.assertEqual(item(v,6,"roster")["state"],"CONFLICT")
        self.assertIn(item(v,6,"roster")["key"],v["missing_keys"])

    def test_invalid_runner_or_start_time_never_certified(self):
        for field,value in [("runner_count",1),("runner_count",19),
                            ("runner_count",True),("start_time_jst","10:5")]:
            a,b=fixtures()
            b["races"]["3"][field]=value
            with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,"invalid_structured_g03"):
                build(a,b,day=DAY)

    def test_absent_run_is_unobserved_not_failure(self):
        a,b=fixtures()
        a["races"]["4"]={}
        b["races"]["4"]={"state":"UNKNOWN"}
        v=build(a,b,day=DAY)
        self.assertEqual(item(v,4,"racecard_original")["state"],"UNOBSERVED")
        self.assertNotIn("HTTP_FAILED",item(v,4,"racecard_original")["failure_classes"])
        self.assertEqual(item(v,4,"roster")["state"],"UNOBSERVED")

    def test_day_conflict_and_race_missing_fail_closed(self):
        a,b=fixtures()
        b["day"]="20261121"
        with self.assertRaisesRegex(ValueError,"day_receipt_mismatch"):
            build(a,b,day=DAY)
        b["day"]=DAY;del a["races"]["12"]
        with self.assertRaisesRegex(ValueError,"missing_complete_12r_receipts"):
            build(a,b,day=DAY)

    def test_idempotence_and_input_immutability(self):
        a,b=fixtures()
        before=json.dumps([a,b],sort_keys=True)
        v=build(a,b,day=DAY)
        self.assertEqual(v,build(a,b,day=DAY))
        self.assertEqual(json.dumps([a,b],sort_keys=True),before)
        h=v.pop("content_sha256")
        payload=json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
        self.assertEqual(hashlib.sha256(payload).hexdigest(),h)

if __name__=="__main__":
    unittest.main()
