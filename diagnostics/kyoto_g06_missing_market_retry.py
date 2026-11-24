"""Recover one genuinely missing pre-race market from immutable official menu.

Uses the existing official HTTP POST transport and link parser. Previous
originals are never overwritten. An independent *_recovery receipt records
new bytes and timestamps, and the existing verifier must re-check both.
"""
from __future__ import annotations
import json
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path
from urllib.request import build_opener,HTTPCookieProcessor
from http.cookiejar import CookieJar
from diagnostics.jra_one_shot_market_capture import (
    http_fetch,NoRedirect,RequestPacer,persist_original_once,persist_receipt_once,
    SourceChainError)
from diagnostics.jra_market_source_chain import _html_race_identity
from diagnostics.jra_official_market_navigation import find_market_links
from diagnostics.jra_odds_matrix_parser import parse_matrix
from diagnostics.kyoto_g06_roster_aware_bracket import parse_bracket_with_roster

MARKETS=("quinella","bracket_quinella")
def _date(v):
    if not isinstance(v,str):raise SourceChainError("utc_string_required")
    try:dt=datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError as exc:raise SourceChainError("invalid_utc") from exc
    if dt.tzinfo is None or dt.utcoffset()!=timezone.utc.utcoffset(None):
        raise SourceChainError("non_utc_time")
    return dt

def _verified_file(folder,name,step):
    p=folder/name
    if p.is_symlink() or not p.is_file():raise SourceChainError("evidence_file_missing")
    data=p.read_bytes()
    if not data or len(data)!=step.get("bytes") or sha256(data).hexdigest()!=step.get("sha256"):
        raise SourceChainError("evidence_sha_mismatch")
    return data

