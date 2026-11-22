"""Evidence-first race/data-family ledger. No network, odds invention or auto release.

Ingest independent encrypted-bundle safe receipts plus frozen G03 real-source
parser results. The records do NOT assert market/profile/result completion.
All changes are reproducible, deterministic and reversible.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

FAMILIES=(
    "racecard_original", "roster", "horse_profile", "past_performances",
    "track_conditions", "quinella_odds", "bracket_quinella_odds",
    "official_result", "official_payout"
)
SHA256=re.compile(r"^[0-9a-f]{64}$")
STATES={"UNOBSERVED","ATTEMPT_FAILED","RAW_SAVED_UNVERIFIED",
        "ORIGINAL_VERIFIED","STRUCTURED_VERIFIED","CONFLICT","NOT_APPLICABLE"}
MISSING={"UNOBSERVED","ATTEMPT_FAILED","RAW_SAVED_UNVERIFIED","CONFLICT"}
SOURCES={"PC","SP"}
DAYS=re.compile(r"^20[0-9]{6}$")

def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def _utc(value):
    if not isinstance(value,str):return False
    try:
        parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset().total_seconds()==0
    except (TypeError,ValueError,AttributeError):return False

def _hash(value):
    return isinstance(value,str) and SHA256.fullmatch(value) is not None

def _empty(day,race,family):
    return {"key":f"KYOTO:{day}:{race:02d}:{family}",
            "day":day,"race":race,"family":family,"state":"UNOBSERVED",
            "source_sha256":None,"source_utc":None,
            "source_channel":None,"observations":[],
            "failure_classes":[],"proof_status":"NOT_PROVEN"}

def _append(record,kind,channel,proof,sha=None,utc=None,error=None):
    # Only whitelisted facts. Free-form raw original, credential or URL is
    # never mirrored into the public-safe ledger.
    obs={"event":kind,"channel":channel,"evidence":proof}
    if _hash(sha):obs["sha256"]=sha
    if _utc(utc):obs["captured_at_utc"]=utc
    if error:obs["error_class"]=re.sub(r"[^A-Za-z0-9_]", "",str(error))[:80]
    record["observations"].append(obs)

def build(source,g03,*,day):
    if not DAYS.fullmatch(day):raise ValueError("invalid_day")
    if source.get("day")!=day or g03.get("day")!=day:
        raise ValueError("day_receipt_mismatch")
    if source.get("schema")!="kyoto_nov22_observed_official_all12.v1":
        raise ValueError("unrecognized_source_receipt_schema")
    if g03.get("schema")!="kyoto_nov22_frozen_g03_on_actual_source.v1":
        raise ValueError("unrecognized_g03_receipt_schema")
    if not isinstance(source.get("races"),dict) or not isinstance(g03.get("races"),dict):
        raise ValueError("race_receipts_missing")
    entries=[]
    for race in range(1,13):
        sn=source["races"].get(str(race))
        gn=g03["races"].get(str(race))
        if not isinstance(sn,dict) or not isinstance(gn,dict):
            raise ValueError("missing_complete_12r_receipts")
        records={f:_empty(day,race,f) for f in FAMILIES}
        original=records["racecard_original"]
        roster=records["roster"]
        valid=[]
        for ch in ("PC","SP"):
            e=sn.get(ch)
            if not isinstance(e,dict):continue
            status=e.get("state")
            if status=="REAL_OFFICIAL_ORIGINAL_SAVED_ROSTER_NOT_AUTHENTICATED":
                sha=e.get("sha256");utc=e.get("captured_at_utc")
                if not _hash(sha) or not _utc(utc):
                    raise ValueError(f"unverified_original_provenance:{race}:{ch}")
                valid.append((ch,sha,utc))
                _append(original,"ORIGINAL_BYTE_RECEIPT",ch,"SOURCE_SHA_UTC_RECORDED",sha,utc)
                if e.get("reused_existing_original") is True:
                    _append(original,"REUSED_ORIGINAL",ch,"NO_NEW_HTTP_ASSERTED")
            elif status=="HTTP_OR_SOURCE_REJECTED":
                name=e.get("error_class","UNKNOWN")
                original["failure_classes"].append(re.sub(r"[^A-Za-z0-9_]", "",str(name))[:80])
                _append(original,"SOURCE_ATTEMPT_FAILED",ch,"SAFE_FAILURE_RECEIPT",error=name)
            elif status=="PC_OFFICIAL_SOURCE_PRESENT_SP_DUPLICATE_NOT_NEEDED":
                _append(original,"DELIBERATE_SKIP",ch,"PC_SOURCE_EXISTED")
            elif status:
                _append(original,"OTHER_SOURCE_STATE",ch,"NOT_CERTIFIED")
        if valid:
            original.update(state="ORIGINAL_VERIFIED",
                            source_channel="PC" if any(x[0]=="PC" for x in valid) else "SP",
                            source_sha256=next(x[1] for x in valid if x[0]==("PC" if any(y[0]=="PC" for y in valid) else "SP")),
                            source_utc=next(x[2] for x in valid if x[0]==("PC" if any(y[0]=="PC" for y in valid) else "SP")),
                            proof_status="SOURCE_RECEIPT_SHA_UTC_ONLY")
        elif original["failure_classes"]:
            original["state"]="ATTEMPT_FAILED"
        if gn.get("state")=="G03_ROSTER_AND_START_PARSED_FROM_ACTUAL_ORIGINAL":
            sha=gn.get("original_sha256");utc=gn.get("captured_at_utc")
            count=gn.get("runner_count");start=gn.get("start_time_jst")
            if not _hash(sha) or not _utc(utc) or type(count)!=int or not 2<=count<=18 or not isinstance(start,str) or not re.fullmatch(r"([01][0-9]|2[0-3]):[0-5][0-9]",start):
                raise ValueError(f"invalid_structured_g03:{race}")
            matching=[x for x in valid if x[0]=="PC" and x[1]==sha and x[2]==utc]
            if matching:
                roster.update(state="STRUCTURED_VERIFIED",source_channel="PC",
                              source_sha256=sha,source_utc=utc,
                              proof_status="G03_PARSER_REPLAY_SAME_ORIGINAL")
                _append(roster,"G03_STRUCTURED_REPLAY","PC",f"RUNNERS_{count}_START_{start}",sha,utc)
                for family,field in (("horse_profile","horse_profiles_observed"),
                                     ("past_performances","past_run_dates_observed")):
                    n=gn.get(field,0)
                    if type(n) is int and n>0:
                        _append(records[family],"NAVIGATION_ONLY","PC",
                                f"OBSERVED_LINK_COUNT_{n}")
                # A profile href or historical date is not a downloaded
                # profile or verified previous performance.
            else:
                roster["state"]="CONFLICT"
                roster["failure_classes"].append("G03_SOURCE_SHA_OR_UTC_MISMATCH")
        elif gn.get("state")=="G03_SOURCE_PARSER_REJECTED":
            if valid:roster["state"]="ATTEMPT_FAILED"
            error=gn.get("error_class","PARSER_REJECTED")
            roster["failure_classes"].append(re.sub(r"[^A-Za-z0-9_]", "",str(error))[:80])
            _append(roster,"PARSER_REJECTED","PC","ACTUAL_ORIGINAL_REPLAY_FAILED",error=error)
        else:
            _append(roster,"NO_G03_CERTIFICATION",None,"NOT_PROVEN")
        # No real profile, history, ground condition, live market odds,
        # official result or payout receipts supplied: remain UNOBSERVED.
        entries.extend(records[f] for f in FAMILIES)
    counts={f:{s:sum(x["state"]==s for x in entries if x["family"]==f)
                 for s in sorted(STATES)}
            for f in FAMILIES}
    missing=[x["key"] for x in entries if x["state"] in MISSING]
    # Stable digest must not depend on clock, file paths or GitHub run event.
    result={"schema":"kyoto_evidence_complete_family_ledger.v1","day":day,
            "source_only":True,"prediction_ready":False,
            "real_wager_authorized":False,"market_prices_verified":False,
            "families":list(FAMILIES),"records":entries,"counts":counts,
            "missing_keys":missing,
            "next_acquisition_priority":[f for f in FAMILIES
               if any(x["family"]==f and x["state"] in MISSING for x in entries)],
            "automated_repair_state":"RECEIPT_GENERATED_NO_CODE_MUTATION",
            "approval_required_for_new_collector":True}
    serialized=json.dumps(result,ensure_ascii=False,sort_keys=True,
                          separators=(",",":")).encode()
    result["content_sha256"]=hashlib.sha256(serialized).hexdigest()
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--g03",required=True)
    p.add_argument("--day",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=build(_json(a.source),_json(a.g03),day=a.day)
    path=Path(a.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n",
                    encoding="utf-8")
    for family in FAMILIES:
        c=result["counts"][family]
        print(f"FAMILY_{family.upper()}=STRUCTURED:{c['STRUCTURED_VERIFIED']} ORIGINAL:{c['ORIGINAL_VERIFIED']} UNOBSERVED:{c['UNOBSERVED']} FAILED:{c['ATTEMPT_FAILED']} CONFLICT:{c['CONFLICT']}")
    print("EVIDENCE_LEDGER_SHA256="+result["content_sha256"])
    print("MARKET_OR_RESULT_SUCCESS_NOT_INFERRED")
if __name__=="__main__":main()
