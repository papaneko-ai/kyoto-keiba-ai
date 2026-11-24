"""G06 immutable originals -> G07/P4/P5/P6 *input* staging.

Reparses original bytes, never trusts a batch 'success' flag by itself.
No model, recommendation, trade or fake horse attributes are invented.
"""
from __future__ import annotations
from pathlib import Path
from hashlib import sha256
import json
from diagnostics.kyoto_g06_item_level_recovery import recover_saved_markets,_read_verified
from diagnostics.jra_odds_matrix_parser import parse_matrix
from diagnostics.kyoto_g06_roster_aware_bracket import parse_bracket_with_roster
from diagnostics.jra_market_source_chain import SourceChainError

MARKETS=("quinella","bracket_quinella")
def prepare_intake(root,*,records):
    root=Path(root)
    if not isinstance(records,dict) or set(records)!=set(range(1,13)):
        raise SourceChainError("full_twelve_record_contract_required")
    batch_file=root/"g06_batch_receipt.json"
    if batch_file.is_symlink() or not batch_file.is_file():
        raise SourceChainError("g06_batch_receipt_missing")
    batch=json.loads(batch_file.read_text(encoding="utf-8"))
    if batch.get("schema")!="kyoto_g06_all12_source_capture.v1" or batch.get("total_races")!=12:
        raise SourceChainError("g06_batch_schema_invalid")
    entries=batch.get("records")
    if not isinstance(entries,list) or len(entries)!=12 or [x.get("race") for x in entries]!=list(range(1,13)):
        raise SourceChainError("batch_order_or_identity_invalid")
    output=[]
    for race in range(1,13):
        item=records[race]
        row={"race":race,"state":"NO_VERIFIED_SOURCE",
             "G07":{"state":"WAIT_SOURCE","horses":[]},
             "P4":{"state":"WAIT_PAIR_MARKETS","markets":{}},
             "P5":{"state":"WAIT_CALIBRATED_MODEL_AND_P4"},
             "P6":{"state":"WAIT_PRE_RESULT_FROZEN_P5"},
             "prediction_ready":False,"paper_trade_authorized":False}
        if item is None:
            row["state"]="OFFICIAL_LINK_UNOBSERVED"
            output.append(row)
            continue
        spec=item["race_spec"]
        if spec.race_number!=race or len(item["active_runners"])!=len(item["expected_named_runners"]):
            raise SourceChainError("input_race_roster_mismatch")
        verified=recover_saved_markets(root/f"r{race:02d}",race_spec=spec,
            active_runners=item["active_runners"],
            verified_start_utc=item["verified_start_utc"])
        # G07 can consume the externally frozen named roster, but every
        # horse attribute absent from originals is explicitly unknown.
        row["G07"]={"state":"ROSTER_IDENTITIES_STAGED_FIELDS_PENDING",
            "horses":[{"number":n,"bracket":b,"name":name,
                       "profile":"MISSING_NOT_IN_G06",
                       "prior_form":"MISSING_NOT_IN_G06",
                       "workout":"MISSING_NOT_IN_G06"}
                      for n,b,name in item["expected_named_runners"]]}
        for market in MARKETS:
            proof=verified["markets"][market]["selected"]
            if proof is None:continue
            channel=proof["channel"]
            base=root/f"r{race:02d}"
            file_name=market+"_original.html"
            dirs=(base/channel.lower(),base/(channel.lower()+"_recovery"))
            matched=None
            for directory in dirs:
                receipt=directory/"receipt.json"
                if not receipt.is_file() or receipt.is_symlink():continue
                data=json.loads(receipt.read_text(encoding="utf-8"))
                steps={x["step"]:x for x in data.get("request_receipts",[])}
                if market in steps and steps[market].get("sha256")==proof["sha256"]:
                    matched=(directory,steps[market],steps.get("racecard"));break
            if matched is None:
                raise SourceChainError("selected_market_original_not_locatable")
            directory,step,roster_step=matched
            raw=_read_verified(directory,file_name,step)
            from diagnostics.kyoto_impl30_cancelled_market import parse_current_market
            roster_raw=_read_verified(directory,"official_racecard.html",roster_step)
            parsed,_=parse_current_market(raw,market,item["active_runners"],racecard=roster_raw,
                racecard_utc=roster_step["captured_at_utc"],market_utc=step["captured_at_utc"],
                start_utc=item["verified_start_utc"],day=spec.race_day,race=spec.race_number)
            if parsed.get("historical_final_detected"):
                raise SourceChainError("final_prices_cannot_enter_p4")
            row["P4"]["markets"][market]={
                "channel":channel,"sha256":sha256(raw).hexdigest(),
                "captured_at_utc":proof["captured_at_utc"],
                "original_relative_path":str((directory/file_name).relative_to(root)),
                "pairs":[{"numbers":list(x["pair"]),"odds":x["odds"]} for x in parsed["pairs"]],
                "source_url":proof["source_url"],"cancelled_horses":parsed.get("cancelled_horses",[])}
        if len(row["P4"]["markets"])==2 and verified["both_markets_verified"]:
            row["P4"]["state"]="SOURCE_MARKETS_STAGED_AWAIT_MODEL_AND_TEMPORAL_RECHECK"
            row["state"]="G07_P4_INPUTS_AVAILABLE"
        elif verified.get("cancellation_conflict"):
            row["P4"]["state"]="CANCELLATION_CONFLICT_SOURCE_ONLY"
            row["state"]="PARTIAL_MARKET_INPUT_RETAINED"
        elif row["P4"]["markets"]:
            row["state"]="PARTIAL_MARKET_INPUT_RETAINED"
        output.append(row)
    ready=sum(x["state"]=="G07_P4_INPUTS_AVAILABLE" for x in output)
    result={"schema":"kyoto_g06_g07_p4_p5_p6_source_intake.v1",
        "races_total":12,"paired_source_races":ready,
        "partial_source_races":sum(x["state"]=="PARTIAL_MARKET_INPUT_RETAINED" for x in output),
        "G07_stage":"IDENTITY_AND_MISSINGNESS_ONLY",
        "P4_stage":"SOURCE_ODDS_ONLY_NOT_MODEL_EV",
        "P5_stage":"PENDING_P4_MODEL_COMPARISON",
        "P6_stage":"PENDING_INDEPENDENT_PRE_RESULT_FREEZE",
        "eligible_for_prediction":False,"synthetic_model_added":False,
        "actual_wagers_enabled":False,
        "races":output}
    out=root/"g06_downstream_input_receipt.json"
    from diagnostics.kyoto_g06_four_stage_inboxes import publish_inboxes
    # Materialize all four stage inputs before declaring handoff complete.
    manifest=publish_inboxes(root,source_receipt=result)
    result["four_stage_handoff_manifest_sha256"]=sha256(
        (root/"next_stage_inboxes"/"manifest.json").read_bytes()).hexdigest()
    with out.open("x",encoding="utf-8") as f:
        json.dump(result,f,ensure_ascii=False,sort_keys=True,indent=2)
        f.write("\n")
    return result
