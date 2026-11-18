"""H04 provenance-preserving partial training read from observed historical HTML."""
from hashlib import sha256
from datetime import datetime
from urllib.parse import urlsplit,parse_qs
from bs4 import BeautifulSoup
import re
class H04Error(ValueError):pass
def parse_public_training(raw,*,observed_url,race_id,runners,captured_utc,cutoff_utc):
    if not isinstance(raw,bytes) or not 0<len(raw)<=1500000:
        raise H04Error("original_bytes_invalid")
    u=urlsplit(observed_url)
    if u.scheme!="https" or u.hostname!="race.netkeiba.com" or u.path!="/race/oikiri.html" or parse_qs(u.query).get("race_id")!=[race_id]:
        raise H04Error("source_url_or_race_id_mismatch")
    def utc(s):
        try:d=datetime.fromisoformat(s.replace("Z","+00:00"))
        except (ValueError,AttributeError) as e:raise H04Error("timestamp_invalid") from e
        if d.tzinfo is None or d.utcoffset().total_seconds()!=0:raise H04Error("timestamp_not_utc")
        return d
    observed_time=utc(captured_utc)
    cutoff=utc(cutoff_utc)
    lookup={x["horse_number"]:x["horse_name"] for x in runners}
    if len(lookup)!=len(runners) or not 2<=len(lookup)<=18:
        raise H04Error("independent_jra_roster_invalid")
    soup=BeautifulSoup(raw,"html.parser")
    title=soup.title.get_text(" ",strip=True) if soup.title else ""
    if "調教タイム" not in title:raise H04Error("wrong_auxiliary_page")
    matched=[];seen=set()
    for tr in soup.select("table.OikiriTable tr.HorseList"):
        number=tr.select_one("td.Umaban")
        horse=tr.select_one("td.Horse_Info")
        date=tr.select_one("td.Training_Day")
        times=tr.select_one("td.TrainingTimeData")
        if not all((number,horse,date,times)):continue
        t=number.get_text(" ",strip=True)
        if not t.isascii() or not t.isdigit():continue
        n=int(t)
        if n not in lookup or lookup[n] not in horse.get_text(" ",strip=True):
            raise H04Error("horse_identity_conflict")
        if n in seen:raise H04Error("duplicate_horse")
        match=re.match(r"20\d{2}/\d{2}/\d{2}",date.get_text(" ",strip=True))
        if match is None:raise H04Error("missing_training_date")
        day=match.group(0).replace("/","-")
        if day>cutoff.date().isoformat():raise H04Error("future_training_day")
        cells=tr.find_all("td",recursive=False)
        if len(cells)<12:raise H04Error("incomplete_training_row")
        samples=re.findall(r"(?<!\d)(\d{2,3}\.\d)\s*\(\d{2}\.\d\)",times.get_text(" ",strip=True))
        if not samples:raise H04Error("no_training_time")
        matched.append({"horse_number":n,"horse_name":lookup[n],"training_date":day,
                        "course":cells[5].get_text(" ",strip=True),
                        "clock_samples":samples,"rating":cells[-1].get_text(" ",strip=True)})
        seen.add(n)
    matched.sort(key=lambda x:x["horse_number"])
    return {"schema":"kyoto_h04_verified_partial_historical_training.v1",
         "source_url":observed_url,"source_sha256":sha256(raw).hexdigest(),
         "source_bytes":len(raw),"capture_utc":captured_utc,"race_id":race_id,
         "roster_count":len(lookup),"matched_training_count":len(matched),
         "unavailable_horse_numbers":sorted(set(lookup)-seen),"training_rows":matched,
         "historical_only":observed_time>=cutoff,
         "pre_race_original_verified":observed_time<cutoff,
         "bulk_automation_permission_verified":False,"prediction_ready":False}
