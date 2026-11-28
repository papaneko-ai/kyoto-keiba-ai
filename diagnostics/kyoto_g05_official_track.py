"""G05 Kyoto official JRA track page with explicit same-day source isolation.

Official public Kyoto course page was independently located at the fixed
URL below; this URL is NOT derived from any PC race CNAME.
Original is saved even when the HTML is stale or unparseable.
"""
from __future__ import annotations
import hashlib,json,re
from datetime import datetime,timezone,date,timedelta
from pathlib import Path
from urllib.parse import urlsplit
from urllib.error import HTTPError
from bs4 import BeautifulSoup
from diagnostics.kyoto_g04_all_horse_profiles import _utc

# Public JRA Kyoto page indexed at this exact canonical origin, 2026-11-28.
# Preserve the old exact URL for authenticated historical replay only.
KYOTO_TRACK_PAGE="https://www.jra.go.jp/keiba/baba/index2.html"
LEGACY_KYOTO_TRACK_PAGE="https://jra.jp/keiba/baba/index2.html"
MAX_HTML=1_500_000
class G05TrackRejected(ValueError):pass

def parse_kyoto_track(raw,day,source_url,captured_at_utc):
    if source_url not in (KYOTO_TRACK_PAGE,LEGACY_KYOTO_TRACK_PAGE):
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
    fresh=len(meeting)==1 and "前日" not in meeting[0]
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
    # A matching meeting heading does not date the individual observations.
    jst=timezone(timedelta(hours=9))
    def asof(value):
        t=re.search(r"(?:(\d{4})年\s*)?(\d{1,2})月\s*(\d{1,2})日(?:\s*[（(][月火水木金土日]曜(?:日)?[）)])?\s*(正午|\d{1,2}時(?:\s*\d{1,2}分)?)",value)
        if not t:return None
        try:
            year=int(t.group(1) or day[:4]);month=int(t.group(2));dd=int(t.group(3))
            clock=t.group(4)
            if clock=="正午":hour,minute=12,0
            else:
                m=re.fullmatch(r"(\d{1,2})時(?:\s*(\d{1,2})分)?",clock)
                hour,minute=int(m.group(1)),int(m.group(2) or 0)
            dt=datetime(year,month,dd,hour,minute,tzinfo=jst)
            if dt.strftime("%Y%m%d")!=day or dt>stamp:return None
            return dt.astimezone(timezone.utc).isoformat()
        except (ValueError,AttributeError):return None
    blocks=soup.select("div.line.condition")
    current=None;condition_stamp=None
    if len(blocks)==1:
        headers=blocks[0].select("div.block_header h3")
        if len(headers)==1:
            condition_stamp=asof(headers[0].get_text(" ",strip=True))
            current=blocks[0].select_one("div.grid") if condition_stamp else None
    elif not blocks:
        headers=[h for h in soup.select("h3") if h.get_text(" ",strip=True).startswith("馬場状態")]
        if len(headers)==1:
            condition_stamp=asof(headers[0].get_text(" ",strip=True))
            current=headers[0].parent if condition_stamp else None
    if current is not None:
        status=current.get_text(" ",strip=True)
        w=re.findall(r"天候\s*[:：]\s*(晴|曇|雨|小雨|雪|小雪)(?![ぁ-んァ-ン一-龥])",status)
        out["weather"]=w[0] if len(set(w))==1 and w else None
        for surf,key in (("芝","turf_going"),("ダート","dirt_going")):
            m=re.findall(rf"(?:^|\s){surf}\s*(良|稍重|重|不良)(?=\s|$)",status)
            out[key]=m[0] if len(set(m))==1 and m else None
    out["condition_observation_utc"]=condition_stamp
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
    # Preserve measurements with unknown dates, but do not grant target-day credit.
    out["moisture_observation_utc"]=None
    out["undated_moisture_observations"]={}
    if len(moisture)==1:
        blocks=soup.select("div.line.moist")
        if len(blocks)==1:
            times=blocks[0].select("div.grid")
            if len(times)==1 and "測定時刻" in times[0].get_text(" ",strip=True):
                out["moisture_observation_utc"]=asof(times[0].get_text(" ",strip=True))
        for surface,prefix in (("芝","turf"),("ダート","dirt")):
            for suffix,value in zip(("finish_pct","turn4_pct"),moisture[0][surface]):
                k=prefix+"_moisture_"+suffix
                if out["moisture_observation_utc"]:out[k]=value
                else:out["undated_moisture_observations"][k]=value
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
    phase="FETCH"
    try:
        raw=fetch(KYOTO_TRACK_PAGE)
        phase="VALIDATE_ORIGINAL"
        stamp=_utc(clock())
        if type(raw) is not bytes or not 0<len(raw)<=MAX_HTML:
            raise G05TrackRejected("invalid_http_original")
        (root/"g05_official_kyoto_track.html").write_bytes(raw)
        phase="PARSE"
        report=parse_kyoto_track(raw,day,KYOTO_TRACK_PAGE,stamp.isoformat())
    except Exception as exc:
        # Preserve a safe, authenticated failure receipt; never credit a failed
        # response as data, follow a redirect, or spend another HTTP request.
        failed={"schema":"kyoto_g05_track_failure.v1","day":day,
                "source_url":KYOTO_TRACK_PAGE,"requested_at_utc":before.isoformat(),
                "state":"TRACK_"+phase+"_FAILED","error_class":type(exc).__name__,
                "prediction_ready":False}
        if isinstance(exc,HTTPError) and type(exc.code) is int and 100<=exc.code<=599:
            failed["http_status"]=exc.code
            failed["error_code"]="HTTP_STATUS_"+str(exc.code)
        if phase=="PARSE":
            failed.update(source_sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
                          captured_at_utc=stamp.isoformat())
        (root/"g05_track_receipt.json").write_text(
            json.dumps(failed,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
        raise
    report["requested_at_utc"]=before.isoformat()
    (root/"g05_track_receipt.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
    return report
