"""Capture each unique SP Kyoto race anchor actually saved by discovery.

No PC-derived URL, no synthetic token and no network from receipt-only hints.
Every race owns its failure, while completed raw bytes are flattened for AES.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from diagnostics.kyoto_weekend_sp_discovery import observed_kyoto_race_candidates
from diagnostics.kyoto_sp_observed_source import capture_verified_sp_seed


def capture_all(root, *, day, opener, pacer, deadline_monotonic=None, monotonic=time.monotonic):
    root = Path(root)
    receipt_path = root / "sp_discovery_receipt.json"
    discovery = json.loads(receipt_path.read_text(encoding="utf8"))
    if discovery.get("day") != day or not isinstance(discovery.get("attempts"), list):
        raise ValueError("discovery_receipt_day_or_shape_invalid")
    candidates = {str(n): set() for n in range(1, 13)}
    for item in discovery["attempts"]:
        if not isinstance(item, dict) or "file" not in item:
            continue
        filename = item["file"]
        if not isinstance(filename, str) or not filename.startswith("official_sp_discovery_") or not filename.endswith(".html") or "/" in filename or "\\" in filename:
            raise ValueError("invalid_discovery_file_reference")
        page = root / filename
        if not page.is_file() or page.is_symlink():
            raise ValueError("missing_saved_discovery_page")
        from hashlib import sha256
        raw = page.read_bytes()
        if sha256(raw).hexdigest() != item.get("sha256"):
            raise ValueError("discovery_original_sha_mismatch")
        for number, urls in observed_kyoto_race_candidates(raw, item["url"], day).items():
            candidates[number].update(urls)
    outcomes = {}
    for number in range(1, 13):
        urls = candidates[str(number)]
        if deadline_monotonic is not None and monotonic() >= deadline_monotonic:
            outcomes[str(number)] = {"state": "DEFERRED_FOR_AES_SEALING_BUDGET", "candidate_count": len(urls)}
            continue
        if len(urls) != 1:
            outcomes[str(number)] = {"state": "NO_UNIQUE_SAVED_OFFICIAL_SP_ANCHOR", "candidate_count": len(urls)}
            continue
        staging = root / f"sp_stage_{number:02d}"
        staging.mkdir(exist_ok=False)
        try:
            result = capture_verified_sp_seed(staging, race_day=day, race_number=number,
                                              source_url=next(iter(urls)), opener=opener,
                                              pacer=pacer, include_odds=True)
            outcomes[str(number)] = {"state": result["state"], "network_requests_started": result.get("network_requests_started", 0),
                                     "racecard_fetched": result.get("racecard_fetched", False),
                                     "sp_market_state": result.get("sp_market_state", "NOT_ATTEMPTED")}
        except Exception as exc:
            outcomes[str(number)] = {"state": "SP_RACE_EXCEPTION", "error_class": type(exc).__name__}
        finally:
            for item in sorted(staging.iterdir()):
                if not item.is_file() or item.is_symlink():
                    raise ValueError("unsafe_sp_stage_entry")
                target = root / f"r{number:02d}_{item.name}"
                if target.exists() or target.is_symlink():
                    raise ValueError("sp_race_archive_collision")
                item.rename(target)
            staging.rmdir()
    report = {"schema": "kyoto_sp_saved_anchor_all12.v1", "day": day, "races": outcomes,
              "source_only": True, "both_markets_verified": False,
              "prediction_ready": False, "all_twelve_races_verified": False}
    (root / "sp_all12_receipt.json").write_text(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    return report
