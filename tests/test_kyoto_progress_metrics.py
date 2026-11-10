"""Deterministic and destructive acceptance tests for the progress scorer."""
import copy
import unittest
import tempfile
import json
from pathlib import Path
from diagnostics.kyoto_progress_metrics import ProgressError, WEIGHTS, verify_rubric, measure, persistent_baseline


def fake_rubric():
    entries = []
    for phase, weight in WEIGHTS.items():
        amounts = [weight // 4] * 4
        for i in range(weight % 4):
            amounts[i] += 1
        for j, points in enumerate(amounts, 1):
            entries.append({"id": f"{phase}-{j:02d}", "phase": phase,
                            "points": points, "title": "test", "acceptance": "verified"})
    return {"schema": "kyoto_progress_fixed_scope.v1", "scope_id": "original",
            "weights": dict(WEIGHTS), "criteria": entries}


def fake_evidence(ids):
    return {"schema": "kyoto_progress_proof_claims.v1", "scope_id": "original",
            "claims": [{"id": x, "run_id": 1, "job_id": 2, "head_sha": "0" * 40,
                        "workflow_name": "known-good", "source_paths": ["existing.py"]}
                       for x in sorted(ids)]}


class ProgressMetricsTests(unittest.TestCase):
    def test_fixed_100_points_and_32_gates(self):
        self.assertEqual(sum(WEIGHTS.values()), 100)
        self.assertEqual(len(fake_rubric()["criteria"]), 32)
        self.assertEqual(len(verify_rubric(fake_rubric())), 64)

    def test_no_claims_is_zero_not_the_old_45_percent(self):
        measured = measure(fake_rubric(), fake_evidence([]), lambda _: True)
        self.assertEqual(measured["score_percent"], 0)
        self.assertIsNone(measured["delta_points"])

    def test_unverified_run_has_no_credit(self):
        with self.assertRaisesRegex(ProgressError, "proof failed"):
            measure(fake_rubric(), fake_evidence(["P1-01"]), lambda _: False)

    def test_duplicate_proof_is_rejected(self):
        e = fake_evidence(["P1-01"])
        e["claims"].append(copy.deepcopy(e["claims"][0]))
        with self.assertRaisesRegex(ProgressError, "duplicate"):
            measure(fake_rubric(), e, lambda _: True)

    def test_score_overflow_rejected(self):
        r = fake_rubric()
        r["criteria"][0]["points"] += 100
        with self.assertRaisesRegex(ProgressError, "phase points"):
            verify_rubric(r)

    def test_phase_allocation_cannot_change_silently(self):
        r = fake_rubric()
        r["weights"]["P1"] = 26
        with self.assertRaisesRegex(ProgressError, "weights"):
            verify_rubric(r)

    def test_unknown_extra_feature_cannot_change_original_scope(self):
        with self.assertRaisesRegex(ProgressError, "unknown"):
            measure(fake_rubric(), fake_evidence(["P9-01"]), lambda _: True)

    def test_unexplained_drop_fails_closed(self):
        before = measure(fake_rubric(), fake_evidence(["P1-01"]), lambda _: True)
        with self.assertRaisesRegex(ProgressError, "unexplained score decrease"):
            measure(fake_rubric(), fake_evidence([]), lambda _: True,
                    before, {"incidents": []})

    def test_decrease_requires_reason_evidence_and_recovery(self):
        before = measure(fake_rubric(), fake_evidence(["P1-01"]), lambda _: True)
        inc = {"incidents": [{"criterion_id": "P1-01", "reason": "IMPLEMENTATION_REGRESSION"}]}
        with self.assertRaisesRegex(ProgressError, "cause"):
            measure(fake_rubric(), fake_evidence([]), lambda _: True, before, inc)
        inc["incidents"][0].update({"description": "previous test failed",
            "evidence_url": "https://github.com/papaneko-ai/kyoto-keiba-ai/actions",
            "recovery_condition": "fix and rerun at new HEAD"})
        result = measure(fake_rubric(), fake_evidence([]), lambda _: True, before, inc)
        self.assertLess(result["delta_points"], 0)
        self.assertEqual(len(result["regressions"]), 1)

    def test_positive_and_unchanged_delta(self):
        before = measure(fake_rubric(), fake_evidence(["P1-01"]), lambda _: True)
        same = measure(fake_rubric(), fake_evidence(["P1-01"]),
                       lambda _: True, before, {"incidents": []})
        after = measure(fake_rubric(), fake_evidence(["P1-01", "P1-02"]),
                        lambda _: True, before, {"incidents": []})
        self.assertEqual(same["delta_points"], 0)
        self.assertGreater(after["delta_points"], 0)

    def test_tampered_previous_report_rejected(self):
        before = measure(fake_rubric(), fake_evidence(["P1-01"]), lambda _: True)
        before["score_percent"] = 95
        with self.assertRaisesRegex(ProgressError, "disagree"):
            measure(fake_rubric(), fake_evidence(["P1-01"]),
                    lambda _: True, before, {"incidents": []})

    def test_changed_rubric_not_comparable(self):
        before = measure(fake_rubric(), fake_evidence(["P1-01"]), lambda _: True)
        before["rubric_sha256"] = "bad"
        with self.assertRaisesRegex(ProgressError, "standard"):
            measure(fake_rubric(), fake_evidence(["P1-01"]),
                    lambda _: True, before, {"incidents": []})

    def test_deterministic_nonmutation(self):
        r, e = fake_rubric(), fake_evidence(["P1-01", "P2-01"])
        snapshots = copy.deepcopy((r, e))
        first = measure(r, e, lambda _: True)
        second = measure(r, e, lambda _: True)
        self.assertEqual(first, second)
        self.assertEqual((r, e), snapshots)


    def test_permanent_baseline_valid_and_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / "docs/diagnostics/kyoto_progress_baseline_20261110.json"
            target.parent.mkdir(parents=True)
            baseline = {"schema": "kyoto_progress_result.v1",
                        "scope_id": "KYOTO_P1_P8_FIXED_20261110",
                        "score_percent": 31,
                        "rubric_sha256": "b836ae69a22427b185545f569f9c6dc90923293277c02c7d58681321e40bc7bf",
                        "passed_ids": ["P1-01", "P1-02", "P2-01", "P3-01",
                                       "P4-01", "P5-01", "P6-01", "P8-01"],
                        "ci_run_id": "42730742998"}
            target.write_text(json.dumps(baseline), encoding="utf-8")
            self.assertEqual(persistent_baseline(root)["score_percent"], 31)
            baseline["score_percent"] = 45
            target.write_text(json.dumps(baseline), encoding="utf-8")
            with self.assertRaisesRegex(ProgressError, "tampered"):
                persistent_baseline(root)


if __name__ == "__main__":
    unittest.main()
