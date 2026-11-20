"""C12 fixed Saturday->Sunday all-run classification and fail-closed tests."""
import unittest
from unittest.mock import patch
from diagnostics.kyoto_impl25_c12_all_runs_handoff import (
    DAY,WORKFLOW,HandoffRejected,summarize,gather)

def make(run_id,*,event="schedule",status="completed",pc="RAW_BOTH_MARKETS_PRESERVED_NOT_AUTHENTICATED",
         sp="VALID_ORIGINALS_WITH_INCOMPLETE_MARKETS",pc_job="success",sp_job="success"):
    run={"id":run_id,"event":event,"name":WORKFLOW,"created_at":"2026-11-21T02:00:00Z",
         "status":status,"conclusion":"success"}
    return {"run":run,"jobs":[
        {"name":"pc-originals-independent","conclusion":pc_job,"steps":[]},
        {"name":"sp-originals-independent","conclusion":sp_job,"steps":[]}],
        "artifacts":[
            {"name":f"kyoto-pc-{run_id}-{DAY}","expired":False},
            {"name":f"kyoto-sp-{run_id}-{DAY}","expired":False}],
        "source_assessment":{
            "PC":{"state":pc,"ciphertext_authenticated":True,
                  "source_original_sha_utc_checked":True,
                  "both_raw_market_originals_sha_utc_verified":True},
            "SP":{"state":sp,"ciphertext_authenticated":True,
                  "source_original_sha_utc_checked":True}}}

