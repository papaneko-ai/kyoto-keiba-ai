"""P6-03 offline result-HTML -> versioned payout -> frozen P6 LAB replay.

This accepts user-provided bytes ONLY, never network fetches. It parses
payout labels in a synthetic/JRA-shaped fixture but does not certify JRA
origin or source timestamps. Original P6 freeze or settlement directories
are NEVER mutated: a new full snapshot is built and verified then published.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from diagnostics.extract_kyoto_payouts import VisibleText
from diagnostics.p6_fixture_durable_ledger import read_journal, append_record, LabRejected
from diagnostics.p6_virtual_settlement_fixture_lab import _utc

class FinalResultRejected(ValueError): pass

def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
                    separators=(",",":"),allow_nan=False).encode()).hexdigest()

def _decode_final(raw):
    if type(raw) is not bytes or not 0<len(raw)<=1_800_000:
        raise FinalResultRejected("final_html_source_invalid")
    p=VisibleText()
    p.feed(raw.decode("cp932",errors="strict"))
    return " ".join(p.parts)

def _read_final(*,raw,race_date,race,ticket_type):
    if ticket_type not in ("QUINELLA","BRACKET"):
        raise FinalResultRejected("unsupported_ticket_type")
    try:
        parsed=datetime.strptime(race_date,"%Y-%m-%d")
    except (TypeError,ValueError) as exc:
        raise FinalResultRejected("race_date_invalid") from exc
    if type(race) is not int or not 1<=race<=12:
        raise FinalResultRejected("race_invalid")
    text=_decode_final(raw)
    if f"{parsed.year}年{parsed.month}月{parsed.day}日" not in text:
        raise FinalResultRejected("result_meeting_date_mismatch")
    if not re.search(r"京都\s*"+str(race)+r"\s*(?:R|レース)",text):
        raise FinalResultRejected("result_race_identity_missing")
    if len(re.findall(r"払戻金\s+単勝",text))!=1:
        raise FinalResultRejected("result_section_not_unique")
    label="馬連" if ticket_type=="QUINELLA" else "枠連"
    end="馬単" if ticket_type=="QUINELLA" else "ワイド"
    match=re.search(r"(?<!\S)"+label+r"\s+(.*?)\s+"+end+r"(?=\s|$)",text)
    if not match:
        raise FinalResultRejected("final_market_boundaries_missing")
    block=match.group(1).strip()
    pattern=r"(\d{1,2})-(\d{1,2})\s+([\d,]+)\s*円"
    items=list(re.finditer(pattern,block))
    if len(items)!=1 or block!=items[0].group(0):
        raise FinalResultRejected("payout_pair_ambiguous")
    a,b,amount=items[0].groups()
    a,b=int(a),int(b)
    top=18 if ticket_type=="QUINELLA" else 8
    if not 1<=a<=top or not 1<=b<=top or (a==b and ticket_type=="QUINELLA"):
        raise FinalResultRejected("payout_pair_out_of_range")
    amount=int(amount.replace(",",""))
    if amount<100 or amount>20_000_000:
        raise FinalResultRejected("payout_yen_invalid")
    pair=tuple(sorted((a,b)))
    return {"pair":"-".join(map(str,pair)), "payout_per_100":amount}

def settle_ranked_lab_results(*,prior_directory,destination,result_captures,
                              expected_prior_manifest_sha256,version=1):
    """Produce an immutable new settled snapshot, including 0 selected races.

    Each capture has exact keys {raw, captured_utc, declared_scope}; declared
    scope must be LAB_RESULT_FIXTURE_ONLY. No user-supplied event/payout dict.
    The source bytes are parsed against a preexisting frozen race/date;
    authenticity and official confirmation remain explicitly false.
    """
    prior=Path(prior_directory);target=Path(destination)
    if not prior.is_dir() or prior.is_symlink() or target.exists() or target.is_symlink():
        raise FinalResultRejected("immutable_source_or_target_invalid")
    if not target.parent.is_dir() or prior.resolve()==target.resolve():
        raise FinalResultRejected("destination_parent_invalid")
    if type(version) is not int or version<1:
        raise FinalResultRejected("result_version_invalid")
    if type(expected_prior_manifest_sha256) is not str or len(expected_prior_manifest_sha256)!=64:
        raise FinalResultRejected("manifest_anchor_required")
    manifest_file=prior/"manifest.json"
    raw_manifest=manifest_file.read_bytes()
    if hashlib.sha256(raw_manifest).hexdigest()!=expected_prior_manifest_sha256:
        raise FinalResultRejected("prior_manifest_sha_mismatch")
    manifest=json.loads(raw_manifest)
    if manifest.get("schema") not in ("kyoto_p6_pre_result_ranked_lab.v1",
                                      "kyoto_p6_lab_result_settlement_snapshot.v1"):
        raise FinalResultRejected("unsupported_prior_manifest")
    rows=manifest.get("journals")
    if type(rows) is not list or type(result_captures) is not dict:
        raise FinalResultRejected("result_capture_spec_invalid")
    required={str(x["race"]) for x in rows}
    if set(result_captures)!=required or len(required)!=len(rows):
        raise FinalResultRejected("exact_result_race_coverage_required")
    validated=[]
    for item in rows:
        race=item["race"];path=prior/item["file"]
        if not re.fullmatch(r"race-\d{2}\.jsonl",item["file"]) or path.is_symlink():
            raise FinalResultRejected("journal_member_invalid")
        state=read_journal(path,expected_head=item["journal_head_sha256"])
        frozen=state["entries"][0]["payload"]["record"]["frozen"]
        if (frozen["scenario_id"]!=item["scenario_id"] or
            state["entries"][0]["payload"]["record"]["frozen_sha256"]!=item["frozen_prediction_sha256"]):
            raise FinalResultRejected("frozen_receipt_mismatch")
        capture=result_captures[str(race)]
        if type(capture) is not dict or set(capture)!={"raw","captured_utc","declared_scope"}:
            raise FinalResultRejected("result_capture_shape_invalid")
        if capture["declared_scope"]!="LAB_RESULT_FIXTURE_ONLY":
            raise FinalResultRejected("official_result_claim_not_authorized")
        captured=_utc(capture["captured_utc"])
        if captured<=_utc(frozen["cutoff_utc"]):
            raise FinalResultRejected("result_capture_not_after_cutoff")
        info=_read_final(raw=capture["raw"],race_date=item["race_date"],race=race,
                         ticket_type=frozen["ticket_type"])
        latest=state["entries"][-1]["payload"]
        prior_version=(latest["record"]["version"] if latest["type"]=="RESULT_EVENT" else 0)
        if version!=prior_version+1:
            raise FinalResultRejected("result_version_not_next")
        event={"scenario_id":frozen["scenario_id"],"source_kind":"FIXTURE",
               "version":version,"state":"PAYOUT_FINAL",
               "payout_per_100":{info["pair"]:info["payout_per_100"]},
               "refunded_pairs":[]}
        validated.append((item,path,state,capture,event))
    with tempfile.TemporaryDirectory(prefix=".p6-result-stage-",dir=target.parent) as tmp:
        stage=Path(tmp)
        new_rows=[]
        for item,path,state,capture,event in validated:
            stage_path=stage/item["file"]
            shutil.copyfile(path,stage_path)
            updated=append_record(stage_path,"RESULT_EVENT",event,expected_head=state["head"])
            replay=read_journal(stage_path,expected_head=updated["head"])
            if replay["result"]["status"]!="FINAL_FIXTURE_ONLY":
                raise FinalResultRejected("settlement_replay_not_final")
            new_rows.append({**item,"journal_head_sha256":updated["head"],
                "source_final_html_sha256":hashlib.sha256(capture["raw"]).hexdigest(),
                "final_result_observed_utc":capture["captured_utc"],
                "final_result_version":version,
                "fixture_payout_yen":replay["result"]["payout_yen"],
                "fixture_profit_yen":replay["result"]["profit_yen"]})
        body={"schema":"kyoto_p6_lab_result_settlement_snapshot.v1",
              "scope":"OFFLINE_JRA_SHAPED_LAB_RESULT_NOT_OFFICIAL",
              "prior_manifest_sha256":expected_prior_manifest_sha256,
              "p5_ranking_sha256":manifest["p5_ranking_sha256"],
              "research_spent_yen":manifest["research_spent_yen"],
              "settled_fixture_payout_yen":sum(x["fixture_payout_yen"] for x in new_rows),
              "settled_fixture_profit_yen":sum(x["fixture_profit_yen"] for x in new_rows),
              "journals":new_rows,
              "official_origin_independently_verified":False,
              "official_results_verified":False,
              "real_race_paper_trade_settled":False,
              "actual_purchase_authorized":False}
        receipt={**body,"receipt_sha256":_hash(body)}
        (stage/"manifest.json").write_text(json.dumps(receipt,ensure_ascii=False,
           sort_keys=True,separators=(",",":"),allow_nan=False)+"\n",encoding="utf8")
        if target.exists() or target.is_symlink():
            raise FinalResultRejected("immutable_target_changed")
        os.rename(stage,target)
    return receipt
