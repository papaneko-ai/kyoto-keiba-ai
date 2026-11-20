"""G06 experimental 12R paired-market capture orchestrator.

Reuses the existing independently observed race spec and hybrid collector.
No URLs are synthesized. Individual race errors do not abort other races.
Never authorizes prediction or production deployment on its own.
"""
from __future__ import annotations
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import json
import time
from diagnostics.jra_one_shot_market_capture import capture_hybrid, SourceChainError, RequestPacer
from diagnostics.kyoto_g06_item_level_recovery import recover_saved_markets
from diagnostics.kyoto_g06_gap_recovery_plan import plan_gap_recovery
from diagnostics.kyoto_g06_market_link_evidence import observed_market_links
from diagnostics.kyoto_g06_missing_market_retry import recover_one

MARKETS=("quinella","bracket_quinella")
REQUIRED_ORIGINALS=("official_odds_menu.html","quinella_original.html","bracket_quinella_original.html")

def _verify_saved_channel(folder, *, verified_start_utc):
    """Independently verify both saved market files against immutable request receipts."""
    receipt_path=folder/"receipt.json"
    if not receipt_path.is_file() or receipt_path.is_symlink():
        return {"state":"MISSING_CHANNEL_RECEIPT"}
    try:
        receipt=json.loads(receipt_path.read_text(encoding="utf-8"))
        steps={x["step"]:x for x in receipt["request_receipts"]}
        chain=receipt.get("market_receipt")
        if not isinstance(chain,dict) or chain.get("classification")!="VALIDATED_LIVE_MARKETS_NOT_PREDICTION_RELEASED":
            return {"state":"MARKET_VALIDATION_CHAIN_NOT_PROVEN"}
        phases=chain.get("markets",{})
        if set(phases)!=set(MARKETS) or any(
                phases[k].get("phase")!="LIVE_PRE_RACE"
                or phases[k].get("pre_race_usable") is not True
                for k in MARKETS):
            return {"state":"MARKET_PHASE_OR_INTEGRITY_NOT_VALIDATED"}
        try:
            cutoff=datetime.fromisoformat(verified_start_utc.replace("Z","+00:00"))
            if cutoff.tzinfo is None or cutoff.utcoffset()!=timezone.utc.utcoffset(None):
                return {"state":"INVALID_CUTOFF"}
            for step in ("odds_menu",)+MARKETS:
                seen=datetime.fromisoformat(steps[step]["captured_at_utc"].replace("Z","+00:00"))
                if seen.tzinfo is None or seen.utcoffset()!=timezone.utc.utcoffset(None) or seen>=cutoff:
                    return {"state":"MARKET_NOT_CAPTURED_BEFORE_START","step":step}
        except (ValueError,TypeError,KeyError,AttributeError):
            return {"state":"INVALID_CAPTURE_TIME"}
        for market,name in (("odds_menu",REQUIRED_ORIGINALS[0]),
                            ("quinella",REQUIRED_ORIGINALS[1]),
                            ("bracket_quinella",REQUIRED_ORIGINALS[2])):
            path=folder/name
            if path.is_symlink() or not path.is_file() or market not in steps:
                return {"state":"MISSING_MARKET_ORIGINAL_OR_RECEIPT","missing":market}
            raw=path.read_bytes()
            if not raw or len(raw)!=steps[market]["bytes"] or sha256(raw).hexdigest()!=steps[market]["sha256"]:
                return {"state":"ORIGINAL_RECEIPT_MISMATCH","market":market}
        if receipt.get("state")!="SOURCE_FROZEN" or receipt.get("pre_race_prices_accepted") is not True:
            return {"state":"SOURCE_NOT_FROZEN"}
        if any(phases[k].get("source_sha256")!=steps[k]["sha256"] for k in MARKETS):
            return {"state":"MARKET_CHAIN_ORIGINAL_SHA_MISMATCH"}
        return {"state":"BOTH_MARKET_ORIGINALS_VERIFIED",
                "market_shas":{m:steps[m]["sha256"] for m in MARKETS},
                "capture_times_utc":{m:steps[m]["captured_at_utc"] for m in MARKETS}}
    except (ValueError,KeyError,TypeError,OSError):
        return {"state":"CORRUPT_CHANNEL_RECEIPT"}

