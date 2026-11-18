"""G06 experimental 12R paired-market capture orchestrator.

Reuses the existing independently observed race spec and hybrid collector.
No URLs are synthesized. Individual race errors do not abort other races.
Never authorizes prediction or production deployment on its own.
"""
from __future__ import annotations
from pathlib import Path
from hashlib import sha256
import json
from diagnostics.jra_one_shot_market_capture import capture_hybrid, SourceChainError

MARKETS=("quinella","bracket_quinella")
REQUIRED_ORIGINALS=("official_odds_menu.html","quinella_original.html","bracket_quinella_original.html")

def _verify_saved_channel(folder):
    """Independently verify both saved market files against immutable request receipts."""
    receipt_path=folder/"receipt.json"
    if not receipt_path.is_file() or receipt_path.is_symlink():
        return {"state":"MISSING_CHANNEL_RECEIPT"}
    try:
        receipt=json.loads(receipt_path.read_text(encoding="utf-8"))
        steps={x["step"]:x for x in receipt["request_receipts"]}
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
        return {"state":"BOTH_MARKET_ORIGINALS_VERIFIED",
                "market_shas":{m:steps[m]["sha256"] for m in MARKETS},
                "capture_times_utc":{m:steps[m]["captured_at_utc"] for m in MARKETS}}
    except (ValueError,KeyError,TypeError,OSError):
        return {"state":"CORRUPT_CHANNEL_RECEIPT"}

def run_twelve(root, *, records, authorized_live_http=False, runner=None):
    """records: 12 entries indexed 1..12; missing links explicitly None.

    Requires a fresh output directory. Every valid record carries an existing
    ObservedRaceSpec and a frozen independent named roster; no remote fetch is
    attempted by default. run output is evidence-only even on 12 successes.
    """
    if not isinstance(records,dict) or set(records)!=set(range(1,13)):
        raise SourceChainError("all_twelve_race_slots_required")
    base=Path(root)
    if base.exists() or base.is_symlink() or not base.parent.is_dir():
        raise SourceChainError("new_output_directory_required")
    if type(authorized_live_http) is not bool:
        raise SourceChainError("authorization_boolean_required")
    base.mkdir()
    results=[]
    collector=runner or capture_hybrid
    for race in range(1,13):
        item=records[race]
        entry={"race":race,"state":"NOT_ATTEMPTED","both_markets_verified":False}
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
            receipt=collector(output,primary_channel=item["primary_channel"],
                verified_start_utc=item["verified_start_utc"],
                active_runners=item["active_runners"],race_spec=spec,
                authorized_live_http=authorized_live_http,
                expected_named_runners=item["expected_named_runners"])
            entry["state"]=receipt.get("state","UNKNOWN")
            entry["selected_channel"]=receipt.get("selected_channel")
            if entry["selected_channel"] in ("PC","SP"):
                verified=_verify_saved_channel(output/entry["selected_channel"].lower())
                entry["evidence_check"]=verified
                entry["both_markets_verified"]=verified["state"]=="BOTH_MARKET_ORIGINALS_VERIFIED"
            else:
                entry["evidence_check"]={"state":"NO_SELECTED_CHANNEL"}
        except (ValueError,TypeError,KeyError,AttributeError,OSError) as exc:
            entry.update(state="INPUT_OR_CAPTURE_REJECTED",
                         reason=type(exc).__name__+":"+str(exc)[:120])
        results.append(entry)
    summary={"schema":"kyoto_g06_all12_source_capture.v1",
        "total_races":12,"verified_dual_market_races":sum(x["both_markets_verified"] for x in results),
        "unobserved_link_races":sum(x["state"]=="OFFICIAL_LINK_NOT_OBSERVED" for x in results),
        "all_twelve_source_originals_verified":all(x["both_markets_verified"] for x in results),
        "g06_certified":False,"prediction_ready":False,
        "actual_wager_authorized":False,"production_cutover_authorized":False,
        "records":results}
    (base/"g06_batch_receipt.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return summary
