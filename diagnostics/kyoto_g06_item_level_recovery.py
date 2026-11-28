"""Verify saved PC/SP market originals independently; no network or URL synthesis."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from diagnostics.jra_market_source_chain import _html_race_identity
from diagnostics.jra_official_market_navigation import find_market_links
from diagnostics.jra_odds_matrix_parser import parse_matrix
from diagnostics.kyoto_g06_roster_aware_bracket import parse_bracket_with_roster
from diagnostics.jra_market_integrity_gate import MarketEvidence, check

MARKETS=("quinella","bracket_quinella")
FILES={"quinella":"quinella_original.html","bracket_quinella":"bracket_quinella_original.html"}

def _read_verified(directory,name,step):
    path=directory/name
    if path.is_symlink() or not path.is_file():
        raise ValueError("original_missing")
    raw=path.read_bytes()
    if not raw or len(raw)!=step.get("bytes") or sha256(raw).hexdigest()!=step.get("sha256"):
        raise ValueError("original_receipt_mismatch")
    return raw

def _utc(value):
    if not isinstance(value,str):
        raise ValueError("invalid_utc")
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None or dt.utcoffset()!=timezone.utc.utcoffset(None):
        raise ValueError("non_utc_time")
    return dt

def recover_saved_markets(folder, *, race_spec,active_runners,verified_start_utc):
    """Keep individually verified market and time, never equate cross-channel quotes."""
    folder=Path(folder)
    cutoff=_utc(verified_start_utc)
    verified={}
    blocked=[]
    for channel,subdirectory in (("PC","pc"),("SP","sp"),
                                 ("PC","pc_recovery"),("SP","sp_recovery")):
        directory=folder/subdirectory
        receipt_file=directory/"receipt.json"
        if receipt_file.is_symlink() or not receipt_file.is_file():
            continue
        try:
            rec=json.loads(receipt_file.read_text(encoding="utf-8"))
            if rec.get("race_id")!=race_spec.race_id or rec.get("channel")!=channel:
                raise ValueError("receipt_race_channel_mismatch")
            if rec.get("state") in ("REJECT_FINAL_ODDS","OFFICIAL_NOT_PUBLISHED","CUTOFF_PASSED_NO_HTTP","WAIT_FOR_OFFICIAL_SALES"):
                raise ValueError("unsafe_market_phase")
            steps={x["step"]:x for x in rec["request_receipts"]}
            if "racecard" not in steps or "odds_menu" not in steps:
                raise ValueError("missing_racecard_or_menu_receipt")
            racecard=_read_verified(directory,"official_racecard.html",steps["racecard"])
            if not _html_race_identity(racecard,race_spec.race_day,race_spec.venue,race_spec.race_number):
                raise ValueError("racecard_identity_mismatch")
            menu_step="odds_menu"
            nav=sorted((k for k in steps if k.startswith("odds_navigation_")),key=lambda s:int(s.rsplit("_",1)[-1]))
            if nav:
                menu_step=nav[-1]
            menu_file=("official_odds_menu.html" if menu_step=="odds_menu"
                       else "official_odds_navigation_"+menu_step.rsplit("_",1)[-1]+".html")
            menu=_read_verified(directory,menu_file,steps[menu_step])
            if not _html_race_identity(menu,race_spec.race_day,race_spec.venue,race_spec.race_number):
                raise ValueError("menu_identity_mismatch")
            host="sp.jra.jp" if channel=="SP" else ("www.jra.go.jp" if race_spec.race_day=="20261129" and race_spec.pc_racecard_url.startswith("https://www.jra.go.jp/") else "jra.jp")
            links=find_market_links(menu,expected_race_day=race_spec.race_day,
                expected_race_number=race_spec.race_number,expected_host=host)
            if links["source_final_odds_detected"]:
                raise ValueError("final_odds_menu")
            for market in MARKETS:
                if market not in steps:
                    continue
                try:
                    step=steps[market]
                    raw=_read_verified(directory,FILES[market],step)
                    if not _html_race_identity(raw,race_spec.race_day,race_spec.venue,race_spec.race_number):
                        raise ValueError("market_identity_mismatch")
                    if _utc(step["captured_at_utc"])>=cutoff or _utc(steps[menu_step]["captured_at_utc"])>=cutoff:
                        raise ValueError("after_start")
                    link=links["markets"][market]
                    if (step.get("requested_url")!=link["official_post_url"] or
                        step.get("observed_action_token")!=link["cname"] or step.get("method")!="POST"):
                        raise ValueError("unobserved_market_action")
                    from diagnostics.kyoto_impl30_cancelled_market import parse_current_market
                    parsed,effective=parse_current_market(raw,market,active_runners,racecard=racecard,
                        racecard_utc=steps["racecard"]["captured_at_utc"],market_utc=step["captured_at_utc"],
                        start_utc=verified_start_utc,day=race_spec.race_day,race=race_spec.race_number)
                    if parsed["historical_final_detected"]:
                        raise ValueError("final_odds_original")
                    quotes=tuple((p["pair"][0],p["pair"][1],p["odds"]) for p in parsed["pairs"])
                    validation=check(MarketEvidence(race_spec.race_id,market,"LIVE_PRE_RACE",
                        step["requested_url"],step["captured_at_utc"],step["sha256"],len(raw),
                        tuple(effective),quotes,True,True),
                        race_start_utc=verified_start_utc,source_bytes=raw)
                    if not validation["usable"]:
                        raise ValueError("market_gate:"+validation["reason"])
                    row={"channel":channel,"source_url":step["requested_url"],
                        "sha256":step["sha256"],"captured_at_utc":step["captured_at_utc"],
                        "pair_count":len(quotes),"cancelled_horses":parsed.get("cancelled_horses",[]),"source_menu_sha256":steps[menu_step]["sha256"]}
                    verified.setdefault(market,[]).append(row)
                except (ValueError,KeyError,TypeError,IndexError) as exc:
                    blocked.append({"channel":channel,"market":market,"reason":str(exc)[:150]})
        except (ValueError,KeyError,TypeError,IndexError,OSError) as exc:
            blocked.append({"channel":channel,"market":None,"reason":str(exc)[:150]})
    attempts={}
    for market in MARKETS:
        if market in verified:
            candidates=sorted(verified[market],key=lambda x:(x["captured_at_utc"],x["channel"]))
            attempts[market]={"state":"VERIFIED","selected":candidates[0],"candidates":candidates}
        else:
            attempts[market]={"state":"PENDING_RECOVERY","selected":None,"candidates":[]}
    good=all(attempts[m]["state"]=="VERIFIED" for m in MARKETS)
    selected=[attempts[m]["selected"] for m in MARKETS if attempts[m]["selected"]]
    # Never merge incompatible active rosters. Preserve verified individual
    # observations for diagnosis, but block combined market certification.
    conflict=len({tuple(x.get("cancelled_horses",[])) for x in selected})>1
    if conflict:
        good=False
        blocked.append({"channel":None,"market":None,"reason":"cross_market_cancellation_conflict"})
    return {"schema":"kyoto_g06_item_level_recovery.v1","race_id":race_spec.race_id,
        "markets":attempts,"blocked_evidence":blocked,"both_markets_verified":good,
        "cancellation_conflict":conflict,
        "mixed_channel":good and len({x["channel"] for x in selected})>1,
        "simultaneous_snapshot_asserted":False,"prediction_ready":False,
        "g06_certified":False,"network_requests":0}
