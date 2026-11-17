"""Isolated bidirectional PC/SP and supplemental source evidence tests."""
from hashlib import sha256
import unittest
from diagnostics.kyoto_hybrid_multi_source import (
    merge_fields,rank_sources,coverage,HybridRejected)

R="KYOTO:20261121:03";C="2026-11-21T04:00:00Z"
PC={"kind":"JRA_PC","url":"https://www.jra.go.jp/JRADB/accessD.html?CNAME=observed",
    "verified_original_url":True,"license_verified":True,"allowed_for_automated_access":True}
SP={"kind":"JRA_SP","url":"https://sp.jra.jp/JRADB/accessD.html?CNAME=observed",
    "verified_original_url":True,"license_verified":True,"allowed_for_automated_access":True}
OTHER={"kind":"SUPPLEMENTAL","url":"https://example.org/actual-observed-source",
       "verified_original_url":True,"license_verified":True,"allowed_for_automated_access":True}
def ev(field,value,source=PC,*,horse=2,raw=b"real-source-bytes",capture="2026-11-21T03:00:00Z"):
    return {"race_key":R,"horse_number":horse,"field":field,"value":value,
            "source":source,"raw":raw,"source_sha256":sha256(raw).hexdigest(),
            "captured_utc":capture,"published_utc":None,"identity_verified":True}
def merge(items,fields=("body_weight","workout"),metrics=None):
    return merge_fields(race_key=R,horse_number=2,cutoff_utc=C,
                        evidence=items,required_fields=fields,metrics=metrics)

class HybridTests(unittest.TestCase):
    def test_pc_missing_sp_fills_specific_field_and_avoids_other_bets(self):
        r=merge([ev("body_weight",440,PC),ev("workout","54.0",SP)])
        self.assertTrue(r["complete"])
        self.assertEqual(r["fields"]["workout"]["source_kind"],"JRA_SP")
        self.assertEqual(r["fields"]["body_weight"]["source_kind"],"JRA_PC")
        self.assertEqual(r["network_requests"],0)
        self.assertFalse(r["prediction_ready"])
    def test_sp_main_pc_backfills_missing(self):
        r=merge([ev("body_weight",440,SP),ev("workout","54.0",PC)])
        self.assertTrue(r["complete"])
        self.assertEqual(r["fields"]["workout"]["source_kind"],"JRA_PC")
    def test_supplemental_only_when_explicitly_authorized(self):
        r=merge([ev("body_weight",440,SP),ev("workout","54.0",OTHER)])
        self.assertTrue(r["complete"])
        self.assertEqual(r["fields"]["workout"]["source_kind"],"SUPPLEMENTAL")
        bad=dict(OTHER,allowed_for_automated_access=False)
        with self.assertRaisesRegex(HybridRejected,"supplemental_usage_not_authorized"):
            merge([ev("workout","54.0",bad)],("workout",))
    def test_conflicting_pc_sp_values_do_not_silently_replace(self):
        r=merge([ev("body_weight",440,PC),ev("body_weight",450,SP)],("body_weight",))
        self.assertEqual(r["fields"]["body_weight"]["state"],"CONFLICT")
        self.assertIsNone(r["fields"]["body_weight"]["value"])
        self.assertFalse(r["complete"])
        self.assertEqual(r["conflict_fields"],["body_weight"])
    def test_unchanged_pc_sp_both_sources_count_once(self):
        r=merge([ev("body_weight",440,PC),ev("body_weight",440,SP)],("body_weight",))
        self.assertTrue(r["complete"])
        self.assertEqual(r["verified_field_count"],1)
        self.assertEqual(r["fields"]["body_weight"]["all_sources"],["JRA_PC","JRA_SP"])
    def test_missing_field_prioritized_for_additional_request(self):
        metrics={"JRA_PC":{"workout":{"samples":10,"verified_field_success":5,
                                        "mean_elapsed_seconds":1.0,"mean_bytes":8000}},
                 "JRA_SP":{"workout":{"samples":10,"verified_field_success":9,
                                        "mean_elapsed_seconds":2.0,"mean_bytes":1000}}}
        r=merge([],("workout",),metrics)
        self.assertEqual(r["followup"][0]["try_sources_in_order"],["JRA_SP","JRA_PC"])
        self.assertTrue(r["followup"][0]["must_observe_actual_links"])
    def test_main_changes_when_reliable_results_change(self):
        def met(pc,sp):
            return {"JRA_PC":{"profile":{"samples":10,"verified_field_success":pc,
                                         "mean_elapsed_seconds":1.0,"mean_bytes":400}},
                    "JRA_SP":{"profile":{"samples":10,"verified_field_success":sp,
                                         "mean_elapsed_seconds":1.2,"mean_bytes":200}}}
        self.assertEqual(rank_sources(met(9,7),"profile")[0],"JRA_PC")
        self.assertEqual(rank_sources(met(7,9),"profile")[0],"JRA_SP")
    def test_unknown_performance_never_promoted(self):
        self.assertEqual(rank_sources({"JRA_SP":{"workout":{"samples":1,
                 "verified_field_success":1,"mean_elapsed_seconds":0.1,"mean_bytes":99}}},"workout"),[])
    def test_sp_token_on_pc_host_forbidden(self):
        bad=dict(SP,url="https://jra.go.jp/JRADB/accessD.html?CNAME=abc")
        with self.assertRaisesRegex(HybridRejected,"channel_host_mismatch"):
            merge([ev("workout","54.0",bad)],("workout",))
    def test_original_sha_mismatch_rejected(self):
        bad=ev("workout","54.0");bad["raw"]=b"changed"
        with self.assertRaisesRegex(HybridRejected,"altered_original"):
            merge([bad],("workout",))
    def test_post_start_information_rejected(self):
        with self.assertRaisesRegex(HybridRejected,"captured_after_cutoff"):
            merge([ev("workout","54.0",capture="2026-11-21T04:01:00Z")],("workout",))
    def test_other_horse_cannot_backfill(self):
        with self.assertRaisesRegex(HybridRejected,"race_horse_identity_not_verified"):
            merge([ev("workout","54.0",horse=3)],("workout",))
    def test_supplemental_never_mistaken_for_official(self):
        bad=dict(OTHER,verified_original_url=False)
        with self.assertRaisesRegex(HybridRejected,"unverified_source_url"):
            merge([ev("workout","54.0",bad)],("workout",))
    def test_coverage_comparison_denominator_fixed(self):
        x=merge([ev("body_weight",440)],("body_weight","workout"))
        y=merge([ev("body_weight",440),ev("workout","54.0",SP)])
        self.assertEqual(coverage([x])["coverage_pct"],50.0)
        self.assertEqual(coverage([y])["coverage_pct"],100.0)
        self.assertEqual(coverage([x,y])["horses_fully_verified"],1)
    def test_supplemental_undocumented_publication_not_assumed(self):
        src=ev("workout","54.0",OTHER)
        src["published_utc"]="2026-11-21T04:30:00Z"
        with self.assertRaisesRegex(HybridRejected,"publication_after_capture_or_cutoff"):
            merge([src],("workout",))
if __name__=="__main__":unittest.main()
