"""End-to-end offline evidence gate for official JRA odds source originals.

A valid page title or parse success alone does not authorize pre-race use.
Inputs: source-original bytes, externally verified race identity/start, time,
and independent frozen starter roster. No HTTP, DB, model or auto-switch.
"""
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path
from hashlib import sha256
import re
from diagnostics.jra_official_market_navigation import find_market_links
from diagnostics.jra_odds_matrix_parser import parse_matrix
from diagnostics.jra_market_integrity_gate import MarketEvidence,check
from diagnostics.jra_odds_source_archive import freeze_once

class SourceChainError(ValueError):pass

def _html_race_identity(raw,day,venue,race):
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    text=soup.get_text(" ",strip=True)
    if not re.fullmatch(r"20\d{6}",day):return False
    year,month,date=int(day[:4]),int(day[4:6]),int(day[6:])
    return re.search(fr"{year}年\s*{month}月\s*{date}日.{{0,30}}?{re.escape(venue)}.{{0,30}}?{race}\s*レース",text) is not None

def audit_source_originals(menu_raw,market_raw,market_urls,*,race_key,
        race_day,venue,race_number,channel,captured_at_utc,
        verified_start_utc,active_runners,historical=False,
        archive_directory=None, market_captured_at_utc=None):
    """Only a validated live 2-market source can be archived; never auto-predict."""
    if channel not in ("PC","SP"):raise SourceChainError("invalid_channel")
    if not _html_race_identity(menu_raw,race_day,venue,race_number):
        raise SourceChainError("menu_race_identity_not_proven")
    official_host="sp.jra.jp" if channel=="SP" else "jra.jp"
    links=find_market_links(menu_raw,expected_race_day=race_day,
                            expected_race_number=race_number,expected_host=official_host)
    if len(active_runners)<2 or len({n for n,f in active_runners})!=len(active_runners):
        raise SourceChainError("unverified_runner_numbers")
    phase_final=links["source_final_odds_detected"]
    output={"schema_version":"jra_market_source_chain.v1",
            "race_key":race_key,"race_day":race_day,"race_number":race_number,
            "channel":channel,"captured_at_utc":captured_at_utc,
            "menu_sha256":sha256(menu_raw).hexdigest(),
            "markets":{},"historical_final_quarantined":False,
            "prediction_ready":False,"training_ready":False}
    if market_captured_at_utc is None:
        # Backward-compatible offline single-fixture audit only. Actual live
        # multi-request capture must provide separate timestamps for both.
        if archive_directory is not None:
            raise SourceChainError("individual_market_capture_times_required")
        market_captured_at_utc={m:captured_at_utc for m in ("quinella","bracket_quinella")}
    if set(market_captured_at_utc)!={"quinella","bracket_quinella"}:
        raise SourceChainError("both_market_capture_times_required")
    staged=[]
    for market in ("quinella","bracket_quinella"):
        raw=market_raw.get(market);url=market_urls.get(market)
        if not isinstance(raw,bytes) or not isinstance(url,str):
            raise SourceChainError("both_market_originals_required")
        if not _html_race_identity(raw,race_day,venue,race_number):
            raise SourceChainError("market_race_identity_not_proven")
        data=parse_matrix(raw,market,expected_runners=len(active_runners) if market=="quinella" else None)
        if data["historical_final_detected"]!=phase_final:
            raise SourceChainError("conflicting_market_phases")
        phase="HISTORICAL_FINAL" if historical or phase_final else "LIVE_PRE_RACE"
        quotes=tuple((q["pair"][0],q["pair"][1],q["odds"]) for q in data["pairs"])
        evidence=MarketEvidence(race_key,market,phase,url,market_captured_at_utc[market],
                data["source_sha256"],len(raw),tuple(active_runners),quotes,True,True)
        verdict=check(evidence,race_start_utc=verified_start_utc,source_bytes=raw)
        output["markets"][market]={
            "source_sha256":data["source_sha256"],"source_bytes":len(raw),
            "pair_count":len(quotes),"phase":phase,
            "captured_at_utc":market_captured_at_utc[market],
            "integrity_state":verdict["state"],"reason":verdict.get("reason"),
            "pre_race_usable":verdict["usable"]}
        staged.append((market,raw,url,data,verdict))
    if historical:
        if any(x[4]["usable"] for x in staged):
            raise SourceChainError("historical_market_must_not_be_live")
        output["classification"]="QUARANTINED_HISTORICAL_FINAL"
        output["historical_final_quarantined"]=True
        return output
    if not all(x[4]["usable"] for x in staged):
        output["classification"]="BLOCKED_SOURCE_INTEGRITY"
        return output
    output["classification"]="VALIDATED_LIVE_MARKETS_NOT_PREDICTION_RELEASED"
    if archive_directory is not None:
        # Once per individual market; if a race's second market fails, do not
        # claim combined release. Both markets have been validated before writes.
        for market,raw,url,data,verdict in staged:
            receipt={"channel":channel,"market":market,
                "source_phase":"LIVE_PRE_RACE",
                "source_sha256":data["source_sha256"],"source_bytes":len(raw),
                "official_race_identity_verified":True,"source_url":url,
                "captured_at_utc":market_captured_at_utc[market],"race_id":race_key,
                "usage":"SOURCE_ONLY",
                "market_integrity_state":verdict["state"],
                "market_pair_count":len(data["pairs"])}
            output["markets"][market]["archive"]=freeze_once(archive_directory,
               receipt,raw,race_start_utc=verified_start_utc)
    return output
