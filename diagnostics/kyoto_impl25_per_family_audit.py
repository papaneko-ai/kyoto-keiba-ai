"""Read-only G03-G06 family audit of already decrypted, ephemeral originals.

Never opens the network, touches Turso, changes original bytes or authenticates
JRA merely from receipt presence. All date, hash, cutoff and race/horse
identities are fail-closed. Do not publish original URLs or horse names.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

FAMILIES=("G03","G04","G05","G06")
DAYS=("20261121","20261122")

def _load(path):
    if path.is_symlink() or not path.is_file():
        return None
    try:
        value=json.loads(path.read_text(encoding="utf8"))
        return value if isinstance(value,dict) else None
    except (ValueError,OSError,UnicodeError):
        return None

def _time(value):
    if not isinstance(value,str):
        return None
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
        return dt if dt.tzinfo is not None and dt.utcoffset()==timezone.utc.utcoffset(None) else None
    except ValueError:
        return None

def _bound(root,name,sha,stamp,cutoff):
    if not isinstance(name,str) or "/" in name or "\\" in name or name in ("",".",".."):
        return False
    p=root/name
    if p.is_symlink() or not p.is_file():
        return False
    acquired,end=_time(stamp),_time(cutoff)
    if acquired is None or end is None or acquired>=end:
        return False
    return isinstance(sha,str) and hashlib.sha256(p.read_bytes()).hexdigest()==sha

def audit(root,day):
    if day not in DAYS:
        raise ValueError("day_out_of_scope")
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe_decrypted_source")
    result={"schema":"kyoto_impl25_per_family_source_audit.v1","day":day,
       "source_is_decrypted_ephemeral":True,"jra_origin_proven_by_this_report":False,
       "prediction_ready":False,"per_race":{},"totals":{},
       "uncertainties":["SP_FULL_12_RACES_NOT_ESTABLISHED",
                        "INDEPENDENT_WORKOUT_SOURCE_NOT_ESTABLISHED"]}
    g03=_load(root/"g03_receipt.json")
    g04=_load(root/"g04_receipt.json")
    g05=_load(root/"g05_receipt.json")
    if g03 and (g03.get("day")!=day or g03.get("schema")!="kyoto_g03_all_races.v1"):
        g03=None
    if g04 and (g04.get("day")!=day or g04.get("schema")!="kyoto_g04_all_horses.v1"):
        g04=None
    if g05 and (g05.get("day")!=day or g05.get("schema")!="kyoto_g05_source_evidence.v1"):
        g05=None
    # Reuse the independently tested partial G03 verification; never weaken it.
    verified=set()
    if g03:
        try:
            from diagnostics.kyoto_g03_independent_partial import verify_partial
            verified=set(verify_partial(root,expected_day=day)["verified_race_numbers"])
        except (ValueError,OSError,KeyError,TypeError):
            verified=set()
    profiles=g04.get("profiles",[]) if g04 else []
    by_race={}
    if isinstance(profiles,list):
        for item in profiles:
            if isinstance(item,dict) and type(item.get("race")) is int:
                by_race.setdefault(item["race"],[]).append(item)
    else:
        by_race={}
    # G06 is nested in the already AES-GCM authenticated parent. The
    # existing tar path allowlist, per-file SHA, bounded-size proof is reused.
    markets={}
    bundle=root/"g06_source_bundle.tar.gz"
    if bundle.is_file() and not bundle.is_symlink():
        try:
            from diagnostics.kyoto_g06_nested_bundle import verify_bundle
            verify_bundle(bundle)
            import tarfile
            with tarfile.open(bundle,"r:gz") as tar:
                item=tar.extractfile("g06_batch_receipt.json")
                batch=json.loads(item.read(1_500_001)) if item else {}
                for entry in batch.get("records",[]):
                    if isinstance(entry,dict) and type(entry.get("race")) is int:
                        markets[entry["race"]]=entry
        except (ValueError,OSError,KeyError,TypeError,tarfile.TarError):
            markets={}
    for race in range(1,13):
        entry=g03.get("races",{}).get(str(race),{}) if g03 else {}
        if not isinstance(entry,dict): entry={}
        roster=entry.get("runners",[]) if race in verified else []
        horses={h["number"]:h["name"] for h in roster
                if isinstance(h,dict) and type(h.get("number")) is int
                and isinstance(h.get("name"),str)}
        race_proof=race in verified
        counts={"G03":{"state":"VERIFIED_PRESTART_ORIGINAL" if race_proof else "MISSING_OR_UNVERIFIED",
                       "verified_horses":len(horses),"expected_horses":len(horses) if race_proof else None},
                "G04":{"state":"MISSING_OR_UNVERIFIED","verified_horses":0,
                       "expected_horses":len(horses) if race_proof else None},
                "G05":{"state":"MISSING_OR_UNVERIFIED","observed_fields":0,
                       "missing_fields":0},
                "G06":{"state":"MISSING_OR_UNVERIFIED",
                       "paired_market_receipt_claim":False}}
        if race_proof and g04:
            found=set()
            for p in by_race.get(race,[]):
                no=p.get("horse_number")
                if type(no) is not int or no not in horses or p.get("horse_name")!=horses[no] or no in found:
                    continue
                found.add(no)
                if (p.get("profile_verified") is True and
                    _bound(root,p.get("raw_original_file"),p.get("source_sha256"),
                           p.get("captured_at_utc"),p.get("race_cutoff_utc"))):
                    counts["G04"]["verified_horses"]+=1
            counts["G04"]["state"]=(
                "ALL_HORSES_SHA_UTC_PRESTART_VERIFIED" if len(horses)>0 and
                counts["G04"]["verified_horses"]==len(horses)
                else "PARTIAL_OR_UNVERIFIED_PROFILE_ORIGINALS")
        if race_proof and g05:
            part=g05.get("races",{}).get(str(race),{})
            if isinstance(part,dict):
                original=f"g03_official_racecard_{race:02d}.html"
                start=part.get("start_utc")
                if (part.get("original_sha256")==entry.get("original_sha256")
                    and _bound(root,original,part.get("original_sha256"),
                               entry.get("captured_at_utc"),start)):
                    field_evidence=list(part.get("track",{}).values())
                    for no in horses:
                        fields=part.get("horses",{}).get(str(no),{})
                        if isinstance(fields,dict):
                            field_evidence.extend(fields.get(k,{}) for k in
                                ("body_weight_kg","body_weight_change_kg","workout"))
                    for field in field_evidence:
                        if not isinstance(field,dict): continue
                        if (field.get("source_sha256")!=entry.get("original_sha256")
                            or field.get("source_original")!=original
                            or field.get("captured_at_utc")!=entry.get("captured_at_utc")):
                            counts["G05"]["state"]="EVIDENCE_MISMATCH"
                            counts["G05"]["observed_fields"]=0
                            counts["G05"]["missing_fields"]=0
                            break
                        if field.get("state")=="OBSERVED" and field.get("value") is not None:
                            counts["G05"]["observed_fields"]+=1
                        else:
                            counts["G05"]["missing_fields"]+=1
                    else:
                        counts["G05"]["state"]="BOUND_FIELDS_PARTIAL_OR_COMPLETE"
        market=markets.get(race)
        if isinstance(market,dict):
            counts["G06"]["paired_market_receipt_claim"]=market.get("both_markets_verified") is True
            counts["G06"]["state"]="BUNDLE_HASH_VALID_RECEIPT_CLAIM_NOT_INDEPENDENTLY_REPLAYED"
        result["per_race"][str(race)]=counts
    result["totals"]={
        "G03_races_verified":len(verified),
        "G03_horses_verified":sum(d["G03"]["verified_horses"] for d in result["per_race"].values()),
        "G04_profiles_sha_utc_verified":sum(d["G04"]["verified_horses"] for d in result["per_race"].values()),
        "G05_observed_fields_bound":sum(d["G05"]["observed_fields"] for d in result["per_race"].values()),
        "G05_missing_fields_declared":sum(d["G05"]["missing_fields"] for d in result["per_race"].values()),
        "G06_paired_market_receipt_claims":sum(d["G06"]["paired_market_receipt_claim"] for d in result["per_race"].values())}
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--day",choices=DAYS,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    result=audit(args.root,args.day)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
    print("PER_FAMILY_SOURCE_AUDIT_COMPLETED_NOT_ORIGIN_AUTHENTICATION")

if __name__=="__main__":
    main()
