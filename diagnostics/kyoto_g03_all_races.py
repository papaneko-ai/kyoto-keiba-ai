"""G03 official saved-original Kyoto 1-12R roster audit. Never guesses links."""
from __future__ import annotations
import hashlib, json, re
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlsplit, parse_qs
from diagnostics.jra_official_link_repair import observed_links

class G03Error(ValueError): pass
CoverageRejected=G03Error

def links(original, parent, day):
    if not re.fullmatch(r"20\d{6}", day): raise G03Error("invalid_day")
    if urlsplit(parent).hostname != "jra.jp": raise G03Error("untrusted_meeting")
    soup=BeautifulSoup(original.decode("cp932",errors="replace"),"html.parser")
    found={r:set() for r in range(1,13)}
    for a in soup.select("a[href]"):
        title=a.get_text(" ",strip=True)
        match=re.search(r"(?<!\d)(1[0-2]|0?[1-9])\s*(?:R|レース)(?!\d)",title,re.I)
        if not match: continue
        race=int(match.group(1)); url=urljoin(parent,a["href"]); p=urlsplit(url)
        q=parse_qs(p.query)
        if (p.scheme!="https" or p.hostname!="jra.jp" or p.path!="/JRADB/accessD.html"
            or p.fragment or set(q)!={"CNAME"} or len(q["CNAME"])!=1): continue
        token=q["CNAME"][0]
        if re.fullmatch(r"pw[A-Za-z0-9]+/[A-Za-z0-9]+",token) and f"{race:02d}{day}" in token:
            found[race].add(url)
    if any(len(v)>1 for v in found.values()): raise G03Error("ambiguous_race_link")
    return {r:next(iter(v)) for r,v in found.items() if v}

def parse(raw, day, race, url, utc):
    stamp=datetime.fromisoformat(utc.replace("Z","+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset().total_seconds()!=0: raise G03Error("timestamp_not_utc")
    if not 0<len(raw)<=1500000: raise G03Error("invalid_original")
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    # Reuse the existing validated historical PC racecard parser; its checks
    # bind the HTML's date, race number, horse numbers and frame order.
    from diagnostics.jra_multi_capture_20261106 import parse as pc_parse
    meeting_date=f"{day[:4]}-{day[4:6]}-{day[6:]}"
    rows,errors=pc_parse(raw,race,meeting_date=meeting_date)
    if errors:
        raise G03Error("official_roster_identity_invalid:"+",".join(sorted(set(errors))))
    if not 2<=len(rows)<=18:
        raise G03Error("incomplete_roster")
    horses=[{"number":row["horse_number"],
             "name":row["horse_name"],
             "frame":row["frame_number"],
             "profile_navigation":row["horse_profile_href"],
             "past_race_dates":row["past_race_dates"],
             "permanent_id":None} for row in rows]
    text=soup.get_text(" ",strip=True)
    if "京都" not in text:
        raise G03Error("kyoto_venue_not_in_original")
    times=set(re.findall(r"発走(?:予定)?(?:時刻)?\s*[:：]?\s*([01]?\d|2[0-3]):([0-5]\d)",soup.get_text(" ",strip=True)))
    if len(times)!=1: raise G03Error("start_time_not_proven")
    hh,mm=next(iter(times))
    return {"local_race_key":f"KYOTO:{day}:{race:02d}","official_race_id_verified":False,"race":race,
            "start_time_jst":f"{int(hh):02d}:{mm}","runner_count":len(horses),"runners":horses,
            "url":url,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),"utc":utc}

def audit(day, meeting_original, meeting_url, fetch, utc, output):
    """fetch must implement existing bounded official-only/no-redirect/paced transport."""
    root=Path(output)
    if root.exists() or root.is_symlink() or not root.parent.is_dir(): raise G03Error("output_not_fresh")
    root.mkdir()
    (root/"official_meeting.html").write_bytes(meeting_original)
    observed=links(meeting_original,meeting_url,day)
    report={"schema":"kyoto_g03_all_races.v1","day":day,"meeting_sha256":hashlib.sha256(meeting_original).hexdigest(),
            "observed_races":sorted(observed),"races":{},"complete":False,"prediction_ready":False}
    for race in range(1,13):
        if race not in observed:
            report["races"][str(race)]={"state":"LINK_MISSING"};continue
        try:
            raw=fetch(observed[race])
            if type(raw) is not bytes or not 0<len(raw)<=1500000: raise G03Error("invalid_http_original")
            file=f"official_racecard_{race:02d}.html"
            (root/file).write_bytes(raw)
            result=parse(raw,day,race,observed[race],utc())
            report["races"][str(race)]={"state":"ROSTER_START_VERIFIED_OFFLINE","file":file,**result}
        except Exception as error:
            report["races"][str(race)]={"state":"FAILED","reason":type(error).__name__,"message":str(error)[:120]}
    report["missing"]=[r for r in range(1,13) if report["races"][str(r)]["state"]!="ROSTER_START_VERIFIED_OFFLINE"]
    report["complete"]=not report["missing"]
    (root/"g03_receipt.json").write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
    return report


# Stable production adapter used by the pinned development capture workflow.
def acquire_all(*,day,root,meeting_raw,meeting_url,fetch,captured_at_utc,allowed=False):
    if allowed is not True: raise CoverageRejected("explicit_capture_authorization_required")
    root=Path(root)
    if root.exists() or root.is_symlink() or not root.parent.is_dir():
        raise CoverageRejected("fresh_output_directory_required")
    root.mkdir()
    (root/"official_meeting.html").write_bytes(meeting_raw)
    found=links(meeting_raw,meeting_url,day)
    report={"schema":"kyoto_g03_all_races.v1","day":day,"meeting_url":meeting_url,
            "meeting_sha256":hashlib.sha256(meeting_raw).hexdigest(),
            "observed_races":sorted(found),"races":{},"complete":False,"prediction_ready":False}
    for race in range(1,13):
        if race not in found:
            report["races"][str(race)]={"state":"OFFICIAL_LINK_NOT_OBSERVED"};continue
        try:
            raw=fetch(found[race])
            if type(raw) is not bytes or not 0<len(raw)<=1500000:raise CoverageRejected("invalid_response")
            filename=f"official_racecard_{race:02d}.html"
            (root/filename).write_bytes(raw)
            details=parse(raw,day,race,found[race],captured_at_utc())
            report["races"][str(race)]={"state":"ROSTER_AND_START_VERIFIED_OFFLINE",
                    "original_file":filename,"original_sha256":details["sha256"],
                    "runner_count":details["runner_count"],"start_time_jst":details["start_time_jst"],
                    "local_race_key":details["local_race_key"],"official_race_id_verified":False,
                    "runners":details["runners"],"captured_at_utc":details["utc"]}
        except Exception as exc:
            report["races"][str(race)]={"state":"SOURCE_OR_PARSE_FAILED",
                    "error":type(exc).__name__,"reason":str(exc)[:140]}
    report["missing_races"]=[r for r in range(1,13)
                            if report["races"][str(r)]["state"]!="ROSTER_AND_START_VERIFIED_OFFLINE"]
    report["complete"]=not report["missing_races"]
    (root/"g03_receipt.json").write_text(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    return report
