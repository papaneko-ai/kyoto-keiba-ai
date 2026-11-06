"""Fail-closed official JRA live odds integrity gate; no network or DB writes."""
from dataclasses import dataclass
from datetime import datetime,timezone,date,time,timedelta
from decimal import Decimal,InvalidOperation
from hashlib import sha256
from itertools import combinations
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

class OddsGateError(ValueError):
    pass

def utc(s):
    if not isinstance(s,str):raise OddsGateError("missing_timestamp")
    try:v=datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError as e:raise OddsGateError("invalid_timestamp") from e
    if v.tzinfo is None or v.utcoffset() is None:raise OddsGateError("naive_timestamp")
    return v.astimezone(timezone.utc)

def normal_sales_open(day):
    if not isinstance(day,date) or isinstance(day,datetime):raise OddsGateError("bad_race_day")
    if day.weekday()==5:hour,minute=18,30
    elif day.weekday() in (6,0):hour,minute=19,30
    else:return None
    return datetime.combine(day-timedelta(days=1),time(hour,minute),ZoneInfo("Asia/Tokyo")).astimezone(timezone.utc)

def publication_status(*,race_day,checked_at_utc,visible_text,title,official_verified,exception=False):
    checked=utc(checked_at_utc)
    if not official_verified:return {"state":"INVALID_SOURCE","usable":False}
    if "最終オッズ" in title or "最終オッズ" in visible_text:
        return {"state":"FINAL_NOT_PRERACE","usable":False}
    if "今週のオッズは未発表です" in visible_text or "オッズは未発表" in visible_text:
        return {"state":"NOT_PUBLISHED","usable":False}
    opening=normal_sales_open(race_day)
    if opening is None or exception:return {"state":"EXCEPTION_REVIEW","usable":False}
    if checked<opening:return {"state":"BEFORE_NORMAL_SALES","usable":False}
    return {"state":"NEEDS_MARKET_HTML_VALIDATION","usable":False}

@dataclass(frozen=True)
class MarketEvidence:
    race_key:str
    market:str
    phase:str
    source_url:str
    captured_at_utc:str
    source_sha256:str
    source_bytes:int
    runners:tuple
    quotes:tuple
    official_verified:bool
    race_identity_verified:bool

def check(e,*,race_start_utc,source_bytes=None):
    """Never accepts a claimed 'live' label without independent source bytes.

    runners: tuple[(horse number, frame number)]
    quotes: tuple[(number1, number2, decimal odds)]
    """
    def block(reason):return {"state":"BLOCKED","reason":reason,"usable":False,
                               "prediction_ready":False,"training_ready":False}
    if e.market not in ("quinella","bracket_quinella"):return block("invalid_market")
    if e.phase!="LIVE_PRE_RACE":return block("historical_or_unpublished_phase")
    if not e.official_verified or not e.race_identity_verified or not e.race_key:
        return block("unverified_race_or_origin")
    u=urlsplit(e.source_url)
    if u.scheme!="https" or u.hostname not in ("jra.jp","www.jra.go.jp","sp.jra.jp") or u.path!="/JRADB/accessO.html":
        return block("source_not_official_odds_page")
    try:
        if utc(e.captured_at_utc)>=utc(race_start_utc):return block("after_start")
    except OddsGateError:return block("invalid_timestamp")
    if source_bytes is None:return block("original_bytes_missing")
    if len(source_bytes)!=e.source_bytes or sha256(source_bytes).hexdigest()!=e.source_sha256:
        return block("original_hash_mismatch")
    txt=source_bytes.decode("cp932",errors="replace")
    if "最終オッズ" in txt or "今週のオッズは未発表です" in txt:
        return block("final_or_unpublished_original")
    runners=e.runners
    if not runners or len({x[0] for x in runners})!=len(runners):
        return block("bad_runner_roster")
    if any(len(x)!=2 or type(x[0]) is not int or type(x[1]) is not int
           or not 1<=x[0]<=18 or not 1<=x[1]<=8 for x in runners):
        return block("bad_runner_number_or_frame")
    if e.market=="quinella":
        expected=set(combinations(sorted(x[0] for x in runners),2))
    else:
        frames=[x[1] for x in runners]
        expected=set(combinations(sorted(set(frames)),2)) | {(f,f) for f in set(frames) if frames.count(f)>=2}
    observed={}
    for v in e.quotes:
        if len(v)!=3:return block("bad_quote")
        a,b,value=v
        if type(a) is not int or type(b) is not int or a>b or (a,b) in observed or (a,b) not in expected:
            return block("duplicate_or_ineligible_pair")
        try:odds=Decimal(str(value))
        except (InvalidOperation,ValueError):return block("unpriced_or_invalid_quote")
        if not odds.is_finite() or odds<1:return block("invalid_decimal_odds")
        observed[(a,b)]=odds
    if set(observed)!=expected:return block("incomplete_pair_matrix")
    return {"state":"VALIDATED_MARKET_SOURCE","reason":"source_bytes_and_pairs_verified",
            "usable":True,"verified_pairs":len(expected),
            "prediction_ready":False,"training_ready":False}
