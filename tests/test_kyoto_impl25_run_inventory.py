"""Destructive no-network tests for full day21/22 run inventory."""
import unittest
from diagnostics.kyoto_impl25_run_inventory import summarize, NAME


def run(i, day="20261121", status="completed", conclusion="success"):
    return {"id": i, "name": NAME, "created_at":
            f"{day[:4]}-{day[4:6]}-{day[6:]}T02:00:00Z",
            "status": status, "conclusion": conclusion, "event": "schedule"}


def details(i, day="20261121", artifact=True):
    return {"jobs": [{"name": "pc-originals-independent", "conclusion": "success"},
                     {"name": "sp-originals-independent", "conclusion": "failure"}],
            "artifacts": ([{"name": f"kyoto-pc-{i}-{day}", "expired": False}]
                          if artifact else [])}


class RunInventoryTests(unittest.TestCase):
    def test_all_four_runs_are_reported_not_only_latest(self):
        runs = [run(i) for i in (11, 12, 13, 14)]
        result = summarize("20261121", runs,
                           {str(i): details(i) for i in (11, 12, 13, 14)})
        self.assertEqual([x["run_id"] for x in result["runs"]], [11,12,13,14])
        self.assertEqual(result["runs_found"], 4)
        self.assertFalse(result["g03_g04_g05_g06_all_race_evidence_verified"])
        self.assertFalse(result["source_success_from_job_or_artifact_metadata"])

    def test_successful_job_and_artifact_never_authenticate_jra(self):
        res = summarize("20261121", [run(11)], {"11": details(11)})
        lane = res["runs"][0]["lanes"]["pc-originals-independent"]
        self.assertTrue(lane["encrypted_artifact_metadata_present"])
        self.assertFalse(lane["g03_g04_g05_g06_per_race_coverage_verified"])
        self.assertEqual(res["runs"][0]["source_claim"], "NOT_AUTHENTICATED_BY_METADATA")

    def test_missing_run_details_are_preserved(self):
        res = summarize("20261121", [run(11)], {})
        self.assertEqual(res["runs"][0]["detail_state"],
                         "COMPLETED_RUN_DETAILS_MISSING")

    def test_other_day_is_not_reclassified(self):
        res = summarize("20261121", [run(11, day="20261122")], {})
        self.assertEqual(res["runs_found"], 0)

    def test_duplicate_run_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            summarize("20261121", [run(11), run(11)], {})

    def test_wrong_workflow_fails(self):
        r = run(11)
        r["name"] = "invented-workflow"
        with self.assertRaisesRegex(ValueError, "WRONG_WORKFLOW"):
            summarize("20261121", [r], {})

    def test_no_run_is_not_a_failed_jra_attempt(self):
        res = summarize("20261121", [], {})
        self.assertEqual(res["runs_found"], 0)
        self.assertFalse(res["g03_g04_g05_g06_all_race_evidence_verified"])

    def test_page_limit_marks_incomplete_inventory(self):
        res = summarize("20261121", [run(i) for i in range(1,101)], {})
        self.assertFalse(res["all_runs_in_api_page_confirmed"])

    def test_sp_and_workout_cannot_be_promoted(self):
        res = summarize("20261122", [run(11, day="20261122")],
                        {"11": details(11, day="20261122")})
        self.assertFalse(res["sp_full_twelve_races_verified"])
        self.assertFalse(res["auxiliary_independent_workout_source_verified"])
        self.assertFalse(res["day22_automatic_new_sha_promotion_allowed"])


if __name__ == "__main__":
    unittest.main()
