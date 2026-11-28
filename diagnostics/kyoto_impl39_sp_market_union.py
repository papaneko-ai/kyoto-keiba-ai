"""Independent SP market originals can fill PC-bound day gaps, never roster denominators."""
from hashlib import sha256
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
import json
from diagnostics.kyoto_impl30_day_coverage import digest,proof,MARKETS
from diagnostics.kyoto_impl31_sp_saved_roster_audit import utc,exact_mobile_race
from diagnostics.jra_pc_sp_benchmark import sp_rows
from diagnostics.jra_one_shot_market_capture import exact_odds_action,observed_next_market_action
from diagnostics.jra_market_source_chain import _html_race_identity
from diagnostics.jra_official_market_navigation import find_market_links
from diagnostics.kyoto_impl30_cancelled_market import parse_current_market
from diagnostics.jra_market_integrity_gate import MarketEvidence,check

def context(slots,day):
    # The caller passes only independently reopened authenticated PC/auxiliary slots.
    result={}
    for n in map(str,range(1,13)):
        found=[]
        for s in slots:
            if s.get("day")!=day:continue
            x=s.get("races",{}).get(n)
            if not x:continue
            try:
                row={k:x[k] for k in ("roster_digest","named_roster_digest","start_utc")}
                row["numbers"]=sorted(int(k) for k in x["horses"])
                if utc(x["racecard"]["utc"])>=utc(row["start_utc"]):continue
                found.append(row)
            except (KeyError,TypeError,ValueError,AttributeError):continue
        if found and all(x==found[0] for x in found):result[n]=found[0]
    return result

def assess(root,day,run_id,post,rosters,pc_context):
    root=Path(root)
    out={"day":day,"run_id":str(run_id),"races":{},"network_requests":0}
    if day!="20261129" or post.get("day")!=day or post.get("channel")!="SP":return out
    verified={x["filename"]:x for x in post.get("source_rows",[])}
    for n,pc in pc_context.items():
        try:
            number=int(n)
            if n!=str(number) or not 1<=number<=12:continue
            observed=rosters["races"][n]
            if observed["state"] not in ("SP_STRUCTURAL_ROSTER_OBSERVED","SP_SPLIT_LAYOUT_OBSERVED","SP_SPLIT_LAYOUT_PARTIAL"):continue
            if post["sp_race_integrity"][n]["state"]!="DIGEST_UTC_CHECKED_ONLY":continue
            prefix=f"r{number:02d}_"
            rec=json.loads((root/(prefix+"sp_receipt.json")).read_text(encoding="utf8"))
            url=rec["observed_sp_source_url"]
            if not exact_mobile_race(url,day,number):continue
            host=urlsplit(url).hostname
            start=utc(pc["start_utc"])
            def raw_at(name):
                p=root/(prefix+name);m=verified[p.name]
                if not p.is_file() or p.is_symlink() or not 0<p.stat().st_size<=1500000:raise ValueError("sp_original")
                raw=p.read_bytes();stamp=utc(m["captured_at_utc"])
                if sha256(raw).hexdigest()!=m["sha256"] or stamp.strftime("%Y%m%d")!=day or stamp>=start:raise ValueError("sp_original_time")
                return raw,stamp,m["sha256"]
            card,card_time,card_sha=raw_at("official_sp_racecard.html")
            if card_sha!=observed["source_sha256"] or card_time!=utc(observed["captured_at_utc"]):continue
            named=sp_rows(card)
            if digest(named)!=pc["named_roster_digest"] or [x[0] for x in named]!=pc["numbers"]:continue
            registered=tuple((n,f) for n,f,_ in named)
            token=exact_odds_action(card,"SP")
            if token!=rec.get("sp_odds_menu_action"):continue
            menu,menu_time,_=raw_at("official_sp_odds_menu.html")
            if menu_time<card_time:continue
            for i in (1,2):
                name=f"official_sp_odds_navigation_{i}.html"
                if prefix+name not in verified:
                    if i==1 and prefix+"official_sp_odds_navigation_2.html" in verified:raise ValueError("navigation_gap")
                    break
                expected=observed_next_market_action(menu,"SP",SimpleNamespace(race_day=day,race_number=number),step=i-1)
                if rec.get(f"sp_odds_navigation_{i}_action")!=expected:raise ValueError("navigation_action")
                following,stamp,_=raw_at(name)
                if stamp<menu_time:raise ValueError("navigation_time")
                menu,menu_time=following,stamp
            if not _html_race_identity(menu,day,"京都",number):continue
            links=find_market_links(menu,expected_race_day=day,expected_race_number=number,expected_host=host)
            if links["source_final_odds_detected"]:continue
            row={**{k:pc[k] for k in ("roster_digest","named_roster_digest","start_utc")},"markets":{},"paired_same_slot":False}
            for market in MARKETS:
                try:
                    raw,stamp,sha=raw_at(f"official_sp_{market}_odds.html")
                    link=links["markets"][market]
                    if stamp<menu_time or rec.get(f"sp_{market}_action")!=link["cname"] or not _html_race_identity(raw,day,"京都",number):continue
                    parsed,effective=parse_current_market(raw,market,registered,racecard=card,racecard_utc=card_time.isoformat(),market_utc=stamp.isoformat(),start_utc=start.isoformat(),day=day,race=number)
                    quotes=tuple((p["pair"][0],p["pair"][1],p["odds"]) for p in parsed["pairs"])
                    if parsed["historical_final_detected"]:continue
                    result=check(MarketEvidence(f"{day}_KYOTO_{number}R",market,"LIVE_PRE_RACE",link["official_post_url"],stamp.isoformat(),sha,len(raw),tuple(effective),quotes,True,True),race_start_utc=start.isoformat(),source_bytes=raw)
                    if not result["usable"]:continue
                    row["markets"][market]={**proof(sha,stamp.isoformat(),sha),"channel":"SP","pair_count":len(quotes),"cancelled_horses":parsed.get("cancelled_horses",[])}
                except (KeyError,ValueError,TypeError,OSError,AttributeError,IndexError):continue
            a,b=(row["markets"].get(m) for m in MARKETS)
            row["paired_same_slot"]=bool(a and b and a["cancelled_horses"]==b["cancelled_horses"])
            if row["markets"]:out["races"][n]=row
        except (KeyError,ValueError,TypeError,OSError,AttributeError,IndexError):continue
    return out
