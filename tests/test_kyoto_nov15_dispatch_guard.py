import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_nov15_dispatch_guard import validate_activation, ActivationRejected

class DispatchGuardTests(unittest.TestCase):
    def test_dispatch_requires_exact_confirmation(self):
        for value in ("", "NO", "nov15-observe-two-originals", "NOV15-OBSERVE-TWO-ORIGINALS "):
            with self.subTest(value=value), self.assertRaises(ActivationRejected):
                validate_activation(event_name="workflow_dispatch", confirmation=value, gate_path="missing")
        result = validate_activation(event_name="workflow_dispatch", confirmation="NOV15-OBSERVE-TWO-ORIGINALS", gate_path="missing")
        self.assertFalse(result["http_authorized"])
    def test_push_needs_exact_safe_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate=Path(tmp)/"gate.txt"
            with self.assertRaises(ActivationRejected):
                validate_activation(event_name="push", confirmation="", gate_path=gate)
            gate.write_text("NO")
            with self.assertRaises(ActivationRejected):
                validate_activation(event_name="push", confirmation="", gate_path=gate)
            gate.write_text("NOV15-OBSERVE-TWO-ORIGINALS\n")
            self.assertFalse(validate_activation(event_name="push", confirmation="", gate_path=gate)["http_authorized"])
    def test_schedule_and_other_events_rejected(self):
        for event in ("schedule", "workflow_run", "repository_dispatch", ""):
            with self.assertRaises(ActivationRejected):
                validate_activation(event_name=event, confirmation="NOV15-OBSERVE-TWO-ORIGINALS", gate_path="missing")
    def test_workflow_keeps_history_secret_time_gates(self):
        w=Path('.github/workflows/kyoto-nov15-encrypted-observer.yml').read_text()
        self.assertIn('workflow_dispatch:',w)
        self.assertIn('validate_activation(',w)
        self.assertLess(w.index('validate_activation('),w.index('NOV15_OBSERVER_OUTSIDE_TIME_WINDOW_NO_HTTP_RETRY_SAFE'))
        self.assertLess(w.index('NOV15_ENCRYPTED_ARCHIVE_SECRET_MISSING_OR_INVALID_NO_HTTP'),w.index('Up to TWO bounded observed official PC GET requests'))
        self.assertIn('audit_previous_runs(',w)
        self.assertNotIn('schedule:',w)

if __name__=='__main__': unittest.main()