class C12AllRuns(unittest.TestCase):
    def test_four_independent_runs_all_reported_and_never_called_market_success(self):
        entries=[make(104),make(101),make(103),make(102)]
        r=summarize(DAY,entries,total_count=4)
        self.assertEqual([x["run"]["id"] for x in r["scheduled_runs"]],[101,102,103,104])
        self.assertEqual(r["observed_schedule_count"],4)
        self.assertTrue(r["all_run_metadata_screened"])
        self.assertFalse(r["individual_cron_slot_identity_independently_proved"])
        self.assertEqual(r["scheduled_runs"][0]["lanes"]["PC"]["artifact_evidence_state"],
                         "RAW_BOTH_MARKETS_PRESERVED_NOT_AUTHENTICATED")
        self.assertFalse(r["full_live_jra_coverage_proved"])
        self.assertFalse(r["collector_sha_auto_promotion_authorized"])
        self.assertEqual(r["new_live_jra_http_requests_started"],0)

    def test_one_missing_run_cannot_be_hidden_by_three_successes(self):
        r=summarize(DAY,[make(1),make(2),make(3)],total_count=3)
        self.assertEqual(r["missing_run_count_lower_bound"],1)
        self.assertFalse(r["all_run_metadata_screened"])
        self.assertIn("SCHEDULED_RUN_COUNT_NOT_EXACTLY_FOUR",r["detected_review_reasons"])

    def test_one_pc_artifact_missing_in_four_runs_keeps_review_required(self):
        entries=[make(i) for i in range(1,5)]
        entries[2]["source_assessment"]["PC"]={"state":"EXACT_ARTIFACT_NOT_FOUND_OR_AMBIGUOUS"}
        entries[2]["artifacts"]=entries[2]["artifacts"][1:]
        r=summarize(DAY,entries)
        self.assertTrue(r["all_run_metadata_screened"])
        self.assertIn("SOURCE_OR_CIPHERTEXT_GAP_REQUIRES_REVIEW",r["detected_review_reasons"])
        self.assertFalse(r["scheduled_runs"][2]["lanes"]["PC"]["ciphertext_authenticated"])

    def test_c11_counts_only_when_recomputed_from_decrypted_sources(self):
        entries=[make(i) for i in range(1,5)]
        entries[0]["source_assessment"]["PC"].update({
            "c11_family_evidence_state":"RECOMPUTED_SOURCE_SHA_UTC_MATCH",
            "c11_verified_counts":{"g03_verified_races":11,
                "g04_verified_profiles":30,"g05_bound_races":10,
                "g06_paired_market_races_locally_verified":8}})
        entries[1]["source_assessment"]["PC"].update({
            "c11_family_evidence_state":"SAVED_C11_CANNOT_BE_REVALIDATED",
            "c11_verified_counts":{"g03_verified_races":12}})
        report=summarize(DAY,entries)
        self.assertEqual(report["scheduled_runs"][0]["lanes"]["PC"]["c11_verified_counts"]["g04_verified_profiles"],30)
        self.assertEqual(report["scheduled_runs"][1]["lanes"]["PC"]["c11_verified_counts"],{})
        self.assertIn("C11_G03_G06_FAMILY_COUNTS_NOT_RECOMPUTED",report["detected_review_reasons"])
        self.assertFalse(report["full_live_jra_coverage_proved"])

    def test_secret_or_ciphertext_error_not_marked_authenticated(self):
        entries=[make(i) for i in range(1,5)]
        entries[0]["source_assessment"]["SP"]={
            "state":"DECRYPT_OR_SOURCE_EVIDENCE_REJECTED",
            "ciphertext_authenticated":False,"error_class":"InvalidTag"}
        r=summarize(DAY,entries)
        self.assertFalse(r["scheduled_runs"][0]["lanes"]["SP"]["ciphertext_authenticated"])
        self.assertFalse(r["scheduled_runs"][0]["lanes"]["SP"]["official_live_market_accepted"])

    def test_manual_run_excluded_from_schedule_count(self):
        entries=[make(1),make(2),make(3),make(4,event="workflow_dispatch")]
        r=summarize(DAY,entries)
        self.assertEqual(r["observed_schedule_count"],3)
        self.assertEqual(r["excluded_runs"][0]["reason"],"NON_SCHEDULED_RUN")

    def test_duplicate_run_identity_rejected(self):
        with self.assertRaisesRegex(HandoffRejected,"duplicate_run_identity"):
            summarize(DAY,[make(1),make(1)])

    def test_wrong_day_or_workflow_rejected(self):
        with self.assertRaisesRegex(HandoffRejected,"c12_only_20261121"):
            summarize("20261122",[make(1)])
        e=make(1)
        e["run"]["name"]="unrelated-workflow"
        with self.assertRaisesRegex(HandoffRejected,"workflow_or_day_identity"):
            summarize(DAY,[e])

    def test_uncompleted_run_has_no_success_evidence(self):
        entries=[make(i) for i in range(1,5)]
        entries[0]["run"]["status"]="in_progress"
        r=summarize(DAY,entries)
        self.assertFalse(r["all_run_metadata_screened"])
        self.assertEqual(r["scheduled_runs"][0]["state"],"RUN_NOT_COMPLETED")

    def test_incomplete_pagination_cannot_prove_four_runs(self):
        r=summarize(DAY,[make(i) for i in range(1,5)],
                    total_count=1001,pagination_complete=False)
        self.assertFalse(r["github_run_listing_complete"])
        self.assertFalse(r["all_run_metadata_screened"])

    def test_missing_two_early_runs_is_not_inferred_as_http_failure(self):
        r=summarize(DAY,[],total_count=0)
        self.assertEqual(r["observed_schedule_count"],0)
        self.assertEqual(r["missing_run_count_lower_bound"],4)
        self.assertFalse(r["full_live_jra_coverage_proved"])

    def test_gather_uses_exact_artifact_names_not_prefix_or_old_run(self):
        docs={"runs":{"total_count":1,"workflow_runs":[{
            "id":99,"name":WORKFLOW,"event":"schedule",
            "created_at":"2026-11-21T00:10:00Z",
            "status":"completed","conclusion":"failure"}]},
            "jobs":{"total_count":2,"jobs":[
                {"name":"pc-originals-independent","conclusion":"failure","steps":[]},
                {"name":"sp-originals-independent","conclusion":"success","steps":[]}]},
            "artifacts":{"total_count":1,"artifacts":[{
                "name":"kyoto-sp-98-20261121","expired":False}]}}
        def api(path):
            return (docs["runs"] if "/runs?" in path else
                    docs["jobs"] if "/jobs?" in path else docs["artifacts"])
        with patch("diagnostics.kyoto_impl25_c12_all_runs_handoff._gh",side_effect=api),patch(
            "diagnostics.kyoto_impl25_c12_all_runs_handoff._download") as download:
            result=gather(DAY,"papaneko-ai/kyoto-keiba-ai")
        download.assert_not_called()
        self.assertEqual(result["observed_schedule_count"],1)
        self.assertEqual(result["scheduled_runs"][0]["lanes"]["SP"]["artifact_evidence_state"],
                         "EXACT_ARTIFACT_NOT_FOUND_OR_AMBIGUOUS")

    def test_no_automated_repair_or_prediction_authority(self):
        r=summarize(DAY,[make(i) for i in range(1,5)])
        self.assertEqual(r["next_day"],"20261122")
        self.assertIn("EXPLICIT_APPROVED_SHA",r["next_day_action"])
        self.assertFalse(r["automatic_patch_or_secret_edit_authorized"])
        self.assertFalse(r["independent_sp_full12_fallback_proved"])

if __name__=="__main__":
    unittest.main()
