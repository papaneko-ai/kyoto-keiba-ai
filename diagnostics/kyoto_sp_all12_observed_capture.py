"""Capture each unique SP Kyoto race anchor actually saved by discovery.

No PC-derived URL, no synthetic token and no network from receipt-only hints.
Every race owns its failure, while completed raw bytes are flattened for AES.
"""
from __future__ import annotations
import json
import time
import re
from hashlib import sha256
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from pathlib import Path
from diagnostics.kyoto_weekend_sp_discovery import observed_kyoto_race_candidates, OFFICIAL_OBSERVED_NOV22_R1
from diagnostics.kyoto_sp_observed_source import capture_verified_sp_seed


def _verified_archived_sunday_r1(raw, source, item, day):
    """Classify a saved *already-fetched* R1 original without a second GET.

    Do not treat a matching URL alone as evidence: require the exact saved
    hash, UTC, Kyoto identity, target date, race number and racecard headings.
    No market or complete-roster claim is made by this minimum check.
    """
    if day!="20261122" or source!=OFFICIAL_OBSERVED_NOV22_R1:
        return False
    try:
        stamp=datetime.fromisoformat(item["captured_at_utc"].replace("Z","+00:00"))
        if stamp.utcoffset()!=timezone.utc.utcoffset(None):
            return False
        if stamp.date().strftime("%Y%m%d")!=day:
            return False
    except (KeyError,ValueError,TypeError):
        return False
    try:
        text=raw.decode("utf-8")
    except UnicodeError:
        text=raw.decode("cp932",errors="replace")
    visible=" ".join(BeautifulSoup(text,"html.parser").stripped_strings)
    return bool(
        re.search(r"2026\s*年\s*11\s*月\s*22\s*日",visible)
        and "京都" in visible
        and re.search(r"(?<![0-9])0?1\s*(?:R|レース)(?![0-9])",visible,re.I)
        and "出馬表" in visible
        and "馬番" in visible and "馬名" in visible
    )


def capture_all(root, *, day, opener, pacer, deadline_monotonic=None, monotonic=time.monotonic, race_order=None):
    root = Path(root)
    receipt_path = root / "sp_discovery_receipt.json"
    discovery = json.loads(receipt_path.read_text(encoding="utf8"))
    if discovery.get("day") != day or not isinstance(discovery.get("attempts"), list):
        raise ValueError("discovery_receipt_day_or_shape_invalid")
    candidates = {str(n): set() for n in range(1, 13)}
    verified_reusable = {}
    for item in discovery["attempts"]:
        if not isinstance(item, dict) or "file" not in item:
            continue
        filename = item["file"]
        if not isinstance(filename, str) or not filename.startswith("official_sp_discovery_") or not filename.endswith(".html") or "/" in filename or "\\" in filename:
            raise ValueError("invalid_discovery_file_reference")
        page = root / filename
        if not page.is_file() or page.is_symlink():
            raise ValueError("missing_saved_discovery_page")
        raw = page.read_bytes()
        if sha256(raw).hexdigest() != item.get("sha256"):
            raise ValueError("discovery_original_sha_mismatch")
        if _verified_archived_sunday_r1(raw,item["url"],item,day):
            verified_reusable[item["url"]] = (raw,item)
            candidates["1"].add(item["url"])
        for number, urls in observed_kyoto_race_candidates(raw, item["url"], day).items():
            candidates[number].update(urls)
    order=list(range(1,13)) if race_order is None else list(race_order)
    if any(type(n) is not int for n in order) or sorted(order)!=list(range(1,13)):
        raise ValueError("invalid_sp_race_order")
    outcomes = {}
    for number in order:
        urls = candidates[str(number)]
        if deadline_monotonic is not None and monotonic() >= deadline_monotonic:
            outcomes[str(number)] = {"state": "DEFERRED_FOR_AES_SEALING_BUDGET", "candidate_count": len(urls), "racecard_fetched": False}
            continue
        if len(urls) != 1:
            outcomes[str(number)] = {"state": "NO_UNIQUE_SAVED_OFFICIAL_SP_ANCHOR", "candidate_count": len(urls), "racecard_fetched": False}
            continue
        staging = root / f"sp_stage_{number:02d}"
        staging.mkdir(exist_ok=False)
        try:
            exact_url=next(iter(urls))
            if number==1 and exact_url in verified_reusable:
                raw, archived = verified_reusable[exact_url]
                (staging/"official_sp_racecard.html").write_bytes(raw)
                metadata={
                    "schema":"kyoto_sp_existing_official_r1.v1",
                    "state":"SP_SAVED_R1_ORIGINAL_REUSED_ROSTER_UNVERIFIED",
                    "channel":"SP","day":day,"race_number":1,
                    "racecard_fetched":True,
                    "racecard_sha256":sha256(raw).hexdigest(),
                    "racecard_captured_at_utc":archived["captured_at_utc"],
                    "observed_source_url":exact_url,
                    "network_requests_started":0,
                    "both_markets_verified":False,
                    "prediction_ready":False,
                    "real_racecard_verified":False
                }
                (staging/"sp_receipt.json").write_text(
                    json.dumps(metadata,ensure_ascii=False,sort_keys=True)+"\n",
                    encoding="utf8")
                result=metadata
            else:
                result = capture_verified_sp_seed(staging, race_day=day, race_number=number,
                                                  source_url=exact_url, opener=opener,
                                                  pacer=pacer, include_odds=True)
            outcomes[str(number)] = {"state": result["state"], "network_requests_started": result.get("network_requests_started", 0),
                                     "racecard_fetched": result.get("racecard_fetched", False),
                                     "sp_market_state": result.get("sp_market_state", "NOT_ATTEMPTED")}
        except Exception as exc:
            outcomes[str(number)] = {"state": "SP_RACE_EXCEPTION", "error_class": type(exc).__name__, "racecard_fetched": False}
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
