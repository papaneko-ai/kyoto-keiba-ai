"""Nov14 evidence-based one-shot exclusion guard.

The previous GET must never be retried merely because source capture failed.
Explicit source-evidence receipt and persisted incident record are inputs,
not a guess that the race was unpublished. Entirely offline.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

INCIDENT="docs/diagnostics/nov14_existing_attempt_safe_stop_20261113.md"
RUN_ID="43142384975"
EXPECTED_DAY="20261114"

class AttemptGuardRejected(ValueError):
    pass

def evaluate_attempt_guard(incident_text, *, prior_attempted_get, event_name):
    if (type(incident_text) is not str
        or RUN_ID not in incident_text
        or "attempted_GET=1" not in incident_text
        or "2026-11-14" not in incident_text
        or "FAILED_CLOSED" not in incident_text):
        raise AttemptGuardRejected("prior_attempt_incident_not_locked")
    if type(prior_attempted_get) is not int or prior_attempted_get not in (0,1):
        raise AttemptGuardRejected("prior_attempt_count_invalid")
    if event_name not in ("workflow_dispatch","push","offline_preflight"):
        raise AttemptGuardRejected("trigger_invalid")
    if prior_attempted_get != 1:
        raise AttemptGuardRejected("incident_and_attempt_disagree")
    return {
        "schema":"kyoto_nov14_attempt_guard.v1",
        "race_day":EXPECTED_DAY,
        "prior_run_id":RUN_ID,
        "prior_attempted_GET":prior_attempted_get,
        "status":"PRIOR_ONE_SHOT_ALREADY_ATTEMPTED_NO_REPEAT",
        "safe_next_action":"PRESERVE_EVIDENCE_AND_OFFLINE_DIAGNOSE",
        "allow_JRA_GET":False,
        "allow_workflow_rerun":False,
        "real_market_verified":False,
        "network_requests":0
    }

def enforce_recorded_one_shot(incident_path=INCIDENT, *, event_name="workflow_dispatch"):
    path=Path(incident_path)
    if path.is_symlink() or not path.is_file():
        raise AttemptGuardRejected("incident_record_unavailable_no_live_permission")
    text=path.read_text(encoding="utf-8")
    status=evaluate_attempt_guard(text,prior_attempted_get=1,event_name=event_name)
    if status["allow_JRA_GET"] is not False:
        raise AttemptGuardRejected("attempt_guard_not_closed")
    return status

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--incident",default=INCIDENT)
    args=p.parse_args()
    state=enforce_recorded_one_shot(args.incident)
    print("NOV14_ALREADY_ATTEMPTED="+str(state["prior_attempted_GET"]))
    print("NOV14_NO_REPEAT_HTTP=TRUE")
    print("NOV14_RETRY_BLOCKED="+state["status"])
    return state

if __name__=="__main__":
    main()
