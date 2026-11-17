"""Offline regression for the Nov21→Nov22 scheduled result-handoff run-ID persistence."""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/".github/workflows/kyoto-20261121-22-result-handoff.yml"

def evaluate(source):
    issues=[]
    if '  schedule:' not in source or '  workflow_run:' not in source:
        issues.append("MISSING_AUTOMATED_DAY21_TRIGGER")
    if 'OBSERVED_RUN="$(python - <<\'PY\'' not in source:
        issues.append("NO_SCHEDULE_RUN_SELECTION")
    if 'echo "OBSERVED_RUN=$OBSERVED_RUN" >> "$GITHUB_ENV"' not in source:
        issues.append("SELECTED_RUN_NOT_PERSISTED")
    if not any('printf ' in line and ' > day_result_handoff/observed_run_id.txt' in line for line in source.splitlines()):
        issues.append("RUN_RECEIPT_MISSING")
    if 'if [ "$OBSERVED_RUN" != "0" ]; then' not in source:
        issues.append("NO_SAVED_RUN_HANDOFF")
    if '--run-id "$OBSERVED_RUN"' not in source:
        issues.append("SOURCE_ASSESSMENT_NOT_BOUND")
    if '--run day_result_handoff/run.json' not in source:
        issues.append("TRIAGE_NOT_BOUND")
    return issues

class HandoffContractTests(unittest.TestCase):
    def test_actual_workflow(self):
        self.assertEqual(evaluate(FILE.read_text()),[])
    def test_detect_missing_persistence(self):
        s=FILE.read_text().replace('echo "OBSERVED_RUN=$OBSERVED_RUN" >> "$GITHUB_ENV"','echo INVALID')
        self.assertIn("SELECTED_RUN_NOT_PERSISTED",evaluate(s))
    def test_detect_missing_receipt(self):
        s=FILE.read_text().replace(' > day_result_handoff/observed_run_id.txt',' > /dev/null')
        self.assertIn("RUN_RECEIPT_MISSING",evaluate(s))
    def test_detect_broken_downstream(self):
        s=FILE.read_text().replace('--run-id "$OBSERVED_RUN"','--run-id "0"')
        self.assertIn("SOURCE_ASSESSMENT_NOT_BOUND",evaluate(s))

if __name__=="__main__":
    unittest.main()
