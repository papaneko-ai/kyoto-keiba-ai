"""Evidence-only all-run inventory for 2026 Nov21/22 production observations.

Never confuse GitHub job/artifact success with authenticated JRA source.
This module uses normalized GitHub API metadata; no JRA HTTP or database writes.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

NAME = "Kyoto Nov21-22 independent encrypted original collection"
DAYS = ("20261121", "20261122")
LANES = ("pc-originals-independent", "sp-originals-independent")


def summarize(day, runs, details):
    if day not in DAYS:
        raise ValueError("DAY_NOT_IN_SCOPE")
    if not isinstance(runs, list) or not isinstance(details, dict):
        raise ValueError("INVALID_INPUT_TYPES")
    selected = []
    ids = set()
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("INVALID_RUN")
        stamp = f"{day[:4]}-{day[4:6]}-{day[6:]}"
        if not str(run.get("created_at", "")).startswith(stamp):
            continue
        if run.get("name") != NAME:
            raise ValueError("WRONG_WORKFLOW_IN_DATE")
        if run.get("event") not in ("schedule", "workflow_dispatch"):
            raise ValueError("UNEXPECTED_EVENT")
        rid = run.get("id")
        if type(rid) is not int or rid <= 0 or rid in ids:
            raise ValueError("DUPLICATE_OR_INVALID_RUN_ID")
        ids.add(rid)
        entry = {"run_id": rid, "created_at": run["created_at"],
                 "event": run["event"], "status": run.get("status"),
                 "conclusion": run.get("conclusion"),
                 "source_claim": "NOT_AUTHENTICATED_BY_METADATA",
                 "lanes": {}}
        data = details.get(str(rid))
        if run.get("status") == "completed" and not isinstance(data, dict):
            entry["detail_state"] = "COMPLETED_RUN_DETAILS_MISSING"
        elif isinstance(data, dict):
            jobs = data.get("jobs")
            artifacts = data.get("artifacts")
            if not isinstance(jobs, list) or not isinstance(artifacts, list):
                raise ValueError("INVALID_RUN_DETAILS")
            for lane in LANES:
                matches = [j for j in jobs if isinstance(j, dict) and j.get("name") == lane]
                artifact_name = f"kyoto-{'pc' if lane.startswith('pc-') else 'sp'}-{rid}-{day}"
                matched = [a for a in artifacts if isinstance(a, dict)
                           and a.get("name") == artifact_name and a.get("expired") is False]
                entry["lanes"][lane] = {
                    "job_state": (matches[0].get("conclusion") if len(matches) == 1
                                  else "MISSING_OR_DUPLICATE_JOB"),
                    "encrypted_artifact_metadata_present": len(matched) == 1,
                    "artifact_state": ("METADATA_ONLY_CONTENT_UNVERIFIED" if len(matched) == 1
                                       else "MISSING_OR_DUPLICATE_ARTIFACT"),
                    "g03_g04_g05_g06_per_race_coverage_verified": False}
            entry["detail_state"] = "METADATA_INSPECTED_NOT_SOURCE_PROOF"
        selected.append(entry)
    selected.sort(key=lambda r: (r["created_at"], r["run_id"]))
    return {"schema": "kyoto_impl25_all_observation_runs.v1",
            "day": day, "runs_found": len(selected), "runs": selected,
            "all_runs_in_api_page_confirmed": len(runs) < 100,
            "g03_g04_g05_g06_all_race_evidence_verified": False,
            "sp_full_twelve_races_verified": False,
            "auxiliary_independent_workout_source_verified": False,
            "source_success_from_job_or_artifact_metadata": False,
            "day22_automatic_new_sha_promotion_allowed": False,
            "requires_individual_aes_original_and_sha_utc_inspection": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", required=True, choices=DAYS)
    parser.add_argument("--runs", required=True, type=Path)
    parser.add_argument("--details", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    runs = json.loads(args.runs.read_text(encoding="utf8"))["workflow_runs"]
    details = json.loads(args.details.read_text(encoding="utf8"))
    report = summarize(args.day, runs, details)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True,
                              indent=2) + "\n", encoding="utf8")
    print(f"OBSERVATION_RUNS_INVENTORIED={report['runs_found']}; "
          "NOT_SOURCE_AUTHENTICATION")


if __name__ == "__main__":
    main()
