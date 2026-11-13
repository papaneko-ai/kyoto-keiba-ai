import unittest
from diagnostics.kyoto_nov15_observer_artifact_identity import artifact_name,ObservationRunRejected,LAUNCHER,LEGACY

class ArtifactIdentityTests(unittest.TestCase):
 def r(self,**changes):
    d={"id":12345,"status":"completed","conclusion":"success","name":LAUNCHER,
       "head_branch":"main","event":"schedule","created_at":"2026-11-15T02:00:01Z"}
    d.update(changes)
    return d
 def test_workflow_uses_identity_checker_for_actual_artifact(self):
    from pathlib import Path
    wf=Path(".github/workflows/kyoto-nov15-second-day-observed-oneshot.yml").read_text(encoding="utf8")
    self.assertIn('gh api "repos/$GITHUB_REPOSITORY/actions/runs/$OBSERVER_RUN"',wf)
    self.assertIn("python -m diagnostics.kyoto_nov15_observer_artifact_identity",wf)
    self.assertIn('--name "$OBSERVER_ARTIFACT"',wf)
    self.assertLess(wf.index("NOV15_ARCHIVE_ENCRYPTION_SECRET_MISSING_NO_HTTP"),
                    wf.index("OBSERVER_ARTIFACT="))
    self.assertLess(wf.index("OBSERVER_ARTIFACT="),wf.index("gh run download"))
 def test_scheduled_launcher_name(self):
    self.assertEqual(artifact_name(self.r(),run_id="12345"),
      "kyoto-nov15-unattended-encrypted-observation-12345")
 def test_legacy_artifact_name(self):
    self.assertEqual(artifact_name(self.r(name=LEGACY,
      head_branch="jra-html-diagnostic-20261105",
      event="push",created_at="2026-11-13T09:00:00Z"),run_id="12345"),
      "kyoto-nov15-encrypted-observation-12345")
 def test_wrong_source_name(self):
    with self.assertRaises(ObservationRunRejected):artifact_name(self.r(name="different"),run_id="12345")
 def test_wrong_run_id(self):
    with self.assertRaises(ObservationRunRejected):artifact_name(self.r(),run_id="999")
 def test_early_scheduled_run(self):
    with self.assertRaises(ObservationRunRejected):artifact_name(self.r(created_at="2026-11-14T08:00:00Z"),run_id="12345")
 def test_manual_run_untrusted(self):
    with self.assertRaises(ObservationRunRejected):artifact_name(self.r(event="workflow_dispatch"),run_id="12345")
 def test_failure_not_source(self):
    with self.assertRaises(ObservationRunRejected):artifact_name(self.r(conclusion="failure"),run_id="12345")
 def test_incomplete_not_source(self):
    with self.assertRaises(ObservationRunRejected):artifact_name(self.r(status="in_progress"),run_id="12345")
 def test_wrong_branch(self):
    with self.assertRaises(ObservationRunRejected):artifact_name(self.r(head_branch="jra-html-diagnostic-20261105"),run_id="12345")
 def test_bad_legacy_date(self):
    with self.assertRaises(ObservationRunRejected):artifact_name(self.r(name=LEGACY,
      head_branch="jra-html-diagnostic-20261105",event="push",created_at="2026-11-11T00:00:00Z"),run_id="12345")
if __name__=="__main__":unittest.main()
