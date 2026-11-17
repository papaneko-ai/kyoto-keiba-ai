"""G05: source-bound pre-race ground, weather, body mass and workout evidence.

Observe only already saved G03 official originals. No new network, no assumed
publication. A lack of workout provenance is UNKNOWN, not zero workouts.
Every value includes original SHA/UTC and a missingness state. A racecard's
capture timestamp is distinct from the publication time (usually unproven).
"""
from __future__ import annotations
import hashlib,json,re
from datetime import datetime,timezone,timedelta
from pathlib import Path
from bs4 import BeautifulSoup
from diagnostics.kyoto_g03_proof_verify import verify as verify_g03
from diagnostics.kyoto_g04_all_horse_profiles import _utc

class G05Rejected(ValueError):pass
FIELDS=("weather","turf_going","dirt_going","horse_body_weight_kg",
        "horse_body_weight_change_kg","workout")
MISSING="NOT_OBSERVED_IN_ARCHIVED_OFFICIAL_SOURCE"
_DAY=re.compile(r"20[0-9]{6}\Z")
_MASS=re.compile(r"^([3-6][0-9]{2})\s*(?:kg)?\s*(?:[（(]\s*([+-]?[0-9]{1,2})\s*[）)])?$")
_WX=re.compile(r"天候\s*[:：]?\s*(晴|曇|雨|小雨|雪|小雪)(?![ぁ-んァ-ン一-龥])")
_GOING=re.compile(r"(芝|ダート|ダ)\s*(?:馬場|コース)?\s*[:：]\s*(良|稍重|重|不良)(?![ぁ-んァ-ン一-龥])")
_WORKOUT_SOURCE="SOURCE_NOT_INDEPENDENTLY_OBSERVED"

def _ev(value,reason,sha,captured,filename,*,published=None):
    return {"value":value,"state":"OBSERVED" if value is not None else "MISSING",
            "missing_reason":None if value is not None else reason,
            "source_sha256":sha,"captured_at_utc":captured,
            "source_original":filename,
            "official_publication_at_utc":published,
            "publication_time_independently_verified":published is not None}

def _race_fields(raw):
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    # Only dedicated condition blocks count, never prior-performance text.
    sections=soup.select(".weather, .tenkou, .track-condition, .baba, .race-condition, #weather, #baba, #raceCondition")
    strings=[x.get_text(" ",strip=True) for x in sections if x.get_text(" ",strip=True)]
    extracted={}
    for key,pattern in (("weather",_WX),("ground",_GOING)):
        matches=[]
        for chunk in strings:
            matches+=list(pattern.finditer(chunk))
        if key=="weather":
            values={m.group(1) for m in matches}
            extracted[key]=next(iter(values)) if len(values)==1 else None
        else:
            for surface in ("turf_going","dirt_going"):
                matches2={m.group(2) for m in matches
                    if (m.group(1)=="芝")== (surface=="turf_going")}
                extracted[surface]=next(iter(matches2)) if len(matches2)==1 else None
    return extracted

def _body_weights(raw,expected_numbers):
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    tables=[t for t in soup.select("table") if
            all(t.select_one("th."+key) for key in ("horse","num","waku"))]
    if len(tables)!=1:raise G05Rejected("unverified_racecard_table")
    table=tables[0]
    headings=[th.get_text(" ",strip=True) for th in table.select("tr")[0].find_all("th",recursive=False)]
    indices=[i for i,value in enumerate(headings) if "馬体重" in value]
    result={}
    for tr in table.select("tr"):
        number=tr.select_one("td.num")
        if number is None or not number.get_text(strip=True).isdigit():continue
        num=int(number.get_text(strip=True))
        value=None;change=None
        cells=tr.find_all("td",recursive=False)
        direct=tr.select("td.bodyweight, td.body-weight, td.batai, td.horse-weight")
        candidate=direct[0] if len(direct)==1 else None
        if candidate is None and len(indices)==1 and len(cells)==len(headings):
            candidate=cells[indices[0]]
        if candidate is not None:
            text=candidate.get_text(" ",strip=True)
            match=_MASS.fullmatch(text)
            if match:
                value=int(match.group(1))
                if match.group(2) is not None:change=int(match.group(2))
        if num in result:raise G05Rejected("duplicate_weight_row")
        result[num]=(value,change)
    if set(result)!=set(expected_numbers):raise G05Rejected("body_weight_roster_mismatch")
    return result

def compile_saved(root,*,day,expected_cutoff_utc=None):
    root=Path(root)
    if type(day) is not str or not _DAY.fullmatch(day):
        raise G05Rejected("day_invalid")
    if root.is_symlink() or not root.is_dir():
        raise G05Rejected("source_root_invalid")
    proof=verify_g03(root,expected_day=day)
    if proof["races_verified"]!=12:raise G05Rejected("not_all_12r_proven")
    receipt=json.loads((root/"g03_receipt.json").read_text(encoding="utf8"))
    if (root/"g05_receipt.json").exists():raise G05Rejected("g05_receipt_already_exists")
    results={};verified_values=0
    for race in range(1,13):
        info=receipt["races"][str(race)]
        path=root/f"g03_official_racecard_{race:02d}.html"
        raw=path.read_bytes()
        sha=hashlib.sha256(raw).hexdigest()
        if sha!=info["original_sha256"]:raise G05Rejected("g05_original_sha_conflict")
        captured=_utc(info["captured_at_utc"])
        start=datetime.fromisoformat(
            f"{day[:4]}-{day[4:6]}-{day[6:]}T{info['start_time_jst']}:00+09:00").astimezone(timezone.utc)
        if expected_cutoff_utc is not None and captured>_utc(expected_cutoff_utc):
            raise G05Rejected("source_after_requested_cutoff")
        if captured>=start:raise G05Rejected("post_start_source_cannot_be_promoted")
        values=_race_fields(raw)
        horses=_body_weights(raw,[x["number"] for x in info["runners"]])
        basename=path.name
        track={}
        for field in ("weather","turf_going","dirt_going"):
            value=values.get(field)
            track[field]=_ev(value,MISSING,sha,captured.isoformat(),basename)
            verified_values+=value is not None
        mass={}
        for horse in info["runners"]:
            number=horse["number"]
            val,delta=horses[number]
            mass[str(number)]={
                "horse_name":horse["name"],"horse_number":number,
                "body_weight_kg":_ev(val,MISSING,sha,captured.isoformat(),basename),
                "body_weight_change_kg":_ev(delta,MISSING,sha,captured.isoformat(),basename),
                "workout":_ev(None,_WORKOUT_SOURCE,sha,captured.isoformat(),basename)}
            verified_values+=sum(v is not None for v in (val,delta))
        results[str(race)]={"race":race,"start_utc":start.isoformat(),
                            "original_sha256":sha,"observed_source_url":info["source_url"],
                            "track":track,"horses":mass}
    report={"schema":"kyoto_g05_source_evidence.v1","day":day,
            "g03_races_verified":12,"races":results,"observed_field_values":verified_values,
            "weather_going_bodyweight_path_prepared":True,
            "workout_external_source_discovered":False,
            "workout_status":"SOURCE_NOT_INDEPENDENTLY_OBSERVED",
            "unverified_publication_timestamps":True,
            "empty_is_not_zero":True,
            "future_jra_capture_claimed":False,"prediction_ready":False,
            "pre_event_source_contract_testable":True}
    (root/"g05_receipt.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n",
        encoding="utf8")
    return report
