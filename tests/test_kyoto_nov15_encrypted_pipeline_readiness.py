"""Current (non-public-originals) Nov15 readiness requires a prior encrypted observer."""
import json,tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_nov15_readiness_check import encrypted_pipeline_readiness
from test_kyoto_nov14_nov15_second_day_handoff import SPEC,ROSTER,START
class EncryptedReadinessTests(unittest.TestCase):
 def setUp(self):
    t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
    self.root=Path(t.name)
    (self.root/"docs/diagnostics").mkdir(parents=True)
    (self.root/"diagnostics").mkdir()
 def populate(self):
    directory=self.root/"docs/diagnostics"
    (directory/"nov15_pc_observed_race_spec.json").write_text(json.dumps(SPEC))
    (directory/"nov15_pc_current_roster.json").write_text(json.dumps(ROSTER,ensure_ascii=False))
    (directory/"nov15_pc_verified_start_utc.txt").write_text(START)
    (directory/"nov15_observer_run_id.txt").write_text("43112345678")
 def check(self,now="2026-11-14T12:00:00Z",**kw):
    return encrypted_pipeline_readiness(self.root,now_utc=now,**kw)
 def test_missing_inputs_are_visible(self):
    r=self.check()
    self.assertEqual(len(r["missing"]),4)
    self.assertEqual(r["state"],"NOT_READY")
    self.assertEqual(r["network_requests"],0)
 def test_metadata_ready_does_not_authenticate_jra(self):
    self.populate();r=self.check()
    self.assertEqual(r["state"],"INPUTS_READY_NEEDS_DECRYPTED_OFFICIAL_ORIGINAL_CHAIN")
    self.assertFalse(r["http_authorized"])
    self.assertFalse(r["JRA_source_authenticated"])
 def test_missing_observer_run_id_fails(self):
    self.populate();(self.root/"docs/diagnostics/nov15_observer_run_id.txt").unlink()
    self.assertIn("observer_run_id",self.check()["missing"])
 def test_wrong_day_roster_fails(self):
    self.populate()
    r={**ROSTER,"race_date":"2026-11-14"}
    (self.root/"docs/diagnostics/nov15_pc_current_roster.json").write_text(json.dumps(r))
    self.assertEqual(self.check()["state"],"NOT_READY")
 def test_start_cutoff_fails(self):
    self.populate();self.assertEqual(self.check(now="2026-11-15T06:40:00Z")["state"],"NOT_READY")
 def test_unsafe_preactivation_fails(self):
    self.populate();(self.root/"diagnostics/nov15_pc_explicit_activation.txt").write_text("NOV15-ONE-SHOT-READ-ONLY")
    r=self.check();self.assertIn("PREMATURE_ACTIVATION",r["invalid"])
 def test_runner_activation_is_explicitly_allowed_in_workflow(self):
    self.populate();(self.root/"diagnostics/nov15_pc_explicit_activation.txt").write_text("NOV15-ONE-SHOT-READ-ONLY")
    r=self.check(allow_activation=True)
    self.assertEqual(r["state"],"INPUTS_READY_NEEDS_DECRYPTED_OFFICIAL_ORIGINAL_CHAIN")
 def test_invalid_observer_id_does_not_grant_http(self):
    self.populate();(self.root/"docs/diagnostics/nov15_observer_run_id.txt").write_text("not-a-run")
    r=self.check();self.assertEqual(r["state"],"NOT_READY")
    self.assertFalse(r["http_authorized"])
if __name__=="__main__":unittest.main()
