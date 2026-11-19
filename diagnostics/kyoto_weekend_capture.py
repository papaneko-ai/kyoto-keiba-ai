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
    # GitHub rerun is explicit operator action. A previous attempt is not
    # evidence of complete source acquisition: do not suppress recovery.
    if live and os.getenv("KYOTO_WEEKEND_HTTP_APPROVED") != "YES":
        raise ValueError("explicit_live_approval_missing_zero_http")
    if live and not re.fullmatch(r"[0-9a-fA-F]{64}",os.getenv("ARCHIVE_KEY","")):
        raise ValueError("archive_key_missing_zero_http")
    root.mkdir()
    if channel == "PC":
        from diagnostics.kyoto_nov15_two_original_observer import observe
        from diagnostics.kyoto_p1_nov14_official_one_shot_nav import NoRedirect
        from diagnostics.jra_one_shot_market_capture import RequestPacer
        from diagnostics.kyoto_g03_weekend_bridge import collect_after_observer
        pc_client=opener if opener is not None else build_opener(NoRedirect(),HTTPCookieProcessor(CookieJar()))
        pc_pacer=RequestPacer(min_gap_seconds=2.0)
        try:
            result = observe(
                root / "pc_originals", now_utc=datetime.now(timezone.utc).isoformat(),
                opener=pc_client, allowed=True, include_observed_racecard=True,
                include_observed_odds_menu=True, pacer=pc_pacer)
            # Preserve the full observer receipt with every actual SHA, URL and
            # UTC timestamp. A separate summary is returned to the job log only.
            out = _no_claim(day, channel, result["state"],
                            observed_http_requests_started=result["http_requests_started"],
                            captured_originals=bool(result.get("selection_sha256")))
            g03=collect_after_observer(original_root=root / "pc_originals",
                                       day=day,opener=pc_client,pacer=pc_pacer)
            out["g03_all_race_originals_observed"]=bool(g03.get("complete"))
            out["g03_network_requests_started"]=g03.get("network_requests_started",0)
            # G06 starts from exact G03 saved official URLs, named rosters
            # and verified race times. Partial G03 does not cancel the rest.
            # Existing PC opener and pacer are reused; no synthetic SP link.
            out["g06_twelve_race_market_attempted"]=False
            try:
                from diagnostics.kyoto_g03_to_g06_input_adapter import records_from_g03
                from diagnostics.kyoto_g06_all12_capture import run_twelve
                from diagnostics.kyoto_g06_nested_bundle import bundle_g06
                source_inputs=records_from_g03(root/"pc_originals",day=day)
                if any(x is not None for x in source_inputs.values()):
                    g06_root=root/"g06_unsealed"
                    try:
                        from diagnostics.kyoto_weekend_remote_claim_runtime import active_claims_for_weekend
                        claim_context=active_claims_for_weekend(day) if live else {"enabled":False}
                        claim_options={k:v for k,v in claim_context.items()
                           if k in ("claim_client","claim_slot","claim_owner","claim_now_epoch","claim_clock")}
                        markets=run_twelve(g06_root,records=source_inputs,
                            authorized_live_http=live,
                            request_pacer=pc_pacer,openers={"PC":pc_client},
                            **claim_options)
                        # Configuration is not evidence of a completed remote lease.
                        out["g06_shared_claim_state"]=(
                            ("CONFIGURED_PRODUCTION_TURSO" if os.getenv("KYOTO_SHARED_CLAIM_TARGET")=="PRODUCTION"
                             else "CONFIGURED_ISOLATED_TURSO") if claim_context["enabled"]
                            else "OPTIONAL_COORDINATION_NOT_CONFIGURED")
                        if claim_context["enabled"]:
                            from diagnostics.kyoto_g06_claim_evidence import summarize_claims
                            claim_evidence=summarize_claims(markets.get("records",[]), day=day,
                                slot=claim_context["claim_slot"])
                            out["g06_shared_claim_evidence"]=claim_evidence["status"]
                            evidence_path=g06_root/"g06_shared_claim_evidence.json"
                            with evidence_path.open("x",encoding="utf8") as evidence_file:
                                json.dump(claim_evidence,evidence_file,sort_keys=True,indent=2)
                                evidence_file.write("\n")
                        out["g06_twelve_race_market_attempted"]=True
                        out["g06_paired_market_races"]=markets["verified_dual_market_races"]
                        out["g06_markets_prediction_authorized"]=False
                        out["g06_downstream_inbox_created"]=bool(markets.get("downstream_intake_created"))
                    except Exception as exc:
                        out["g06_source_state"]="MARKET_BATCH_EXCEPTION_PARTIAL_ORIGINALS_SAVED"
                        out["g06_error_class"]=type(exc).__name__
                    finally:
                        if g06_root.is_dir():
                            archive=bundle_g06(g06_root,root/"g06_source_bundle.tar.gz")
                            out["g06_nested_originals_sealed_in_parent"]=archive["state"]
            except Exception as exc:
                out["g06_source_state"]="G03_TO_G06_INTEGRATION_NOT_VERIFIED"
                out["g06_error_class"]=type(exc).__name__
            # Independently recheck valid G03 race originals before downstream
            # G04/G05. Full-12 certification is not weakened by this path.
            partial_verified=[]
            try:
                from diagnostics.kyoto_g03_independent_partial import verify_partial
                partial_proof=verify_partial(root/"pc_originals",expected_day=day)
                partial_verified=partial_proof["verified_race_numbers"]
                out["g03_independently_verified_races"]=partial_verified
                out["g03_partial_source_excluded"]=partial_proof["excluded_races"]
            except Exception as exc:
                out["g03_partial_proof_error_class"]=type(exc).__name__
            # G04 follows only independently revalidated G03 originals.
            # Reuse the same official-only, no-redirect and paced GET client.
            # A G04 failure must not discard the successful G03 originals.
            out["g04_all_horse_profiles_parsed"]=False
            if partial_verified:
                try:
                    from diagnostics.kyoto_g04_all_horse_profiles import capture as g04_capture
                    from diagnostics.kyoto_nov15_two_original_observer import _read
                    g04=g04_capture(
                        root=root / "pc_originals",day=day,
                        fetch=lambda url: (pc_pacer.before_request(),_read(pc_client,url))[1],
                        clock=lambda:datetime.now(timezone.utc).isoformat(),allowed=True,
                        allow_partial=not bool(g03.get("complete")))
                    out["g04_all_horse_profiles_parsed"]=bool(g04["all_profiles_parsed"])
                    out["g04_profiles_verified"]=g04["profile_verified_count"]
                    out["g04_profiles_expected"]=g04["expected_horses"]
                except Exception as exc:
                    out["g04_capture_state"]="G04_EXCEPTION_SOURCE_OR_PARSE_BLOCKED"
                    out["g04_error_class"]=type(exc).__name__
            # G05 uses exactly the saved same-day racecards, no new network.
            # Missing or unpublished weather, body weight, workout remain null,
            # never zero/imputed and never a betting authorization.
            out["g05_source_contract_saved"]=False
            if partial_verified:
                try:
                    from diagnostics.kyoto_g05_conditions import compile_saved
                    g05=compile_saved(root / "pc_originals",day=day,
                        allow_partial=not bool(g03.get("complete")))
                    out["g05_source_contract_saved"]=True
                    out["g05_observed_field_values"]=g05["observed_field_values"]
                    out["g05_workout_source_verified"]=False
                except Exception as exc:
                    out["g05_capture_state"]="G05_INCOMPLETE_OR_SOURCE_REJECTED"
                    out["g05_error_class"]=type(exc).__name__
            # The official published Kyoto track page is a separate JRA source.
            # At 09:15 it may still show an earlier meeting; preserve bytes,
            # never promote stale data. Existing shared pacer/no-redirect remains.
            out["g05_kyoto_track_source_saved"]=False
            if partial_verified:
                try:
                    from diagnostics.kyoto_g05_official_track import capture_kyoto_track
                    from diagnostics.kyoto_nov15_two_original_observer import _read
                    track=capture_kyoto_track(
                        root / "pc_originals",day=day,
                        fetch=lambda url: (pc_pacer.before_request(),_read(pc_client,url))[1],
                        clock=lambda:datetime.now(timezone.utc).isoformat(),allowed=True)
                    out["g05_kyoto_track_source_saved"]=True
                    out["g05_same_day_track_heading_verified"]=track[
                        "same_day_official_meeting_heading_verified"]
                except Exception as exc:
                    out["g05_track_capture_state"]="G05_TRACK_SOURCE_UNAVAILABLE_OR_REJECTED"
                    out["g05_track_error_class"]=type(exc).__name__
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
    from diagnostics.jra_one_shot_market_capture import RequestPacer
    shared_sp_pacer=RequestPacer(min_gap_seconds=2.0)
    shared_sp_client=opener or build_opener(NoRedirect(), HTTPCookieProcessor(CookieJar()))
    discovery_requests=0
    if live:
        # Runtime URL is only an unverified hint. Live requests must originate
        # from saved same-day official SP navigation bytes, never a variable.
        sp_source_url=""
        from diagnostics.kyoto_weekend_sp_discovery import discover
        discovery_root=root / "sp_discovery"
        try:
            found=discover(discovery_root,day=day,opener=shared_sp_client,pacer=shared_sp_pacer)
            discovery_requests=found["network_requests_started"]
            sp_source_url=found["racecard_url"]
        except Exception as exc:
            found={"state":"SP_DISCOVERY_EXCEPTION","network_requests_started":0,
                   "error_class":type(exc).__name__}
        finally:
            if discovery_root.is_dir():
                for item in discovery_root.iterdir():
                    if item.is_file() and not item.is_symlink():
                        item.rename(root / item.name)
                discovery_root.rmdir()
        if not sp_source_url:
            out=_no_claim(day,channel,found["state"],
                          observed_http_requests_started=discovery_requests,
                          captured_originals=any(root.glob("official_sp_discovery_*.html")))
            _write_receipt(root,out)
            return out
    if not sp_source_url:
        out = _no_claim(day, channel, "SP_OFFICIAL_LINK_NOT_SUPPLIED_ZERO_HTTP",
                        observed_http_requests_started=0)
        _write_receipt(root, out)
        return out
    try:
        result = capture_verified_sp_seed(
            root, race_day=day, race_number=12, source_url=sp_source_url,
            opener=shared_sp_client, include_odds=True, pacer=shared_sp_pacer)
        out = _no_claim(day, channel, result["state"],
                        observed_http_requests_started=discovery_requests+result.get("network_requests_started", 0),
                        captured_originals=bool(result.get("racecard_sha256")),
                        source_discovery_claim="EXTERNAL_INDEPENDENT_SP_LINK_UNVERIFIED_AT_RUNTIME")
    except Exception as exc:
        out = _no_claim(day, channel, "SP_CAPTURE_EXCEPTION",
                        error_class=type(exc).__name__)
    _write_receipt(root, out)
    return out


