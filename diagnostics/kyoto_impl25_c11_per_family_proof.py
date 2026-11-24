"""C11: read-only race/horse/market evidence receipt built from saved original bytes.

The report proves LOCAL consistency of bytes/SHA/UTC/cutoff and shows
missingness. It does not authenticate JRA identity, grant prediction, or
turn an encrypted artifact into data-acquisition success.
"""
from __future__ import annotations
import hashlib, io, json, re, tarfile, tempfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
from diagnostics.kyoto_g03_independent_partial import verify_partial
from diagnostics.kyoto_g06_nested_bundle import verify_bundle
from diagnostics.kyoto_g06_all12_capture import _verify_saved_channel

DAYS=("20261121","20261122","20261128","20261129")
JST=timezone(timedelta(hours=9))
DATA_FIELDS=("weather","turf_going","dirt_going","body_weight_kg",
             "body_weight_change_kg","workout")
MARKETS=("quinella","bracket_quinella")

def utc(value):
    if not isinstance(value,str):
        return None
    try:
        stamp=datetime.fromisoformat(value.replace("Z","+00:00"))
        return stamp if stamp.tzinfo is not None and stamp.utcoffset()==timedelta(0) else None
    except (ValueError,OverflowError):
        return None

def _receipt(root,name,day,schema):
    p=root/name
    if p.is_symlink() or not p.is_file():
        return None
    try:
        data=json.loads(p.read_text(encoding="utf8"))
        return data if isinstance(data,dict) and data.get("day")==day and data.get("schema")==schema else None
    except (OSError,ValueError,UnicodeError):
        return None

def _original(root,name,sha,stamp,cutoff):
    if not isinstance(name,str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,125}",name):
        return False
    p=root/name
    captured,end=utc(stamp),utc(cutoff)
    if not captured or not end or captured>=end or p.is_symlink() or not p.is_file():
        return False
    if not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{64}",sha):
        return False
    return hashlib.sha256(p.read_bytes()).hexdigest()==sha

def _cutoff(day,start):
    if not isinstance(start,str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]",start):
        return None
    return datetime.fromisoformat(f"{day[:4]}-{day[4:6]}-{day[6:8]}T{start}:00").replace(
        tzinfo=JST).astimezone(timezone.utc).isoformat()

def _g06_local_market_evidence(root,day,start_by_race):
    """Use existing independent channel validator on verified nested bundle.

    The nested bundle manifest authenticates its own local bytes, not the
    JRA origin. Extract only bounded allowlisted market channel files into
    a temporary location, never directly onto a user path.
    """
    result={str(r):{"state":"NO_VERIFIED_G06_BUNDLE","markets":{
        m:{"state":"MISSING_OR_UNVERIFIED","sha256":None,"captured_at_utc":None}
        for m in MARKETS}} for r in range(1,13)}
    path=root/"g06_source_bundle.tar.gz"
    if path.is_symlink() or not path.is_file():
        return result
    try:
        verify_bundle(path)
        with tempfile.TemporaryDirectory(prefix="kyoto_c11_g06_") as temp:
            work=Path(temp)
            with tarfile.open(path,"r:gz") as archive:
                members=archive.getmembers()
                # verify_bundle is the mandatory content/manifest preflight.
                for member in members:
                    match=re.fullmatch(r"r(0[1-9]|1[0-2])/(pc|sp)/(receipt\.json|official_odds_menu\.html|quinella_original\.html|bracket_quinella_original\.html)",member.name)
                    if match:
                        dest=work/member.name
                        dest.parent.mkdir(parents=True,exist_ok=True)
                        dest.write_bytes(archive.extractfile(member).read(1_500_001))
            for race in range(1,13):
                cutoff=start_by_race.get(race)
                if not cutoff:
                    result[str(race)]["state"]="NO_G03_START_TIME_FOR_G06_PROOF"
                    continue
                for channel in ("pc","sp"):
                    folder=work/f"r{race:02d}"/channel
                    if not folder.is_dir():
                        continue
                    check=_verify_saved_channel(folder,verified_start_utc=cutoff)
                    if check.get("state")=="BOTH_MARKET_ORIGINALS_VERIFIED":
                        result[str(race)]={"state":"BOTH_MARKETS_SHA_UTC_PRESTART_VERIFIED_LOCALLY",
                            "channel":channel,"markets":{
                            m:{"state":"SHA_UTC_PRESTART_MATCH","sha256":check["market_shas"][m],
                               "captured_at_utc":check["capture_times_utc"][m]}
                            for m in MARKETS}}
                        break
                else:
                    result[str(race)]["state"]="BUNDLED_BUT_MARKET_RECEIPT_NOT_INDEPENDENTLY_VALIDATED"
    except (OSError,ValueError,KeyError,TypeError,tarfile.TarError):
        for r in result.values():
            r["state"]="INVALID_G06_BUNDLE_OR_RECEIPT"
    return result

