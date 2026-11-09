"""Fail-closed Kyoto AI resume gate; no network and no repository mutations.

The gate prevents ignoring already-known recoverable source artifacts. An API
response must be provided separately for any claim of current availability.
"""
import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path


class ResumeBlocked(ValueError):
    pass


def blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check(root, manifest, *, artifact_metadata=None, local_recovery=None, at_utc=None):
    root = Path(root)
    if at_utc is None:
        at_utc = datetime.now(timezone.utc)
    if at_utc.tzinfo is None:
        raise ResumeBlocked("clock_not_timezone_aware")
    if manifest.get("schema") != "kyoto_ai_resume_evidence_registry.v1":
        raise ResumeBlocked("registry_schema_invalid")
    files = manifest.get("required_files")
    if not isinstance(files, dict) or len(files) < 5:
        raise ResumeBlocked("required_file_catalog_incomplete")
    for name, sha in files.items():
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts or not isinstance(sha, str):
            raise ResumeBlocked("unsafe_registry_path")
        p = root / rel
        if not p.is_file() or p.is_symlink() or blob_sha(p.read_bytes()) != sha:
            raise ResumeBlocked("source_missing_or_changed:" + name)
    status = _json(root / manifest["status_path"])
    rows = _json(root / manifest["registry_path"])
    proof = _json(root / manifest["real_original_replay_path"])
    if len(rows) != 148 or status.get("runner_count") != 148:
        raise ResumeBlocked("horse_count_changed")
    counts = {"VERIFIED_SOURCE_ROWS": 0, "VERIFIED_EMPTY_HISTORY": 0, "NOT_QUERIED": 0}
    total_prior = 0
    identities = set()
    for row in rows:
        key = (row["race_number"], row["horse_number"])
        if key in identities:
            raise ResumeBlocked("duplicated_horse_identity")
        identities.add(key)
        state = row["source_coverage"]["horse_profile"]
        if state not in counts:
            raise ResumeBlocked("unknown_horse_state")
        counts[state] += 1
        total_prior += (row.get("performance_features") or {}).get("prior_valid_finishes_available", 0)
        if row.get("prediction_ready") is not False or row.get("training_ready") is not False:
            raise ResumeBlocked("historical_horse_promoted")
    if (counts != {"VERIFIED_SOURCE_ROWS": 77, "VERIFIED_EMPTY_HISTORY": 19, "NOT_QUERIED": 52}
            or total_prior != 592 or status.get("profile_details_source_verified") != 96
            or status.get("detailed_profiles_unqueried") != 52
            or status.get("total_finished_prior_rows") != 592
            or status.get("prediction_ready") is not False
            or status.get("training_ready") is not False):
        raise ResumeBlocked("p1_frozen_checkpoint_conflict")
    evidence = proof.get("observed", {})
    required = {"pc_profile_sha_matches": 84, "source_originals_missing": 12,
                "valid_prior_rows_reparsed": 485,
                "valid_prior_rows_missing_sources_registry_only": 107,
                "feature_fields_independently_recomputed_and_equal": 335}
    if any(evidence.get(k) != v for k, v in required.items()):
        raise ResumeBlocked("original_replay_receipt_conflict")
    recovery = manifest.get("recovery_artifact", {})
    if (recovery.get("id") != proof.get("artifact", {}).get("artifact_id")
            or recovery.get("run_id") != proof.get("artifact", {}).get("workflow_run_id")
            or recovery.get("sha256") != proof.get("artifact", {}).get("outer_archive_sha256")):
        raise ResumeBlocked("recovery_artifact_not_reconciled")
    if proof.get("prediction_ready") is not False or proof.get("training_ready") is not False:
        raise ResumeBlocked("replay_incorrectly_promoted")
    expires = datetime.fromisoformat(recovery["expires_at"].replace("Z", "+00:00"))
    if at_utc >= expires:
        availability = "EXPIRED_OR_REQUIRES_INDEPENDENT_LOCAL_BACKUP"
    elif artifact_metadata is None:
        availability = "NOT_CHECKED_AT_RESUME"
    else:
        if (artifact_metadata.get("id") != recovery["id"]
                or artifact_metadata.get("expired") is not False
                or artifact_metadata.get("digest") != "sha256:" + recovery["sha256"]
                or artifact_metadata.get("expires_at") != recovery["expires_at"]):
            raise ResumeBlocked("live_artifact_metadata_conflict")
        availability = "CONFIRMED_BY_SUPPLIED_GITHUB_API_RESPONSE"
    if local_recovery is not None:
        backup = Path(local_recovery)
        expected_sha = manifest.get("portable_recovery", {}).get("sha256")
        if not backup.is_file() or hashlib.sha256(backup.read_bytes()).hexdigest() != expected_sha:
            raise ResumeBlocked("portable_recovery_sha_invalid")
        with zipfile.ZipFile(backup) as zf:
            if zf.testzip() is not None:
                raise ResumeBlocked("portable_recovery_zip_invalid")
        availability = "LOCAL_RECOVERY_BYTES_VERIFIED"
    blocked = availability not in ("CONFIRMED_BY_SUPPLIED_GITHUB_API_RESPONSE", "LOCAL_RECOVERY_BYTES_VERIFIED")
    return {"schema": "kyoto_ai_resume_gate_result.v1",
            "decision": "BLOCK_NEW_IMPLEMENTATION" if blocked else "RESUME_EVIDENCE_ACCEPTED_NOT_LIVE_AUTHORIZATION",
            "artifact_availability": availability,
            "must_inspect_existing_artifact_before_new_work": True,
            "preserved_recovery_artifact_id": recovery["id"],
            "already_reparsed_profiles": 84,
            "original_profiles_missing": 12,
            "already_reparsed_prior_runs": 485,
            "registry_only_prior_runs": 107,
            "old_total_prior_runs": 592,
            "verified_feature_fields": 335,
            "remaining_unqueried_horses": 52,
            "no_repeat_of_prior_official_gets": True,
            "live_JRA_http_authorized": False,
            "new_prediction_ready": False,
            "next_work": "P1 LEGAL NEW MEETING OFFICIAL RACE CARD AND PRE-RACE ODDS; DO NOT REPEAT NOV-6 ARCHIVE DISCOVERY"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--registry", type=Path, default=Path("docs/diagnostics/kyoto_ai_resume_evidence_registry_v1.json"))
    p.add_argument("--artifact-json", type=Path)
    p.add_argument("--local-recovery", type=Path)
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    manifest = _json(args.root / args.registry)
    metadata = _json(args.artifact_json) if args.artifact_json else None
    result = check(args.root, manifest, artifact_metadata=metadata, local_recovery=args.local_recovery)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    if result["decision"] == "BLOCK_NEW_IMPLEMENTATION":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
