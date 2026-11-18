"""Classify official SP racecard lifecycle using original HTML, not HTTP 200."""
from hashlib import sha256
from bs4 import BeautifulSoup
from diagnostics.jra_pc_sp_benchmark import sp_rows
import re

class SPPageError(ValueError): pass
def classify(raw, *, race_day, race_number):
    if not isinstance(raw,bytes) or not 0<len(raw)<=1_000_000:
        raise SPPageError("original_missing_or_size_invalid")
    if not (isinstance(race_day,str) and re.fullmatch(r"20\d{6}",race_day)
            and type(race_number) is int and 1<=race_number<=12):
        raise SPPageError("expected_race_identity_invalid")
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    text=soup.get_text(" ",strip=True)
    y,m,d=int(race_day[:4]),int(race_day[4:6]),int(race_day[6:])
    if not re.search(fr"{y}年\s*{m}月\s*{d}日",text):
        raise SPPageError("race_date_absent")
    if not re.search(fr"(?<!\d){race_number}\s*R\b",text):
        raise SPPageError("race_number_absent")
    base={"source_sha256":sha256(raw).hexdigest(),"source_bytes":len(raw),
          "race_day":race_day,"race_number":race_number,
          "racecard_usable":False,"prediction_ready":False}
    if "このレースの出馬表の掲載は終了しております" in text:
        return {**base,"state":"EXPIRED_RACECARD_OFFICIAL_PAGE",
                "recovery":"USE_SAVED_PRE_EXPIRY_ORIGINAL_OR_NEW_LIVE_SP_NAVIGATION"}
    try:
        rows=sp_rows(raw)
    except ValueError as exc:
        return {**base,"state":"NO_VERIFIED_SP_ROSTER","reason":str(exc)}
    return {**base,"state":"SP_ROSTER_PARSED_IDENTITY_PENDING",
            "horse_count":len(rows),"horse_numbers":[x[0] for x in rows]}
