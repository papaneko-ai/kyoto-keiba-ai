"""Identify which Nov15 encrypted observation artifact belongs to a verified GitHub Run.

This is a GitHub-only preflight. Authentication of encrypted contents is separate;
neither a successful workflow nor this identity check proves JRA source authenticity.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone

class ObservationRunRejected(ValueError):
    pass

LAUNCHER="Kyoto Nov15 unattended encrypted official observer launcher"
LEGACY="Kyoto Nov15 gated official links observation encrypted originals"

def artifact_name(run, *, run_id):
    if type(run) is not dict or not str(run_id).isdigit():
        raise ObservationRunRejected("run_identity_missing")
    if str(run.get("id"))!=str(run_id):
        raise ObservationRunRejected("run_id_mismatch")
    if run.get("status")!="completed" or run.get("conclusion")!="success":
        raise ObservationRunRejected("run_not_completed_successfully")
    name=run.get("name")
    if name==LAUNCHER:
        branch="main"
        valid_events=("schedule",)
        prefix="kyoto-nov15-unattended-encrypted-observation-"
        dates=("2026-11-15",)
    elif name==LEGACY:
        branch="jra-html-diagnostic-20261105"
        valid_events=("push","workflow_dispatch")
        prefix="kyoto-nov15-encrypted-observation-"
        dates=("2026-11-12","2026-11-13","2026-11-14","2026-11-15")
    else:
        raise ObservationRunRejected("unrecognized_observer_workflow")
    if run.get("head_branch")!=branch or run.get("event") not in valid_events:
        raise ObservationRunRejected("observer_branch_or_event_invalid")
    created=run.get("created_at")
    if not isinstance(created,str) or not created.startswith(dates):
        raise ObservationRunRejected("observer_created_date_outside_window")
    return prefix+str(run_id)

def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("--run-id",required=True)
    args=ap.parse_args(argv)
    try:
        run=json.load(__import__("sys").stdin)
        print(artifact_name(run,run_id=args.run_id))
    except (ValueError,TypeError,KeyError) as exc:
        raise SystemExit("NOV15_OBSERVER_RUN_IDENTITY_NOT_ACCEPTED_NO_HTTP") from exc

if __name__=="__main__":main()
