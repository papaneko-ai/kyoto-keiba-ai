"""Audit already-archived horse-profile source bytes against P1's immutable registry.

Read-only, offline and historic: locating matching bytes is NOT reparsing HTML,
JRA-authenticity attestation, or pre-race prediction authorization.
"""
import argparse
import hashlib
import json
from pathlib import Path

MAX_FILES = 5000
MAX_BYTES = 1_800_000


def audit(registry, root):
    if not isinstance(registry, list) or len(registry) != 148:
        raise ValueError("expected_148_historical_rows")
    target = {}
    pending = 0
    for row in registry:
        if not isinstance(row, dict):
            raise ValueError("invalid_registry_row")
        state = row.get("source_coverage", {}).get("horse_profile")
        key = f"{row.get('race_number')}:{row.get('horse_number')}"
        if key in target:
            raise ValueError("duplicate_registry_identity")
        if state == "NOT_QUERIED":
            if row.get("profile_source_sha256"):
                raise ValueError("unqueried_has_original_hash")
            pending += 1
            continue
        if state not in ("VERIFIED_SOURCE_ROWS", "VERIFIED_EMPTY_HISTORY"):
            raise ValueError("unrecognized_profile_state")
        h = row.get("profile_source_sha256")
        if not isinstance(h, str) or len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
            raise ValueError("invalid_original_hash")
        target[key] = h
    if len(target) != 96 or pending != 52:
        raise ValueError("historic_registry_totals_mismatch")
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("invalid_archive_root")
    index = {}
    seen = 0
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in (".html", ".htm"):
            continue
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError("unsafe_source_candidate")
        seen += 1
        if seen > MAX_FILES:
            raise ValueError("candidate_limit_exceeded")
        size = path.stat().st_size
        if size <= 0 or size > MAX_BYTES:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in target.values():
            index.setdefault(digest, []).append(path.relative_to(root).as_posix())
    found = {}
    absent = []
    for key, digest in sorted(target.items()):
        locations = index.get(digest, [])
        if not locations:
            absent.append({"horse_identity": key, "expected_source_sha256": digest})
        else:
            found[key] = {"sha256": digest, "paths": locations}
    return {
        "schema": "kyoto_p1_historical_raw_original_availability.v1",
        "historical_race_date": "2026-11-07",
        "target_profile_count": 96,
        "matched_profile_count": len(found),
        "missing_profile_count": len(absent),
        "original_candidate_files_examined": seen,
        "matched": found, "missing": absent,
        "status": "ORIGINAL_BYTES_PRESENT_NOT_REPARSED" if not absent else "RAW_ORIGINALS_INCOMPLETE",
        "prediction_ready": False,
        "network_requests": 0,
        "not_verified": ["source_JRA_authenticity", "html_reparse", "independent_capture_clock", "live_prediction"]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    parser.add_argument("raw_directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = json.loads(args.registry.read_text(encoding="utf-8"))
    result = audit(rows, args.raw_directory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{result['status']} matched={result['matched_profile_count']}/96, no JRA requests")


if __name__ == "__main__":
    main()