def _preserve_interrupted_originals(src: Path, day: str) -> None:
    """Flatten an interrupted PC capture without rewriting saved evidence.

    Nested observer receipt is retained separately when a wrapper failure
    receipt already exists. All provenance claims remain explicitly unverified.
    """
    nested=src / "pc_originals"
    if nested.exists() or nested.is_symlink():
        if nested.is_symlink() or not nested.is_dir():
            raise ValueError("unsafe_interrupted_pc_source")
        for item in sorted(nested.iterdir()):
            if item.is_symlink() or not item.is_file():
                raise ValueError("unsafe_interrupted_pc_entry")
            target=src / ("observer_partial_receipt.json" if item.name=="receipt.json"
                          else item.name)
            if target.exists() or target.is_symlink():
                raise ValueError("interrupted_original_collision")
            item.rename(target)
        nested.rmdir()
    if not (src / "receipt.json").exists():
        from hashlib import sha256
        files={}
        for item in sorted(src.iterdir()):
            if item.is_symlink() or not item.is_file():
                raise ValueError("unsafe_interrupted_source_entry")
            raw=item.read_bytes()
            files[item.name]={"sha256":sha256(raw).hexdigest(),"bytes":len(raw)}
        _write_receipt(src,{
            "schema":"kyoto_interrupted_source_evidence.v1","day":day,
            "state":"PARTIAL_OR_INTERRUPTED_CAPTURE_UNAUTHENTICATED",
            "source_verified":False,"both_markets_verified":False,
            "prediction_ready":False,"actual_http_attempts":"UNKNOWN",
            "original_files_observed":files,
            "saved_at_utc":datetime.now(timezone.utc).isoformat(),
        })


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
    _preserve_interrupted_originals(src,day)
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
