"""Offline fail-closed prereace market structure checker. No HTTP or purchase actions.

This validates an evidence *claim*, never independently certifies the source
or authorizes freezes, real wagers, F04 acceptance, or production use.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re

class PreraceMarketRejected(ValueError):
    pass

def reject(reason):
    raise PreraceMarketRejected(reason)

def utc(value):
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value):
        reject("UTC_SECOND_REQUIRED")
    try:
        return datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        reject("INVALID_UTC")

def validate(evidence, *, raw_bytes, verified_urls, now_utc):
    required={"race_id","scheduled_start_utc","observed_utc","market_status",
              "ticket_type","source_url","source_sha256","source_phase",
              "active_horses","horse_to_bracket","pairs"}
    if type(evidence) is not dict or set(evidence)!=required:
        reject("INVALID_FIELDS")
    if type(raw_bytes) is not bytes or not 0<len(raw_bytes)<=5_000_000:
        reject("SOURCE_BYTES_REQUIRED")
    digest=evidence["source_sha256"]
    if type(digest) is not str or not re.fullmatch("[0-9a-f]{64}",digest) or sha256(raw_bytes).hexdigest()!=digest:
        reject("SOURCE_SHA256_MISMATCH")
    url=evidence["source_url"]
    if type(verified_urls) is not set or not verified_urls or type(url) is not str or not url.startswith("https://") or url not in verified_urls:
        reject("INDEPENDENT_URL_ALLOWLIST_REQUIRED")
    if type(evidence["race_id"]) is not str or not re.fullmatch("[A-Z0-9][A-Z0-9_-]{5,60}",evidence["race_id"]):
        reject("RACE_ID_INVALID")
    if evidence["source_phase"]!="CAPTURED_BEFORE_START" or evidence["market_status"]!="ON_SALE":
        reject("POSTRACE_OR_STOPPED")
    start,observed,now=(utc(v) for v in (evidence["scheduled_start_utc"],evidence["observed_utc"],now_utc))
    if not (observed<=now<start) or (now-observed).total_seconds()>300:
        reject("FUTURE_LATE_OR_STALE")
    kind=evidence["ticket_type"]
    if kind not in ("QUINELLA","BRACKET_QUINELLA"):
        reject("UNSUPPORTED_MARKET")
    horses=evidence["active_horses"]
    if type(horses) is not list or not 2<=len(horses)<=18 or any(type(h) is not int or not 1<=h<=18 for h in horses) or len(set(horses))!=len(horses):
        reject("INVALID_ACTIVE_HORSES")
    mapping=evidence["horse_to_bracket"]
    if type(mapping) is not dict or set(mapping)!={str(h) for h in horses} or any(type(v) is not int or not 1<=v<=8 for v in mapping.values()):
        reject("INVALID_BRACKETS")
    entries=evidence["pairs"]
    if type(entries) is not list:
        reject("MISSING_PAIRS")
    seen=set()
    for entry in entries:
        if type(entry) is not dict or set(entry)!={"pair","odds"}:
            reject("INVALID_PAIR_ENTRY")
        pair=entry["pair"]
        if type(pair) is not list or len(pair)!=2 or any(type(v) is not int for v in pair):
            reject("INVALID_PAIR")
        a,b=pair
        limit=18 if kind=="QUINELLA" else 8
        if not (1<=a<=b<=limit) or (kind=="QUINELLA" and (a==b or a not in horses or b not in horses)):
            reject("PAIR_NOT_ALLOWED")
        if (a,b) in seen:
            reject("DUPLICATE_PAIR")
        seen.add((a,b))
        odds=entry["odds"]
        if type(odds) is not str or not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?",odds):
            reject("ODDS_EXACT_DECIMAL_REQUIRED")
        try:
            value=Decimal(odds)
        except InvalidOperation:
            reject("ODDS_INVALID")
        if not Decimal("1")<=value<=Decimal("1000000"):
            reject("ODDS_OUT_OF_RANGE")
    if kind=="QUINELLA":
        expected={(a,b) for a in horses for b in horses if a<b}
    else:
        counts={b:list(mapping.values()).count(b) for b in set(mapping.values())}
        # JRA: bracket quinella is normally offered for 9+ sale-start runners.
        # With <=8 it is offered only if a bracket held >=2 at sale start.
        # Current active runners are NOT proof of the sale-start roster.
        # Fail closed on obvious unsupported markets; a historic scratch after
        # 9+ started-sale runners needs independent sale-start evidence later.
        if len(horses)<=8 and not any(n>=2 for n in counts.values()):
            reject("BRACKET_MARKET_NOT_PROVEN_ON_SALE")
        expected={(a,b) for a in counts for b in counts if a<b or (a==b and counts[a]>=2)}
    if seen!=expected:
        reject("INCOMPLETE_OR_EXTRA_MARKET_GRID")
    stable=json.dumps(evidence,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
    return {"status":"OFFLINE_STRUCTURAL_CLAIM_ONLY","race_id":evidence["race_id"],
            "ticket_type":kind,"pair_count":len(seen),
            "snapshot_sha256":sha256(stable.encode()).hexdigest(),
            "live_jra_source_verified":False,"approved_for_paper_freeze":False,
            "approved_for_real_purchase":False}