def assess(root,day):
    if day not in DAYS:
        raise ValueError("invalid_day")
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe_source_root")
    g03=_receipt(root,"g03_receipt.json",day,"kyoto_g03_all_races.v1")
    g04=_receipt(root,"g04_receipt.json",day,"kyoto_g04_all_horses.v1")
    g05=_receipt(root,"g05_receipt.json",day,"kyoto_g05_source_evidence.v1")
    aux=_receipt(root,"c10_auxiliary_coverage_receipt.json",day,"kyoto_impl25_auxiliary_source_coverage.v1")
    verified=set()
    try:
        verified=set(verify_partial(root,expected_day=day)["verified_race_numbers"])
    except (ValueError,KeyError,TypeError,OSError):
        pass
    profiles={}
    if g04 and isinstance(g04.get("profiles"),list):
        for p in g04["profiles"]:
            if isinstance(p,dict) and type(p.get("race")) is int and type(p.get("horse_number")) is int:
                profiles[(p["race"],p["horse_number"])]=p
    output={}
    start_by_race={}
    for race in range(1,13):
        original=(g03 or {}).get("races",{}).get(str(race),{})
        original=original if isinstance(original,dict) else {}
        cutoff=_cutoff(day,original.get("start_time_jst"))
        if cutoff and race in verified:
            start_by_race[race]=cutoff
        roster=original.get("runners",[]) if race in verified else []
        roster=roster if isinstance(roster,list) else []
        horses={}
        g05race=(g05 or {}).get("races",{}).get(str(race),{})
        g05race=g05race if isinstance(g05race,dict) else {}
        race_sha=g05race.get("original_sha256")
        conditions_original_ok=(race in verified and race_sha==original.get("original_sha256") and
            bool(cutoff) and _original(root,f"g03_official_racecard_{race:02d}.html",
              race_sha,original.get("captured_at_utc"),cutoff))
        for horse in roster:
            if not isinstance(horse,dict) or type(horse.get("number")) is not int:
                continue
            number=horse["number"]
            profile=profiles.get((race,number),{})
            filename=f"g04_profile_r{race:02d}_h{number:02d}.html"
            good=(profile.get("profile_verified") is True and
                profile.get("horse_name")==horse.get("name") and
                profile.get("raw_original_file")==filename and
                bool(cutoff) and profile.get("race_cutoff_utc")==cutoff and
                _original(root,filename,profile.get("source_sha256"),
                    profile.get("captured_at_utc"),cutoff))
            fields={}
            raw_fields=g05race.get("horses",{}).get(str(number),{}) if conditions_original_ok else {}
            if not isinstance(raw_fields,dict):
                raw_fields={}
            for key in ("body_weight_kg","body_weight_change_kg","workout"):
                source=raw_fields.get(key,{})
                source=source if isinstance(source,dict) else {}
                valid=(conditions_original_ok and key!="workout" and
                    source.get("state")=="OBSERVED" and source.get("value") is not None and
                    source.get("source_sha256")==race_sha and
                    source.get("source_original")==f"g03_official_racecard_{race:02d}.html" and
                    utc(source.get("captured_at_utc")) is not None and
                    utc(source.get("captured_at_utc"))==utc(original.get("captured_at_utc")))
                fields[key]={"state":"SHA_UTC_BOUND" if valid else "MISSING_OR_UNVERIFIED",
                             "value":source.get("value") if valid else None,
                             "missing_reason":None if valid else (
                                "SOURCE_NOT_INDEPENDENTLY_OBSERVED" if key=="workout" else
                                source.get("missing_reason") or "SOURCE_OR_FIELD_NOT_VERIFIED")}
            horses[str(number)]={"profile_state":"SHA_UTC_PRESTART_MATCH" if good else "MISSING_OR_UNVERIFIED",
                                 "profile_sha256":profile.get("source_sha256") if good else None,
                                 "profile_captured_at_utc":profile.get("captured_at_utc") if good else None,
                                 "fields":fields}
        track={}
        for key in ("weather","turf_going","dirt_going"):
            source=g05race.get("track",{}).get(key,{}) if conditions_original_ok else {}
            source=source if isinstance(source,dict) else {}
            good=(conditions_original_ok and source.get("state")=="OBSERVED" and
                  source.get("value") is not None and
                  source.get("source_sha256")==race_sha and
                  source.get("source_original")==f"g03_official_racecard_{race:02d}.html" and
                  utc(source.get("captured_at_utc")) is not None and
                    utc(source.get("captured_at_utc"))==utc(original.get("captured_at_utc")))
            track[key]={"state":"SHA_UTC_BOUND" if good else "MISSING_OR_UNVERIFIED",
                        "value":source.get("value") if good else None}
        output[str(race)]={"g03":{"state":"SHA_UTC_PRESTART_VERIFIED" if race in verified else "MISSING_OR_UNVERIFIED",
                                 "sha256":original.get("original_sha256") if race in verified else None,
                                 "captured_at_utc":original.get("captured_at_utc") if race in verified else None,
                                 "runner_count":len(roster)},
                           "g04":{"horses":horses,
                                  "profiles_verified":sum(x["profile_state"]=="SHA_UTC_PRESTART_MATCH" for x in horses.values())},
                           "g05":{"track":track,"conditions_source_sha_utc_bound":conditions_original_ok},
                           "g06":None}
    markets=_g06_local_market_evidence(root,day,start_by_race)
    for race in range(1,13):
        output[str(race)]["g06"]=markets[str(race)]
    return {"schema":"kyoto_impl25_c11_per_family_proof.v1","day":day,
            "source_only":True,"prediction_ready":False,
            "jra_network_origin_authenticated_by_this_report":False,
            "g03_verified_races":len(verified),
            "g04_verified_profiles":sum(x["g04"]["profiles_verified"] for x in output.values()),
            "g05_bound_races":sum(x["g05"]["conditions_source_sha_utc_bound"] for x in output.values()),
            "g06_paired_market_races_locally_verified":sum(
                x["g06"]["state"]=="BOTH_MARKETS_SHA_UTC_PRESTART_VERIFIED_LOCALLY" for x in output.values()),
            "workout_independent_source_verified":False,
            "c10_auxiliary_receipt_available":aux is not None,
            "races":output}

def save(root,day):
    root=Path(root)
    report=assess(root,day)
    path=root/"c11_per_family_source_proof.json"
    if path.exists() or path.is_symlink():
        raise ValueError("c11_receipt_already_exists")
    path.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
    return report
