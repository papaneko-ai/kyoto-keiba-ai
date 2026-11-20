"""Impl26 GitHub metadata-to-INC converter. No JRA HTTP and no secrets."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

WORKFLOW = "Kyoto Nov21-22 independent encrypted original collection"
STATES = {"NOT_TRIGGERED", "PRE_HTTP_STOP", "HTTP_FAILURE", "PARTIAL_SAVED",
          "SOURCE_BYTES_SAVED", "STRUCTURED_FIELDS_VERIFIED", "BOTH_MARKETS_VERIFIED",
          "SEALING_FAILED", "UNKNOWN"}
ORDER = ("DETECTED", "EVIDENCE_LOCKED", "ROOT_CAUSE_CANDIDATE", "ROOT_CAUSE_PROVED",
         "CANDIDATE_PATCH", "OFFLINE_REGRESSION_PASSED", "APPROVED_FOR_PRODUCTION",
         "LIVE_RECHECK", "CLOSED")
LANES = {"pc-originals-independent": "PC", "sp-originals-independent": "SP"}

def stable_id(day, run_id, lane, stage):
    key = f"{day}|{run_id or 'NO_RUN'}|{lane}|{stage}".encode()
    return f"INC-{day}-{run_id or 'NO-RUN'}-{hashlib.sha256(key).hexdigest()[:12]}"

def classify(run, jobs, artifacts, *, day, scheduled_utc=None):
    if day not in ("20261121", "20261122"):
        raise ValueError("out_of_scope_day")
    if run is not None and (run.get("name") != WORKFLOW or
        run.get("created_at", "")[:10].replace("-", "") != day):
        raise ValueError("wrong_workflow_or_day")
    job_list = jobs.get("jobs", [])
    names = {a.get("name") for a in artifacts.get("artifacts", []) if not a.get("expired")}
    run_id = run.get("id") if run else None
    events = []
    if run is None:
        events.append(("ALL", "NOT_TRIGGERED", "R01", "No workflow run was observed for the scheduled slot", None))
    else:
        for job_name, lane in LANES.items():
            match = [j for j in job_list if j.get("name") == job_name]
            if not match:
                events.append((lane, "UNKNOWN", "R09", "Lane job absent from run metadata", None))
                continue
            job = match[0]
            failed = [s for s in job.get("steps", []) if s.get("conclusion") == "failure"]
            upload = f"kyoto-{lane.lower()}-{run_id}-{day}" in names
            if failed:
                first = failed[0].get("name", "UNKNOWN_STEP")
                state = "SEALING_FAILED" if "seal" in first.lower() or "upload" in first.lower() else "UNKNOWN"
                risk = "R31" if state == "SEALING_FAILED" else "R02"
                events.append((lane, state, risk, "Failed step: " + first[:120], first[:120]))
            if job.get("conclusion") in ("failure", "cancelled", "timed_out") and not failed:
                events.append((lane, "UNKNOWN", "R39", "Job ended without a failing step receipt", None))
            if not upload:
                events.append((lane, "UNKNOWN", "R31", "Encrypted evidence artifact not found", "Artifact upload"))
    for lane, state, risk, symptom, step in events:
        assert state in STATES
        incident = {
            "incident_id": stable_id(day, run_id, lane, state + (step or "")),
            "first_seen_utc": datetime.now(timezone.utc).isoformat(),
            "day": day, "run_id": run_id, "job_id": next(
                (j.get("id") for j in job_list if LANES.get(j.get("name")) == lane), None),
            "step": step, "channel": lane, "race_numbers": [], "horse_numbers": [],
            "market_types": [], "planned_utc": scheduled_utc,
            "actual_start_utc": run.get("run_started_at") if run else None,
            "failed_at_utc": None, "error_class": None, "failure_stage": state,
            "symptom": symptom, "source_file_sha256": None, "artifact_id": None,
            "source_timestamp_utc": None, "safe_stop_state": state,
            "data_preserved": "UNKNOWN", "data_missing": "UNKNOWN",
            "risk_ids": [risk], "root_cause_status": "UNKNOWN",
            "root_cause_evidence": [], "same_cause_search": "PENDING",
            "repair_branch": None, "repair_commit": None, "reproduction_test": None,
            "regression_ci_run": None, "production_approval": None, "rollback_sha": None,
            "post_fix_real_event_check": None, "recurrence_count": 0,
            "closure_evidence": None, "status": "DETECTED"
        }
        yield incident

def run_cli():
    p = argparse.ArgumentParser()
    p.add_argument("--day", required=True)
    p.add_argument("--run")
    p.add_argument("--jobs", required=True)
    p.add_argument("--artifacts", required=True)
    p.add_argument("--scheduled-utc")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    def read(path):
        return json.loads(Path(path).read_text()) if path else None
    data = list(classify(read(a.run), read(a.jobs), read(a.artifacts),
                         day=a.day, scheduled_utc=a.scheduled_utc))
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text(json.dumps({
        "schema":"kyoto_impl26_incidents.v1", "source":"GITHUB_METADATA_ONLY",
        "incidents":data, "actual_source_verification":"NOT_ASSESSED",
        "raw_secrets_included":False, "approval_required_for_changes":True
    }, sort_keys=True, indent=2) + "\n")
    print(f"INC_METADATA_TRIAGE_COMPLETE count={len(data)}")
if __name__ == "__main__":
    run_cli()