def run_twelve(root, *, records, authorized_live_http=False, runner=None,
               request_pacer=None,openers=None,claim_client=None,claim_slot=None,
               claim_owner=None,claim_now_epoch=None,claim_clock=None,
               capture_deadline_monotonic=None,monotonic_clock=None):
    """records: 12 entries indexed 1..12; missing links explicitly None.

    Requires a fresh output directory. Every valid record carries an existing
    ObservedRaceSpec and a frozen independent named roster; no remote fetch is
    attempted by default. run output is evidence-only even on 12 successes.
    """
    if capture_deadline_monotonic is not None and (type(capture_deadline_monotonic) not in (int,float) or capture_deadline_monotonic<=0):
        raise SourceChainError("g06_time_budget_invalid")
    if monotonic_clock is not None and not callable(monotonic_clock):
        raise SourceChainError("g06_time_clock_invalid")
    budget_clock=monotonic_clock or time.monotonic
    if not isinstance(records,dict) or set(records)!=set(range(1,13)):
        raise SourceChainError("all_twelve_race_slots_required")
    base=Path(root)
    if base.exists() or base.is_symlink() or not base.parent.is_dir():
        raise SourceChainError("new_output_directory_required")
    if type(authorized_live_http) is not bool:
        raise SourceChainError("authorization_boolean_required")
    if claim_clock is not None and not callable(claim_clock):
        raise SourceChainError("remote_claim_clock_invalid")
    if claim_client is not None and (not authorized_live_http or runner is not None):
        raise SourceChainError("remote_claims_live_default_collector_only")
    if claim_client is not None and (
        type(claim_slot) is not int or not 0<=claim_slot<=3
        or type(claim_owner) is not str or not claim_owner
        or type(claim_now_epoch) is not int or claim_now_epoch<=0):
        raise SourceChainError("remote_claim_scope_invalid")
    base.mkdir()
    results=[]
    collector=runner or capture_hybrid
    if request_pacer is None and authorized_live_http and runner is None:
        request_pacer=RequestPacer()
    observed_days={item["race_spec"].race_day for item in records.values()
                   if isinstance(item,dict) and "race_spec" in item
                   and hasattr(item["race_spec"],"race_day")}
    if len(observed_days)>1:
        raise SourceChainError("cross_day_batch_mixing_forbidden")
    for race in range(1,13):
        item=records[race]
        entry={"race":race,"state":"NOT_ATTEMPTED","both_markets_verified":False}
        lease=None
        lease_key=None
        lease_now=None
        # A global deadline bounds all 12 races, rather than resetting the
        # timeout at every race. Preserve already saved originals and produce
        # one truthful record for every subsequent unattempted race.
        if capture_deadline_monotonic is not None and budget_clock()>=capture_deadline_monotonic:
            entry["state"]="G06_TIME_BUDGET_RESERVED_FOR_SEALING"
            entry["reason"]="global_capture_budget_exhausted_no_new_http"
            results.append(entry)
            continue
        if item is None:
            entry["state"]="OFFICIAL_LINK_NOT_OBSERVED"
            results.append(entry)
            continue
        try:
            if not isinstance(item,dict) or set(item)!={
                "race_spec","verified_start_utc","active_runners",
                "expected_named_runners","primary_channel"}:
                raise SourceChainError("race_entry_schema_invalid")
            spec=item["race_spec"]
            if spec.race_number!=race:
                raise SourceChainError("cross_race_spec_mismatch")
            if item["primary_channel"] not in ("PC","SP"):
                raise SourceChainError("primary_channel_invalid")
            spec.validate(require_channels=(item["primary_channel"],))
            if len(item["active_runners"])!=len(item["expected_named_runners"]):
                raise SourceChainError("runner_reference_count_mismatch")
            if tuple(tuple(x[:2]) for x in item["expected_named_runners"])!=tuple(item["active_runners"]):
                raise SourceChainError("runner_reference_identity_mismatch")
            output=base/f"r{race:02d}"
            lease=None
            if claim_client is not None:
                from diagnostics.kyoto_shared_capture_reservation import key
                lease_key=key(day=spec.race_day,slot=claim_slot,race=race,
                              channel="SHARED",market="racecard")
                try:
                    lease_now=int(claim_clock()) if claim_clock is not None else claim_now_epoch
                    if lease_now<=0:raise SourceChainError("remote_claim_clock_invalid")
                    lease=claim_client.claim(claim_key=lease_key,owner=claim_owner,
                        now_epoch=lease_now,lease_seconds=1800)
                except Exception as exc:
                    entry["claim_state"]="COORDINATOR_UNCONFIRMED"
                    entry["claim_error_class"]=type(exc).__name__
                    # Do not invent a completed acquisition and do not start
                    # uncoordinated requests when cross-host mode was chosen.
                    raise SourceChainError("remote_claim_unconfirmed_no_http") from None
                entry["claim_state"]=lease["state"]
                if not lease.get("must_fetch"):
                    entry["state"]="SHARED_SLOT_OWNED_OR_DONE_REUSE_NEXT_SLOT"
                    results.append(entry)
                    continue
            receipt=collector(output,primary_channel=item["primary_channel"],
                verified_start_utc=item["verified_start_utc"],
                active_runners=item["active_runners"],race_spec=spec,
                authorized_live_http=authorized_live_http,
                expected_named_runners=item["expected_named_runners"],
                **({"shared_pacer":request_pacer,"openers":openers} if runner is None else {}))
            entry["state"]=receipt.get("state","UNKNOWN")
            entry["selected_channel"]=receipt.get("selected_channel")
            if entry["selected_channel"] in ("PC","SP"):
                verified=_verify_saved_channel(output/entry["selected_channel"].lower(), verified_start_utc=item["verified_start_utc"])
                entry["evidence_check"]=verified
                entry["both_markets_verified"]=verified["state"]=="BOTH_MARKET_ORIGINALS_VERIFIED"
            else:
                entry["evidence_check"]={"state":"NO_SELECTED_CHANNEL"}
            recovered=recover_saved_markets(output,race_spec=spec,
                active_runners=item["active_runners"],
                verified_start_utc=item["verified_start_utc"])
            entry["item_level_recovery"]=recovered
            proofs={m:recovered["markets"][m]["selected"] for m in MARKETS}
            market_link_proof=observed_market_links(output,race_spec=spec,
                verified_start_utc=item["verified_start_utc"])
            entry["official_market_link_proof"]=market_link_proof
            # Live recovery is opt-in, only on the actual collector path.
            # The immutable initial capture is independently verified first.
            # A market already verified from either source is never re-fetched.
            entry["live_market_recovery_attempts"]=[]
            if authorized_live_http and runner is None and not recovered["both_markets_verified"]:
                attempts=receipt.get("attempts",[])
                refusal=any(
                    any(token in str(a.get("reason") or "").lower()
                        for token in ("403","429","redirect_forbidden",
                                      "access_denied","permission","unauthorized"))
                    for a in attempts if isinstance(a,dict))
                if not refusal:
                    for missing in MARKETS:
                        if recovered["markets"][missing]["state"]=="VERIFIED":
                            continue
                        # Avoid post-deadline recovery requests while retaining
                        # verified primary market originals and receipt hashes.
                        if capture_deadline_monotonic is not None and budget_clock()>=capture_deadline_monotonic:
                            entry["live_market_recovery_attempts"].append(
                                {"state":"G06_TIME_BUDGET_RESERVED_FOR_SEALING",
                                 "market":missing})
                            break
                        for channel in (item["primary_channel"],
                                        "SP" if item["primary_channel"]=="PC" else "PC"):
                            if capture_deadline_monotonic is not None and budget_clock()>=capture_deadline_monotonic:
                                entry["live_market_recovery_attempts"].append(
                                    {"state":"G06_TIME_BUDGET_RESERVED_FOR_SEALING",
                                     "market":missing,"channel":channel})
                                break
                            if not market_link_proof[channel]["observed"]:
                                continue
                            try:
                                response=recover_one(root=output,channel=channel,
                                    market=missing,race_spec=spec,
                                    active_runners=item["active_runners"],
                                    verified_start_utc=item["verified_start_utc"],
                                    authorized_live_http=True,pacer=request_pacer,
                                    opener=(openers or {}).get(channel))
                                state=response["state"]
                                entry["live_market_recovery_attempts"].append(
                                    {"channel":channel,"market":missing,"state":state})
                                if "403" in str(response.get("reason","")) or "429" in str(response.get("reason","")):
                                    break
                                recovered=recover_saved_markets(output,race_spec=spec,
                                    active_runners=item["active_runners"],
                                    verified_start_utc=item["verified_start_utc"])
                                if recovered["markets"][missing]["state"]=="VERIFIED":
                                    break
                            except (SourceChainError,ValueError,OSError) as exc:
                                entry["live_market_recovery_attempts"].append(
                                    {"channel":channel,"market":missing,
                                     "state":"RECOVERY_NOT_EXECUTED",
                                     "reason":type(exc).__name__+":"+str(exc)[:120]})
                        # Each existing channel gets at most one bounded
                        # recovery attempt. No fabricated URL or blind replay.
                    entry["item_level_recovery"]=recovered
                else:
                    entry["live_market_recovery_attempts"].append(
                        {"state":"GLOBAL_ACCESS_REFUSAL_RETAIN_ORIGINALS"})
            entry["gap_recovery_plan"]=plan_gap_recovery(
                race_id=spec.race_id,verified_market_receipts=proofs,
                official_links={ch:proof["observed"] for ch,proof in market_link_proof.items()},
                attempt_history=[],now_utc=datetime.now(timezone.utc).isoformat(),
                cutoff_utc=item["verified_start_utc"])
            if recovered["both_markets_verified"]:
                entry["both_markets_verified"]=True
                entry["item_level_completed"]=True
                entry["cross_source_times_not_equated"]=True
            if claim_client is not None and lease and lease["must_fetch"]:
                import hashlib
                try:
                    if entry["both_markets_verified"]:
                        digest=hashlib.sha256((output/"pc"/"receipt.json").read_bytes()).hexdigest() if (output/"pc"/"receipt.json").is_file() else hashlib.sha256((output/"sp"/"receipt.json").read_bytes()).hexdigest()
                        committed=claim_client.complete(claim_key=lease_key,owner=claim_owner,
                            generation=lease["generation"],sha256=digest)
                        entry["claim_commit_state"]=committed["state"]
                    else:
                        released=claim_client.abandon(claim_key=lease_key,owner=claim_owner,
                            generation=lease["generation"],now_epoch=(int(claim_clock()) if claim_clock is not None else lease_now))
                        entry["claim_commit_state"]="RELEASED_FOR_RETRY" if released["released"] else "FENCE_REJECTED"
                except Exception as exc:
                    entry["claim_commit_state"]="COORDINATOR_COMMIT_UNCONFIRMED"
                    entry["claim_error_class"]=type(exc).__name__
        except (SourceChainError,ValueError,TypeError,KeyError,AttributeError,OSError) as exc:
            entry.update(state="INPUT_OR_CAPTURE_REJECTED",
                         reason=type(exc).__name__+":"+str(exc)[:120])
            if claim_client is not None and lease and lease.get("must_fetch"):
                try:
                    released=claim_client.abandon(claim_key=lease_key,owner=claim_owner,
                        generation=lease["generation"],now_epoch=(int(claim_clock()) if claim_clock is not None else lease_now))
                    entry["claim_commit_state"]=(
                        "RELEASED_FOR_RETRY" if released["released"] else "FENCE_REJECTED")
                except Exception:
                    entry["claim_commit_state"]="RELEASE_UNCONFIRMED_LEASE_EXPIRES"
        results.append(entry)
    summary={"schema":"kyoto_g06_all12_source_capture.v1",
        "total_races":12,"verified_dual_market_races":sum(x["both_markets_verified"] for x in results),
        "unobserved_link_races":sum(x["state"]=="OFFICIAL_LINK_NOT_OBSERVED" for x in results),
        "time_budget_reserved_for_sealing_races":sum(x["state"]=="G06_TIME_BUDGET_RESERVED_FOR_SEALING" for x in results),
        "time_budget_deadline_enabled":capture_deadline_monotonic is not None,
        "all_twelve_source_originals_verified":all(x["both_markets_verified"] for x in results),
        "g06_certified":False,"prediction_ready":False,
        "actual_wager_authorized":False,"production_cutover_authorized":False,
        "records":results}
    (base/"g06_batch_receipt.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    # Production-oriented invocation stages the verified original data
    # immediately after the full batch; optional custom runners remain
    # standalone so existing test and migration contracts are preserved.
    if runner is None:
        try:
            from diagnostics.kyoto_g06_downstream_intake import prepare_intake
            stage=prepare_intake(base,records=records)
            summary["downstream_intake_created"]=True
            summary["downstream_source_ready_races"]=stage["paired_source_races"]
        except (ValueError,TypeError,KeyError,OSError) as exc:
            summary["downstream_intake_created"]=False
            summary["downstream_intake_error"]=type(exc).__name__+":"+str(exc)[:130]
    return summary