def recover_one(*, root,channel,market,race_spec,active_runners,
                verified_start_utc,authorized_live_http=False,opener=None,
                now_utc=None,pacer=None):
    if channel not in ("PC","SP") or market not in MARKETS:
        raise SourceChainError("recovery_channel_market_invalid")
    if type(authorized_live_http) is not bool:
        raise SourceChainError("authorization_boolean_required")
    root=Path(root)
    source=root/channel.lower()
    target=root/(channel.lower()+"_recovery")
    if target.exists() or target.is_symlink() or not source.is_dir() or source.is_symlink():
        raise SourceChainError("recovery_destination_exists_or_source_missing")
    now=_date(now_utc) if now_utc else datetime.now(timezone.utc)
    cutoff=_date(verified_start_utc)-timedelta(minutes=10)
    if now>=cutoff:raise SourceChainError("recovery_cutoff_reached_zero_http")
    receipt_path=source/"receipt.json"
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise SourceChainError("original_receipt_missing")
    receipt=json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("race_id")!=race_spec.race_id or receipt.get("channel")!=channel:
        raise SourceChainError("original_identity_conflict")
    if receipt.get("state") in ("REJECT_FINAL_ODDS","OFFICIAL_NOT_PUBLISHED",
                                "CUTOFF_PASSED_NO_HTTP","WAIT_FOR_OFFICIAL_SALES"):
        raise SourceChainError("unsafe_market_phase")
    steps={x["step"]:x for x in receipt["request_receipts"]}
    if "racecard" not in steps or "odds_menu" not in steps:
        raise SourceChainError("official_navigation_chain_missing")
    if market in steps:
        # Saved evidence is present: the verifier decides whether it is
        # usable. Do not fetch a second copy just to mask bad provenance.
        raise SourceChainError("market_original_already_observed")
    racecard=_verified_file(source,"official_racecard.html",steps["racecard"])
    if not _html_race_identity(racecard,race_spec.race_day,race_spec.venue,race_spec.race_number):
        raise SourceChainError("racecard_identity_conflict")
    nav=sorted((x for x in steps if x.startswith("odds_navigation_")),
               key=lambda x:int(x.rsplit("_",1)[-1]))
    chosen=nav[-1] if nav else "odds_menu"
    menu_name=("official_odds_menu.html" if chosen=="odds_menu" else
               "official_odds_navigation_"+chosen.rsplit("_",1)[-1]+".html")
    menu=_verified_file(source,menu_name,steps[chosen])
    if not _html_race_identity(menu,race_spec.race_day,race_spec.venue,race_spec.race_number):
        raise SourceChainError("market_navigation_identity_conflict")
    if _date(steps[chosen]["captured_at_utc"])>=cutoff:
        raise SourceChainError("navigation_not_pre_cutoff")
    host="jra.jp" if channel=="PC" else "sp.jra.jp"
    links=find_market_links(menu,expected_race_day=race_spec.race_day,
                            expected_race_number=race_spec.race_number,expected_host=host)
    if links["source_final_odds_detected"]:
        raise SourceChainError("final_odds_navigation")
    link=links["markets"][market]
    if opener is None and not authorized_live_http:
        raise SourceChainError("live_http_not_authorized_zero_http")
    client=opener or build_opener(NoRedirect(),HTTPCookieProcessor(CookieJar()))
    pacer=pacer or RequestPacer()
    # Do not create output until all zero-HTTP provenance gates pass.
    target.mkdir()
    # Original chain remains untouched; copies are verified against immutable
    # prior receipts, so replay can audit the complete recovery independently.
    evidence=[("racecard","official_racecard.html",racecard),
              ("odds_menu","official_odds_menu.html",_verified_file(source,"official_odds_menu.html",steps["odds_menu"]))]
    if chosen!="odds_menu":
        evidence.append((chosen,menu_name,menu))
    recovery={"schema":"kyoto_missing_market_recovery.v1","race_id":race_spec.race_id,
              "channel":channel,"state":"CAPTURE_BLOCKED",
              "request_receipts":[],"recovered_market":market,
              "parent_receipt_sha256":sha256(receipt_path.read_bytes()).hexdigest(),
              "source_only":True,"prediction_ready":False}
    for step,name,raw in evidence:
        persisted=steps[step]
        persist_original_once(target,name,raw,persisted)
        recovery["request_receipts"].append(dict(persisted))
    try:
        if datetime.now(timezone.utc)>=cutoff and now_utc is None:
            raise SourceChainError("cutoff_reached_before_market_fetch")
        response=http_fetch(client,channel,link["official_post_url"],cname=link["cname"],
                            referer="https://"+host+"/JRADB/accessO.html",pacer=pacer)
        raw=response["raw"]
        # Preserve verified transport bytes before semantic validation, even on rejection.
        persist_original_once(target,market+"_original.html",raw,response)
        recovery["request_receipts"].append({"step":market,
           **{k:v for k,v in response.items() if k!="raw"}})
        recovery["state"]="MARKET_RAW_CAPTURED_VALIDATION_REJECTED"
        if not _html_race_identity(raw,race_spec.race_day,race_spec.venue,race_spec.race_number):
            raise SourceChainError("recovered_market_identity_mismatch")
        from diagnostics.kyoto_impl30_cancelled_market import parse_current_market
        parsed,_=parse_current_market(raw,market,active_runners,racecard=racecard,
            racecard_utc=steps["racecard"]["captured_at_utc"],market_utc=response["captured_at_utc"],
            start_utc=verified_start_utc,day=race_spec.race_day,race=race_spec.race_number)
        if parsed.get("historical_final_detected"):
            raise SourceChainError("recovered_final_odds_rejected")
        if _date(response["captured_at_utc"])>=_date(verified_start_utc):
            raise SourceChainError("recovery_after_start")
        recovery["state"]="MARKET_RAW_CAPTURED_REQUIRES_INDEPENDENT_GATE"
    except Exception as exc:
        recovery["reason"]=type(exc).__name__+":"+str(exc)[:160]
    finally:
        persist_receipt_once(target,"receipt.json",recovery)
    return recovery
