"""P1-FB: offline two-channel decision gate, never executes HTTP."""
from dataclasses import dataclass
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json,re

@dataclass(frozen=True)
class ChannelResult:
    channel:str
    verified:bool
    source_sha256:str
    horse:str
    asof_utc:str
    error:str=""
    race:int=0
    number:int=0
    roster_sha:str=""
    normalized_sha256:str=""
    url_verified:bool=False
    raw_saved:bool=False

def validate(item,cutoff):
    if item.channel not in ("PC","SP"):raise ValueError("invalid_channel")
    if not item.horse or not 1<=item.race<=12 or not 1<=item.number<=18:
        raise ValueError("horse_identity_missing")
    if not re.fullmatch("[0-9a-f]{64}",item.roster_sha):raise ValueError("roster_proof_missing")
    if not re.fullmatch("[0-9a-f]{64}",item.source_sha256):raise ValueError("source_proof_missing")
    stamp=datetime.fromisoformat(item.asof_utc.replace("Z","+00:00"))
    if stamp.tzinfo is None or cutoff.tzinfo is None or stamp.astimezone(timezone.utc)>=cutoff.astimezone(timezone.utc):
        raise ValueError("source_after_cutoff")
    if not item.raw_saved:raise ValueError("original_not_preserved")
    if item.verified and (not item.url_verified or not item.raw_saved or
        not re.fullmatch("[0-9a-f]{64}",item.normalized_sha256)):
        raise ValueError("unproven_validation")

def choose(primary,secondary=None,*,cutoff,compare=False):
    validate(primary,cutoff)
    if secondary is not None:
        validate(secondary,cutoff)
        if secondary.channel==primary.channel:raise ValueError("not_cross_channel")
        if (secondary.horse,secondary.race,secondary.number,secondary.roster_sha)!=(
            primary.horse,primary.race,primary.number,primary.roster_sha):
            raise ValueError("horse_identity_conflict")
    if primary.verified and compare and secondary is not None and secondary.verified and (
        primary.normalized_sha256!=secondary.normalized_sha256):
        return None,"SOURCE_CONFLICT"
    if primary.verified:return primary.channel,"PRIMARY_VALID"
    if secondary is None:return None,"PRIMARY_FAILED"
    if secondary.verified:return secondary.channel,"FALLBACK_VALID_PRIMARY_STILL_BROKEN"
    return None,"BOTH_FAILED"

def write_case(directory,primary,secondary,*,cutoff,compare=False):
    """Immutable decision receipt. Failed channel remains an independent incident."""
    from dataclasses import asdict
    from pathlib import Path
    import json
    target=Path(directory)
    if target.exists() and any(target.iterdir()):
        raise ValueError("incident_receipt_already_exists")
    channel,decision=choose(primary,secondary,cutoff=cutoff,compare=compare)
    target.mkdir(parents=True,exist_ok=True)
    records=[]
    for item in (primary,secondary):
        if item is None:continue
        records.append({"channel":item.channel,"verified":item.verified,
            "error":item.error,"horse":item.horse,"race":item.race,
            "number":item.number,"source_sha256":item.source_sha256,
            "asof_utc":item.asof_utc,
            "incident_open":not item.verified})
    receipt={"schema":"p1_fb_offline_incident.v1",
        "decision":decision,"selected_channel":channel,
        "separate_incidents":records,"network_requests":0,
        "automatic_live_fallback":False,
        "training_ready":False,"prediction_ready":False}
    (target/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    return receipt


def reconcile_complementary_fields(pc, sp, *, cutoff, required_fields=()):
    """Reconcile already-validated independent source fields, never HTTP.

    Each source: {"channel_result": ChannelResult, "fields": mapping,
    "fields_sha256": sha256(canonical JSON fields)}. A missing field can be
    completed from the other validated channel; incompatible non-null values
    are quarantined, not silently selected. Prices and volatile market values
    are deliberately forbidden here (they require same-time market evidence).
    Source validation is inherited from P1-FB and does NOT independently
    prove the raw HTML was ever downloaded.
    """
    import hashlib
    def validated(p, channel):
        if not isinstance(p,dict) or not isinstance(p.get("channel_result"),ChannelResult):
            raise ValueError("source_evidence_required")
        info=p["channel_result"]
        validate(info,cutoff)
        if info.channel!=channel or not info.verified:
            raise ValueError("independent_verified_channel_required")
        fields=p.get("fields")
        if not isinstance(fields,dict) or any(not isinstance(k,str) or not k for k in fields):
            raise ValueError("invalid_field_dictionary")
        raw=json.dumps(fields,sort_keys=True,separators=(",",":"),ensure_ascii=False,
                       allow_nan=False).encode("utf8")
        if hashlib.sha256(raw).hexdigest()!=p.get("fields_sha256"):
            raise ValueError("field_original_sha_mismatch")
        return info,fields
    p, pf=validated(pc,"PC")
    q, sf=validated(sp,"SP")
    if (p.horse,p.race,p.number,p.roster_sha)!=(q.horse,q.race,q.number,q.roster_sha):
        raise ValueError("pc_sp_horse_identity_conflict")
    if not isinstance(required_fields,(list,tuple,set,frozenset)) or any(
            not isinstance(x,str) for x in required_fields):
        raise ValueError("required_fields_invalid")
    prohibited={"odds","price","market_odds","quinella_odds","bracket_quinella_odds",
                "odds_pairs","payout","result","finish_position_today"}
    all_fields=set(pf)|set(sf)|set(required_fields)
    if prohibited & all_fields:
        raise ValueError("volatile_or_postrace_fields_must_not_be_merged")
    merged={}; provenance={}; conflicts={}
    for field in sorted(all_fields):
        left,right=pf.get(field),sf.get(field)
        if left is not None and right is not None and left!=right:
            conflicts[field]={"PC":left,"SP":right}
            continue
        value=left if left is not None else right
        if value is None:continue
        merged[field]=value
        provenance[field]=[{"channel":info.channel,"original_sha256":info.source_sha256,
                             "captured_at_utc":info.asof_utc,
                             "field_set_sha256":piece["fields_sha256"]}
            for info,piece,v in ((p,pc,left),(q,sp,right)) if v is not None]
    missing=sorted(set(required_fields)-set(merged))
    if conflicts:
        return {"state":"CONFLICT_QUARANTINED","merged":{},
                "provenance":{},"conflicts":conflicts,
                "missing_required":missing,"prediction_ready":False}
    return {"state":"COMPLETE" if not missing else "INCOMPLETE",
            "merged":merged,"provenance":provenance,"conflicts":{},
            "missing_required":missing,"prediction_ready":False}
