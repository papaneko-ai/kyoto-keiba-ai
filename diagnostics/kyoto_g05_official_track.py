"""G05 Kyoto official JRA track page with explicit same-day source isolation.

Official public Kyoto course page was independently located at the fixed
URL below; this URL is NOT derived from any PC race CNAME.
Original is saved even when the HTML is stale or unparseable.
"""
from __future__ import annotations
import hashlib,json,re
from datetime import datetime,timezone,date
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from diagnostics.kyoto_g04_all_horse_profiles import _utc

KYOTO_TRACK_PAGE="https://jra.jp/keiba/baba/index2.html"
MAX_HTML=1_500_000
class G05TrackRejected(ValueError):pass

def parse_kyoto_track(raw,day,source_url,captured_at_utc):
    if source_url!=KYOTO_TRACK_PAGE:
        raise G05TrackRejected("nonofficial_or_wrong_venue_track_source")
    if type(raw) is not bytes or not 0<len(raw)<=MAX_HTML:
        raise G05TrackRejected("invalid_official_track_original")
    stamp=_utc(captured_at_utc)
    if not re.fullmatch(r"20[0-9]{6}",day):
        raise G05TrackRejected("day_unverified")
    try:
        decoded=raw.decode("utf8",errors="strict")
    except UnicodeError:
        try:
            decoded=raw.decode("cp932",errors="strict")
        except UnicodeError as exc:
            raise G05TrackRejected("official_track_encoding_unverified") from exc
    soup=BeautifulSoup(decoded,"html.parser")
    # English translation or different encoding may alter selectors.
    # With no trustworthy same-day heading, retain originals only.
    text=soup.get_text(" ",strip=True)
    date_marker=f"{int(day[:4])}年{int(day[4:6])}月{int(day[6:])}日"
    headings=[h.get_text(" ",strip=True) for h in soup.select("h1,h2,h3")]
    meeting=[s for s in headings if "京都競馬" in s and date_marker in s]
    fresh=len(meeting)==1
    out={"schema":"kyoto_g05_kyoto_track.v1","day":day,
         "source_url":source_url,"captured_at_utc":stamp.isoformat(),
         "source_sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),
         "same_day_official_meeting_heading_verified":fresh,
         "data_asof_publication_time_utc_verified":False,
         "weather":None,"turf_going":None,"dirt_going":None,
         "cushion_value":None,"turf_moisture_finish_pct":None,
         "turf_moisture_turn4_pct":None,"dirt_moisture_finish_pct":None,
         "dirt_moisture_turn4_pct":None,
         "prediction_ready":False}
    if not fresh:
        out["state"]="MISSING_OR_STALE_KYOTO_MEETING_HEADING"
        return out
    # Locate weather and going only in the initial current meeting block, not
    # in older weekly weather tables or base explanatory materials.
    section=soup.select_one("#main, main, .main")
    contents=section.get_text(" ",strip=True) if section else text
    status=contents.split("週間情報")[0].split("芝のクッション値")[0]
    w=re.findall(r"天候\s*[:：]\s*(晴|曇|雨|小雨|雪|小雪)",status)
    out["weather"]=w[0] if len(set(w))==1 and w else None
    for surf,key in (("芝","turf_going"),("ダート","dirt_going")):
        m=re.findall(rf"(?:^|\s){surf}\s*(良|稍重|重|不良)(?=\s|$)",status)
        out[key]=m[0] if len(set(m))==1 and m else None
    # The official table is separate from explanatory condition tables.
    # Accept only the unique exact heading/column/row combination. Values
    # describe the saved observation; the measurement time is not inferred.
    moisture=[]
    for table in soup.select("table"):
        caption=table.find("caption")
        if caption is None or "".join(caption.stripped_strings)!="ゴール前と4コーナーの含水率":continue
        rows=[[c.get_text(" ",strip=True) for c in tr.find_all(["th","td"],recursive=False)] for tr in table.select("tr")]
        rows=[r for r in rows if r]
        if len(rows)!=3 or rows[0][-2:]!=["ゴール前","4コーナー"]:continue
        values={}
        for cells in rows[1:]:
            if len(cells)!=3 or cells[0] not in ("芝","ダート") or cells[0] in values:break
            if any(not re.fullmatch(r"(?:[0-9]{1,2}(?:\.[0-9]+)?|100(?:\.0+)?)\s*%?",v) for v in cells[1:]):break
            nums=[float(v.rstrip(" %")) for v in cells[1:]]
            if any(not 0<=v<=100 for v in nums):break
            values[cells[0]]=nums
        if set(values)=={"芝","ダート"}:moisture.append(values)
    if len(moisture)==1:
        for surface,prefix in (("芝","turf"),("ダート","dirt")):
            out[prefix+"_moisture_finish_pct"],out[prefix+"_moisture_turn4_pct"]=moisture[0][surface]
    out["state"]="SAME_DAY_KYOTO_SOURCE_SAVED_FIELDS_UNVERIFIED" if not any(
        out[key] is not None for key in ("weather","turf_going","dirt_going")
    ) else "SAME_DAY_KYOTO_SOURCE_PARTIALLY_PARSED"
    return out

def capture_kyoto_track(root,day,fetch,clock,*,allowed=False):
    if allowed is not True:raise G05TrackRejected("official_track_capture_not_authorized")
    root=Path(root)
    if not root.is_dir() or root.is_symlink():raise G05TrackRejected("unsafe_evidence_root")
    if (root/"g05_official_kyoto_track.html").exists() or (root/"g05_track_receipt.json").exists():
        raise G05TrackRejected("track_capture_already_exists")
    before=_utc(clock())
    raw=fetch(KYOTO_TRACK_PAGE)
    stamp=_utc(clock())
    if type(raw) is not bytes or not 0<len(raw)<=MAX_HTML:
        raise G05TrackRejected("invalid_http_original")
    (root/"g05_official_kyoto_track.html").write_bytes(raw)
    report=parse_kyoto_track(raw,day,KYOTO_TRACK_PAGE,stamp.isoformat())
    report["requested_at_utc"]=before.isoformat()
    (root/"g05_track_receipt.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
    return report
