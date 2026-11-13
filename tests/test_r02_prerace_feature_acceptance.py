"""R02 fixed acceptance: seven families, historical missing and leakage rejection."""
import unittest
from diagnostics.p2_prerace_feature_contract import freeze_feature_envelope,FeatureContractRejected,FAMILIES
from diagnostics.p2_p3_p5_offline_feature_bridge import _feature_row,FEATURE_SCHEMA
CUTOFF="2026-11-14T02:00:00Z"
START="2026-11-14T03:00:00Z"
SHA="a"*64
def fixture():
    return {"schema":"kyoto_p2_seven_family_envelope.v1",
        "race_id":"LAB-R02-20261114-01","source_scope":"LAB_OFFLINE_ONLY",
        "race_start_utc":START,"feature_cutoff_utc":CUTOFF,
        "racecard_source_sha256":SHA,
        "runners":[{"number":n,"frame":(n+1)//2,
            "families":{name:{"value":(n+idx)/20,"missing_reason":None,
                "captured_utc":"2026-11-14T01:00:00Z","source_sha256":SHA}
                for idx,name in enumerate(FAMILIES)}} for n in range(1,5)]}
class R02PreRaceAcceptance(unittest.TestCase):
    def setUp(self):self.data=fixture()
    def runcheck(self):return freeze_feature_envelope(self.data)
    def bad(self,err=None):
        with self.assertRaisesRegex(FeatureContractRejected,err or "."):self.runcheck()
    def test_seven_families_adapt_existing_p3(self):
        x=self.runcheck()
        self.assertEqual(x["status"],"P3_LAB_FEATURES_VALIDATED_NOT_PRODUCTION")
        self.assertEqual(x["receipt"]["family_names"],list(FAMILIES))
        self.assertEqual(len(x["p3_snapshot"]["runners"]),4)
        self.assertEqual(_feature_row(x["p3_snapshot"],expected_keys=FEATURE_SCHEMA),x["p3_snapshot"])
    def test_every_family_affects_receipt(self):
        base=self.runcheck()["receipt"]["receipt_sha256"]
        for name in FAMILIES:
            data=fixture();data["runners"][0]["families"][name]["value"]+=.05
            self.assertNotEqual(freeze_feature_envelope(data)["receipt"]["receipt_sha256"],base)
    def test_reproducible(self):self.assertEqual(self.runcheck(),self.runcheck())
    def test_missing_unqueried_is_skip_not_imputed(self):
        self.data["runners"][0]["families"]["jockey"].update(value=None,missing_reason="SOURCE_NOT_QUERIED")
        x=self.runcheck()
        self.assertIsNone(x["p3_snapshot"])
        self.assertEqual(x["receipt"]["missing"],[{"number":1,"family":"jockey","reason":"SOURCE_NOT_QUERIED"}])
    def test_verified_empty_separate_from_unqueried(self):
        self.data["runners"][0]["families"]["horse"].update(value=None,missing_reason="VERIFIED_NO_HISTORY")
        self.assertEqual(self.runcheck()["receipt"]["missing"][0]["reason"],"VERIFIED_NO_HISTORY")
    def test_all_family_missing_still_skip(self):
        for row in self.data["runners"]:
            for ev in row["families"].values():ev.update(value=None,missing_reason="SOURCE_UNAVAILABLE")
        x=self.runcheck()
        self.assertEqual(len(x["receipt"]["missing"]),28)
        self.assertIsNone(x["p3_snapshot"])
    def test_missing_reason_without_missing_value_rejected(self):
        self.data["runners"][0]["families"]["jockey"]["missing_reason"]="SOURCE_NOT_QUERIED";self.bad("feature_value_invalid")
    def test_missing_without_reason_rejected(self):
        self.data["runners"][0]["families"]["jockey"]["value"]=None;self.bad("missing_reason_required")
    def test_postrace_outcome_field_rejected(self):
        self.data["runners"][0]["families"]["winning_pair"]={"value":1};self.bad("family_missing_or_forbidden")
    def test_postrace_odds_field_rejected(self):
        self.data["runners"][0]["families"]["final_odds"]={"value":1};self.bad("family_missing_or_forbidden")
    def test_cutoff_after_start_refused(self):
        self.data["feature_cutoff_utc"]=START;self.bad("cutoff_not_before_start")
    def test_future_observation_rejected(self):
        self.data["runners"][0]["families"]["horse"]["captured_utc"]="2026-11-14T02:01:00Z";self.bad("future_feature_leakage")
    def test_future_known_result_rejected(self):
        self.data["runners"][0]["families"]["horse"]["captured_utc"]="2026-11-14T04:00:00Z";self.bad("future_feature_leakage")
    def test_nonutc_observation_rejected(self):
        self.data["runners"][0]["families"]["horse"]["captured_utc"]="2026-11-14T10:00:00+09:00";self.bad("utc_required")
    def test_missing_sha_rejected(self):
        self.data["runners"][0]["families"]["horse"]["source_sha256"]="";self.bad("sha256_required")
    def test_wrong_sha_shape_rejected(self):
        self.data["racecard_source_sha256"]="forged";self.bad("sha256_required")
    def test_duplicate_runner_rejected(self):
        self.data["runners"][1]["number"]=1;self.bad("runner_identity_invalid")
    def test_missing_entire_family_rejected(self):
        self.data["runners"][0]["families"].pop("ground");self.bad("family_missing_or_forbidden")
    def test_nonfinite_score_rejected(self):
        self.data["runners"][0]["families"]["pace"]["value"]=float("nan");self.bad("feature_value_invalid")
    def test_negative_score_rejected(self):
        self.data["runners"][0]["families"]["pace"]["value"]=-1;self.bad("feature_value_invalid")
    def test_nonlab_source_forbidden(self):
        self.data["source_scope"]="JRA_AUTHENTIC";self.bad("nonlab_scope_forbidden")
    def test_result_label_at_root_rejected(self):
        self.data["finish_order"]=[1,2];self.bad("envelope_schema_invalid")
    def test_no_official_or_spend_claim(self):
        x=self.runcheck()["receipt"]
        self.assertFalse(x["real_jra_authenticated"])
        self.assertFalse(x["production_ready"])
        self.assertFalse(x["spend_authorized"])
        self.assertEqual(x["network_requests"],0)
    def test_snapshot_immutable_from_input_mutation(self):
        out=self.runcheck()
        self.data["runners"][0]["families"]["horse"]["value"]=.99
        self.assertNotEqual(self.runcheck()["receipt"]["receipt_sha256"],out["receipt"]["receipt_sha256"])
        self.assertNotEqual(self.runcheck()["p3_snapshot"],out["p3_snapshot"])
if __name__=="__main__":unittest.main()
