"""Two-day, two-lane source observation. Never fabricate official JRA URLs.

PC and SP run in separate jobs with separate raw directories and proofs.  The
SP lane requires an independently observed current-day official SP URL.
Production is strictly bounded, read-only, source-only; no wagers or prediction.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.request import HTTPCookieProcessor, build_opener

from diagnostics.kyoto_safe_stop_artifact import record_pre_http_stop

DAYS = {"20261121", "20261122"}
CHANNELS = {"PC", "SP"}
SUCCESS_PC = {
    "NOV15_MEETING_ORIGINALS_OBSERVED_NOT_RACECARD",
    "NOV15_RACECARD_ORIGINAL_OBSERVED_ROSTER_UNVERIFIED",
}


def validate_day(day: str, *, live: bool) -> None:
    if day not in DAYS:
        raise ValueError("unsupported_target_day")
    if live and datetime.now(timezone.utc).strftime("%Y%m%d") != day:
        raise ValueError("not_target_utc_day_zero_http")


def _write_receipt(root: Path, details: dict) -> None:
    target = root / "receipt.json"
    with target.open("x", encoding="utf8") as file:
        json.dump(details, file, sort_keys=True, ensure_ascii=False, indent=2)
        file.write("\n")


def _no_claim(day: str, channel: str, state: str, **other) -> dict:
    return dict(
        schema="kyoto_weekend_source_lane.v1",
        day=day, channel=channel, state=state,
        source_only=True, real_racecard_verified=False,
        both_markets_verified=False, prediction_ready=False,
        paper_trade_authorized=False, real_wager_authorized=False,
        **other,
    )


def capture(day: str, channel: str, output: str, *, live: bool,
            sp_source_url: str = "", opener=None) -> dict:
    """Fail closed before network unless today's explicit runtime conditions hold."""
    validate_day(day, live=live)
    if os.getenv("KYOTO_TARGET_DAY") != day:
        raise ValueError("capture_day_binding_invalid_zero_http")
    if channel not in CHANNELS:
        raise ValueError("invalid_channel")
    root = Path(output)
    if root.exists() or root.is_symlink() or not root.parent.is_dir():
        raise ValueError("capture_root_not_fresh")
    if not live and opener is None:
        raise ValueError("offline_mock_opener_required")
    if live and os.getenv("GITHUB_EVENT_NAME") not in ("schedule", "workflow_dispatch"):
        raise ValueError("unapproved_live_event")
    if live and os.getenv("GITHUB_RUN_ATTEMPT") != "1":
        raise ValueError("rerun_forbidden_zero_http")
    if live and os.getenv("KYOTO_WEEKEND_HTTP_APPROVED") != "YES":
        raise ValueError("explicit_live_approval_missing_zero_http")
    if live and not re.fullmatch(r"[0-9a-fA-F]{64}",os.getenv("ARCHIVE_KEY","")):
        raise ValueError("archive_key_missing_zero_http")
    root.mkdir()
    if channel == "PC":
        from diagnostics.kyoto_nov15_two_original_observer import observe
        try:
            result = observe(
                root / "pc_originals", now_utc=datetime.now(timezone.utc).isoformat(),
                opener=opener, allowed=True, include_observed_racecard=True,
                include_observed_odds_menu=True)
            # Preserve the full observer receipt with every actual SHA, URL and
            # UTC timestamp. A separate summary is returned to the job log only.
            out = _no_claim(day, channel, result["state"],
                            observed_http_requests_started=result["http_requests_started"],
                            captured_originals=bool(result.get("selection_sha256")))
            for original in (root / "pc_originals").iterdir():
                if original.is_file():
                    original.rename(root / original.name)
            (root / "pc_originals").rmdir()
            return out
        except Exception as exc:
            out = _no_claim(day, channel, "PC_CAPTURE_EXCEPTION",
                            error_class=type(exc).__name__)
            if not (root / "receipt.json").exists():
                _write_receipt(root, out)
            return out
    from diagnostics.kyoto_sp_observed_source import capture_verified_sp_seed
    from diagnostics.kyoto_p1_nov14_official_one_shot_nav import NoRedirect
    # No SP token is generated from PC's CNAME. Runtime supply alone is not
    # an independently verified original: the date/race is checked by parser.
    if not sp_source_url:
        out = _no_claim(day, channel, "SP_OFFICIAL_LINK_NOT_SUPPLIED_ZERO_HTTP",
                        observed_http_requests_started=0)
        _write_receipt(root, out)
        return out
    try:
        client = opener or build_opener(NoRedirect(), HTTPCookieProcessor(CookieJar()))
        result = capture_verified_sp_seed(
            root, race_day=day, race_number=12, source_url=sp_source_url,
            opener=client, include_odds=True)
        out = _no_claim(day, channel, result["state"],
                        observed_http_requests_started=result.get("network_requests_started", 0),
                        captured_originals=bool(result.get("racecard_sha256")),
                        source_discovery_claim="EXTERNAL_INDEPENDENT_SP_LINK_UNVERIFIED_AT_RUNTIME")
    except Exception as exc:
        out = _no_claim(day, channel, "SP_CAPTURE_EXCEPTION",
                        error_class=type(exc).__name__)
    _write_receipt(root, out)
    return out


def seal(day: str, source: str, destination: str, *, key: str, repo: str,
         run_id: str):
    """Encrypt all gathered bytes, including a failed capture receipt.

    No plaintext originals are uploaded. A source-less preflight stop is a
    truthful zero-HTTP JSON artifact; no invented 'success' evidence.
    """
    validate_day(day, live=False)
    src = Path(source)
    dst = Path(destination)
    if dst.exists() or dst.is_symlink() or not dst.parent.is_dir():
        raise ValueError("seal_destination_must_not_exist")
    if not src.is_dir():
        return record_pre_http_stop(dst,race_day=day,reason="CAPTURE_NOT_STARTED")
    # The existing crypto's day binding derives from target-day environment.
    if os.getenv("KYOTO_TARGET_DAY") != day:
        raise ValueError("crypto_day_binding_invalid")
    from diagnostics.kyoto_nov15_encrypted_evidence import encrypt_evidence
    result = encrypt_evidence(src,dst,key_hex=key,repo=repo,run_id=run_id)
    shutil.rmtree(src)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--day", required=True,choices=sorted(DAYS))
    parser.add_argument("--channel",required=True,choices=sorted(CHANNELS))
    parser.add_argument("--source",required=True)
    parser.add_argument("--destination",required=True)
    parser.add_argument("--seal-only",action="store_true")
    args=parser.parse_args()
    if args.seal_only:
        seal(args.day,args.source,args.destination,
             key=os.getenv("ARCHIVE_KEY",""),repo=os.getenv("GITHUB_REPOSITORY",""),
             run_id=os.getenv("GITHUB_RUN_ID",""))
        print("SOURCE_EVIDENCE_SEALED_OR_PRE_HTTP_STOP_RECORDED")
    else:
        rec=capture(args.day,args.channel,args.source,live=True,
                    sp_source_url=os.getenv("SP_INDEPENDENT_OFFICIAL_R12_URL",""))
        print(json.dumps({k:v for k,v in rec.items() if k not in ("source_url",)},
                         sort_keys=True))
if __name__=="__main__":
    main()
