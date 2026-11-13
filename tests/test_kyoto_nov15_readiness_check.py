"""Nov15 zero-network readiness: missing inputs, day-of cutoff, provenance limits."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_nov15_readiness_check import readiness, INPUTS, WORKFLOW, REQUIRED_TRIGGER
from test_kyoto_nov14_nov15_second_day_handoff import SPEC,ROSTER,SEL,MEET,START

class ReadinessTests(unittest.TestCase):
 def setUp(self):
    self.tmp=tempfile.TemporaryDirectory()
    self.addCleanup(self.tmp.cleanup)
    self.root=Path(self.tmp.name)
    (self.root/"docs/diagnostics").mkdir(parents=True)
    (self.root/".github/workflows").mkdir(parents=True)
    (self.root/"diagnostics").mkdir(parents=True)
    (self.root/WORKFLOW).write_text("no-network test placeholder")
 def put_inputs(self):
    values={"spec":json.dumps(SPEC).encode(),"roster":json.dumps(ROSTER,ensure_ascii=False).encode(),
            "selection":SEL,"meeting":MEET,"start":(START+"\n").encode()}
    for key,raw in values.items():
        (self.root/INPUTS[key]).write_bytes(raw)
 def test_no_files_is_diagnostic_without_network(self):
    r=readiness(self.root)
    self.assertEqual(set(r["missing"]),set(INPUTS))
    self.assertEqual(r["state"],"NOT_READY_FAIL_CLOSED")
    self.assertEqual(r["network_requests"],0)
    self.assertFalse(r["can_execute_official_http_now"])
 def test_exact_offline_inputs_ready_is_not_real_jra_certified(self):
    self.put_inputs()
    r=readiness(self.root)
    self.assertEqual(r["state"],"OFFLINE_INPUTS_READY_NOT_SOURCE_AUTHENTICATED")
    self.assertFalse(r["source_authenticity_proven"])
    self.assertFalse(r["can_execute_official_http_now"])
    self.assertEqual(len(r["input_sha256"]),5)
 def test_race_day_morning_is_not_prematurely_blocked(self):
    self.put_inputs()
    r=readiness(self.root,clock_utc="2026-11-15T03:30:00Z")
    self.assertEqual(r["state"],"OFFLINE_INPUTS_READY_NOT_SOURCE_AUTHENTICATED")
 def test_after_cutoff_rejected(self):
    self.put_inputs()
    r=readiness(self.root,clock_utc="2026-11-15T06:40:00Z")
    self.assertEqual(r["state"],"NOT_READY_FAIL_CLOSED")
    self.assertTrue(any("capture_cutoff" in x for x in r["invalid"]))
 def test_bad_day14_roster_rejected(self):
    self.put_inputs()
    roster={**ROSTER,"race_date":"2026-11-14"}
    (self.root/INPUTS["roster"]).write_text(json.dumps(roster,ensure_ascii=False))
    r=readiness(self.root)
    self.assertEqual(r["state"],"NOT_READY_FAIL_CLOSED")
 def test_link_tampering_detected(self):
    self.put_inputs()
    changed=MEET.replace(b"%2FB2",b"%2FC3")
    (self.root/INPUTS["meeting"]).write_bytes(changed)
    r=readiness(self.root)
    self.assertEqual(r["state"],"NOT_READY_FAIL_CLOSED")
 def test_activation_file_existing_is_unsafe_in_preflight(self):
    self.put_inputs()
    (self.root/REQUIRED_TRIGGER).write_text("NOV15-ONE-SHOT-READ-ONLY")
    r=readiness(self.root)
    self.assertIn("PREMATURE_OR_ALREADY_CONSUMED_ACTIVATION",r["invalid"])
 def test_symlink_original_rejected(self):
    self.put_inputs()
    path=self.root/INPUTS["selection"]
    path.unlink()
    path.symlink_to(self.root/INPUTS["meeting"])
    r=readiness(self.root)
    self.assertIn("SYMLINK:selection",r["invalid"])
 def test_bad_start_rejected(self):
    self.put_inputs()
    (self.root/INPUTS["start"]).write_text("2026-11-14T06:45:00Z")
    r=readiness(self.root)
    self.assertTrue(any("verified_start_format_invalid" in x for x in r["invalid"]))
 def test_no_fake_both_market_authentication(self):
    self.put_inputs()
    r=readiness(self.root)
    self.assertFalse(r["real_market_verified"])
    self.assertFalse(r["provisional_source_receipt"]["real_prerace_quinella_authenticated"])
    self.assertFalse(r["provisional_source_receipt"]["real_prerace_bracket_authenticated"])
 def test_no_workflow_file_fails_closed(self):
    self.put_inputs()
    (self.root/WORKFLOW).unlink()
    r=readiness(self.root)
    self.assertIn("WORKFLOW_NOT_PRESENT",r["invalid"])
 def test_invalid_override_path_refused(self):
    overrides=copy.deepcopy(INPUTS)
    overrides["spec"]="../other.json"
    r=readiness(self.root,paths=overrides)
    self.assertIn("UNSAFE_PATH:spec",r["invalid"])
if __name__=="__main__":
 unittest.main()
