"""P6 FIXTURE-ONLY virtual prediction freeze and settlement replay.

Never accesses live JRA, external data, actual purchases or production ledger.
Preliminary result is not settled. Final correction replaces, never adds, P&L.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
import math

class LabRejected(ValueError):
    pass

def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",",":"), allow_nan=False).encode("utf-8")

def _utc(s):
    if not isinstance(s,str):
        raise LabRejected("utc_timestamp_required")
    try:
        t=datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError as exc:
        raise LabRejected("timestamp_invalid") from exc
    if t.tzinfo is None or t.utcoffset() != timezone.utc.utcoffset(None):
        raise LabRejected("timestamp_not_utc")
    return t

def _pair(raw, ticket_type):
    if not isinstance(raw,(list,tuple)) or len(raw)!=2:
        raise LabRejected("pair_invalid")
    a,b=raw
    end=18 if ticket_type=="QUINELLA" else 8
    if type(a) is not int or type(b) is not int or not 1<=a<=end or not 1<=b<=end:
        raise LabRejected("pair_invalid")
    if a==b and ticket_type=="QUINELLA":
        raise LabRejected("same_horse_quinella")
    return tuple(sorted((a,b)))

def freeze_fixture(*, scenario_id, ticket_type, cutoff_utc, frozen_utc,
                   model_version, source_sha256, tickets):
    if not isinstance(scenario_id,str) or not scenario_id.startswith("LAB-"):
        raise LabRejected("lab_marker_required")
    if ticket_type not in ("QUINELLA","BRACKET"):
        raise LabRejected("ticket_type_invalid")
    if _utc(frozen_utc) >= _utc(cutoff_utc):
        raise LabRejected("freeze_after_cutoff")
    if not isinstance(model_version,str) or not model_version:
        raise LabRejected("model_version_required")
    if not isinstance(source_sha256,str) or len(source_sha256)!=64 or any(c not in "0123456789abcdef" for c in source_sha256):
        raise LabRejected("source_sha_invalid")
    if not isinstance(tickets,list) or not 1<=len(tickets)<=3:
        raise LabRejected("ticket_count_invalid")
    saved=[]
    seen=set()
    for item in tickets:
        if not isinstance(item,dict):
            raise LabRejected("ticket_invalid")
        pair=_pair(item.get("pair"),ticket_type)
        if pair in seen:
            raise LabRejected("ticket_duplicate")
        seen.add(pair)
        stake=item.get("stake_yen")
        probability=item.get("probability")
        odds=item.get("odds")
        if type(stake) is not int or not 100<=stake<=1_000_000 or stake%100:
            raise LabRejected("stake_invalid")
        if type(probability) not in (float,int) or not math.isfinite(probability) or not 0<=probability<=1:
            raise LabRejected("probability_invalid")
        if type(odds) not in (float,int) or not math.isfinite(odds) or not 1<odds<100000:
            raise LabRejected("odds_invalid")
        saved.append({"pair":list(pair),"stake_yen":stake,"probability":float(probability),"odds":float(odds)})
    body={"schema":"kyoto_p6_fixture_frozen_prediction.v1","scenario_id":scenario_id,
          "ticket_type":ticket_type,"frozen_utc":frozen_utc,"cutoff_utc":cutoff_utc,
          "model_version":model_version,"source_sha256":source_sha256,
          "ledger_type":"VIRTUAL_FIXTURE_ONLY","tickets":saved,
          "not_real_prediction":True,"not_actual_purchase":True}
    return {"frozen":body,"frozen_sha256":sha256(_canonical(body)).hexdigest()}

def _validate_frozen(frozen):
    if not isinstance(frozen,dict) or not isinstance(frozen.get("frozen"),dict):
        raise LabRejected("frozen_missing")
    body=frozen["frozen"]
    if body.get("schema")!="kyoto_p6_fixture_frozen_prediction.v1" or body.get("ledger_type")!="VIRTUAL_FIXTURE_ONLY" or body.get("not_real_prediction") is not True:
        raise LabRejected("not_fixture_prediction")
    try:
        valid=sha256(_canonical(body)).hexdigest()==frozen.get("frozen_sha256")
    except (TypeError,ValueError) as exc:
        raise LabRejected("freeze_tampered") from exc
    if not valid:
        raise LabRejected("freeze_tampered")
    return body

def settle_fixture(frozen, events):
    """Idempotent replay: final version replaces earlier events, no double count."""
    body=_validate_frozen(frozen)
    if not isinstance(events,list):
        raise LabRejected("event_stream_invalid")
    by_version={}
    for event in events:
        if not isinstance(event,dict) or event.get("source_kind")!="FIXTURE" or event.get("scenario_id")!=body["scenario_id"]:
            raise LabRejected("nonfixture_event")
        version=event.get("version")
        if type(version) is not int or version<=0:
            raise LabRejected("event_version_invalid")
        if event.get("state") not in ("RESULT_PRELIMINARY","PAYOUT_FINAL"):
            raise LabRejected("event_state_invalid")
        digest=sha256(_canonical(event)).hexdigest()
        if version in by_version and by_version[version][0]!=digest:
            raise LabRejected("version_payload_conflict")
        by_version[version]=(digest,event)
    stake=sum(t["stake_yen"] for t in body["tickets"])
    if not by_version:
        return {"status":"UNSETTLED","stake_yen":stake,"payout_yen":None,"profit_yen":None,
                "ticket_hits":None,"official_confirmation":False,"fixture_only":True}
    versions=sorted(by_version)
    final_seen=False
    for v in versions:
        state=by_version[v][1]["state"]
        if final_seen and state=="RESULT_PRELIMINARY":
            raise LabRejected("final_to_preliminary_regression")
        if state=="PAYOUT_FINAL":
            final_seen=True
    version=versions[-1]
    event=by_version[version][1]
    if event["state"]=="RESULT_PRELIMINARY":
        return {"status":"PRELIMINARY_UNSETTLED","stake_yen":stake,"payout_yen":None,
                "profit_yen":None,"ticket_hits":None,
                "event_version":version,"official_confirmation":False,"fixture_only":True}
    payout_table=event.get("payout_per_100")
    refunds=event.get("refunded_pairs",[])
    if not isinstance(payout_table,dict) or not isinstance(refunds,list):
        raise LabRejected("final_market_data_invalid")
    paid={}
    for label,amount in payout_table.items():
        if not isinstance(label,str):
            raise LabRejected("payout_pair_invalid")
        parts=label.split("-")
        if len(parts)!=2 or any(not n.isdigit() for n in parts):
            raise LabRejected("payout_pair_invalid")
        pair=_pair(tuple(int(n) for n in parts),body["ticket_type"])
        if "-".join(map(str,pair))!=label:
            raise LabRejected("noncanonical_payout_pair")
        if type(amount) is not int or amount<0:
            raise LabRejected("payout_invalid")
        paid[pair]=amount
    refunded=set()
    for raw in refunds:
        pair=_pair(raw,body["ticket_type"])
        if pair in refunded or pair in paid:
            raise LabRejected("refund_conflict")
        refunded.add(pair)
    total=0;hits=0;refunded_stake=0
    for ticket in body["tickets"]:
        pair=tuple(ticket["pair"]);ticket_stake=ticket["stake_yen"]
        if pair in refunded:
            total+=ticket_stake
            refunded_stake+=ticket_stake
        elif pair in paid:
            total+=(ticket_stake//100)*paid[pair]
            hits+=1
    return {"status":"FINAL_FIXTURE_ONLY","stake_yen":stake,"payout_yen":total,
            "profit_yen":total-stake,"ticket_hits":hits,
            "refunded_stake_yen":refunded_stake,
            "event_version":version,"official_confirmation":False,"fixture_only":True}
