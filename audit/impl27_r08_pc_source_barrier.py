"""R08 GitHub-metadata barrier: permit SP HTTP only after PC source HTTP ended.

This runs in the SP job using an independently checked-out workflow commit.
No JRA requests, no Turso mutations, no access to plaintext originals.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from urllib.request import Request, urlopen

PC_JOB = "pc-originals-independent"
PC_SOURCE_STEP = "Capture official PC observed originals (bounded no guessed URLs)"

class BarrierBlocked(RuntimeError):
    pass

def classify(jobs):
    """Returns (decision, evidence), with no optimistic fallback."""
    if not isinstance(jobs, list):
        return "BLOCK", "job_list_invalid"
    pc = [j for j in jobs if isinstance(j, dict) and j.get("name") == PC_JOB]
    if len(pc) != 1:
        return "WAIT", "pc_job_unavailable_or_ambiguous"
    job = pc[0]
    steps = [s for s in job.get("steps", []) if
             isinstance(s, dict) and s.get("name") == PC_SOURCE_STEP]
    if len(steps) != 1:
        return "BLOCK", "pc_source_step_absent_or_ambiguous"
    step = steps[0]
    # A completed PC request step is the last JRA HTTP operation in that job.
    # Later proof, encryption and artifact steps do not make JRA HTTP requests.
    if step.get("status") == "completed" and step.get("conclusion") in ("success", "failure"):
        if not isinstance(step.get("completed_at"), str) or not step["completed_at"].endswith("Z"):
            return "BLOCK", "pc_end_timestamp_missing"
        return "ALLOW", "pc_source_step_completed"
    # A step skipped due to a failed PC preflight started no source HTTP.
    # It is safe only once the entire PC job has terminated.
    if (step.get("conclusion") == "skipped"
        and job.get("status") == "completed"
        and job.get("conclusion") in ("success", "failure")):
        return "ALLOW", "pc_source_step_never_executed"
    if job.get("status") == "completed":
        return "BLOCK", "pc_source_outcome_ambiguous"
    return "WAIT", "pc_source_still_possible"

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--wait-seconds", type=int, default=1190)
    args = parser.parse_args(argv)
    if (not args.repo or "/" not in args.repo or
        not args.run_id.isdecimal() or not 30 <= args.wait_seconds <= 1200):
        raise SystemExit("R08_METADATA_INPUT_INVALID_NO_SP_HTTP")
    token = os.environ.get("GH_TOKEN", "")
    if len(token) < 10:
        raise SystemExit("R08_GITHUB_TOKEN_MISSING_NO_SP_HTTP")
    url = f"https://api.github.com/repos/{args.repo}/actions/runs/{args.run_id}/jobs?per_page=100"
    deadline = time.monotonic() + args.wait_seconds
    last = "not_observed"
    while time.monotonic() < deadline:
        req = Request(url, headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "User-Agent": "kyoto-r08-readonly-barrier",
        })
        try:
            with urlopen(req, timeout=10) as response:
                body = json.load(response)
            jobs = body.get("jobs")
            # A truncated first page is insufficient to identify the PC job.
            if not isinstance(body.get("total_count"), int) or body["total_count"] > 100:
                raise BarrierBlocked("R08_JOB_SET_INCOMPLETE")
            decision, last = classify(jobs)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise SystemExit("R08_GITHUB_METADATA_UNAVAILABLE_NO_SP_HTTP") from None
        if decision == "ALLOW":
            print("R08_PC_SOURCE_BOUNDARY_PROVED", last, flush=True)
            return 0
        if decision == "BLOCK":
            raise SystemExit("R08_PC_SOURCE_UNVERIFIED_NO_SP_HTTP:" + last)
        time.sleep(4)
    raise SystemExit("R08_WAIT_TIMEOUT_NO_SP_HTTP:" + last)

if __name__ == "__main__":
    main()
