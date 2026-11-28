"""Offline byte/UTC integrity check for every captured original before sealing.

The output is an evidence quality report, never a race/market validity grant.
Runs even after a capture exception and leaves source bytes untouched.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from datetime import datetime,timezone
from pathlib import Path

def _utc(value):
    if not isinstance(value,str): return False
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
        return dt.utcoffset()==timezone.utc.utcoffset(None)
    except (ValueError,TypeError,AttributeError):
        return False

def check_originals(root, *, day, channel):
    root=Path(root)
    if day not in ("20261121","20261122","20261128","20261129") or channel not in ("PC","SP"):
        raise ValueError("invalid_identity")
    if not root.is_dir() or root.is_symlink():
        return {"schema":"kyoto_weekend_postflight.v1","day":day,
                "channel":channel,"state":"NO_ORIGINAL_SOURCE_TO_AUDIT",
                "source_verified":False, "prediction_ready":False}
    report={"schema":"kyoto_weekend_postflight.v1","day":day,"channel":channel,
            "source_verified":False,"prediction_ready":False,
            "both_markets_verified":False,"racecard_start_time_verified":False,
            "local_target_race_key":f"KYOTO:{day}:12",
            "observed_local_race_key":None,"race_identity_verified":False,
            "source_rows":[]}
    if channel=="PC":
        receipt=root/"receipt.json"
        if not receipt.is_file():
            report["state"]="RECEIPT_MISSING"
            return report
        try:
            saved=json.loads(receipt.read_text(encoding="utf8"))
            if saved.get("day")!=day:
                raise ValueError("day_mismatch")
            if saved.get("racecard_original_fetched") is True:
                if saved.get("racecard_number") != 12:
                    raise ValueError("pc_not_target_12r")
                key=f"KYOTO:{day}:12"
                if saved.get("local_observed_race_key",key)!=key:
                    raise ValueError("pc_observed_race_key_mismatch")
                report["observed_local_race_key"]=key
                report["race_identity_verified"]=True
            from diagnostics.kyoto_nov15_two_original_observer import accept_observation
            accepted=accept_observation(root)
            if accepted.get("state")!="TWO_ORIGINALS_MATCH_RECEIPT_ONLY":
                raise ValueError("observer_receipt_invalid")
            report["state"]="PC_OBSERVER_ORIGINALS_AND_RECEIPT_INTEGRITY_VERIFIED_ONLY"
            report["source_verified"]=True
            for basename,key in (
                ("official_pc_navigation_home.html","navigation_home"),
                ("official_selection.html","selection"),
                ("official_meeting.html","meeting"),
                ("official_racecard.html","racecard"),
                ("official_odds_menu.html","odds_menu"),
                ("official_odds_navigation_1.html","navigation_1"),
                ("official_odds_navigation_2.html","navigation_2"),
                ("official_quinella_odds.html","quinella"),
                ("official_bracket_quinella_odds.html","bracket_quinella")):
                path=root/basename
                if path.is_file():
                    raw=path.read_bytes()
                    report["source_rows"].append({"filename":basename,
                        "sha256":hashlib.sha256(raw).hexdigest(),
                        "captured_at_utc":saved.get(key+"_captured_at_utc")})
        except (OSError,ValueError,TypeError,KeyError) as exc:
            report["state"]="PC_PROVENANCE_REJECTED"
            report["error_class"]=type(exc).__name__
        return report
    saved_path=root/"sp_receipt.json"
    discovery_path=root/"sp_discovery_receipt.json"
    racewise=day in ("20261128","20261129") and any(re.fullmatch(r"r(?:0[1-9]|1[0-2])_(?:official_sp_.*\.html|sp_receipt\.json)|sp_all12_receipt\.json",p.name) for p in root.iterdir())
    if not saved_path.is_file() and not discovery_path.is_file() and not racewise:
        report["state"]="SP_RECEIPT_MISSING"
        return report
    try:
        if saved_path.is_file():
            saved=json.loads(saved_path.read_text(encoding="utf8"))
            if saved.get("day")!=day or saved.get("channel")!="SP":
                raise ValueError("sp_day_channel_mismatch")
            if "race_number" in saved:
                if saved["race_number"]!=12:
                    raise ValueError("sp_not_target_12r")
                key=f"KYOTO:{day}:12"
                if saved.get("local_target_race_key",key)!=key:
                    raise ValueError("sp_observed_race_key_mismatch")
                if (root/"official_sp_racecard.html").is_file():
                    report["observed_local_race_key"]=key
                    report["race_identity_verified"]=True
            for name,key in (("official_sp_racecard.html","racecard"),
                             ("official_sp_odds_menu.html","sp_odds_menu"),
                             ("official_sp_odds_navigation_1.html","sp_odds_navigation_1"),
                             ("official_sp_odds_navigation_2.html","sp_odds_navigation_2"),
                             ("official_sp_quinella_odds.html","sp_quinella"),
                             ("official_sp_bracket_quinella_odds.html","sp_bracket_quinella")):
                path=root/name
                if not path.exists():
                    continue
                if path.is_symlink() or not path.is_file():
                    raise ValueError("sp_path_not_regular")
                raw=path.read_bytes()
                if not 0<len(raw)<=1_500_000 or hashlib.sha256(raw).hexdigest()!=saved.get(key+"_sha256"):
                    raise ValueError("sp_original_sha_mismatch")
                stamp=saved.get(key+"_captured_at_utc")
                if not _utc(stamp):
                    raise ValueError("sp_original_utc_missing")
                report["source_rows"].append({"filename":name,
                    "sha256":hashlib.sha256(raw).hexdigest(),"captured_at_utc":stamp})
        if discovery_path.is_file():
            discovery=json.loads(discovery_path.read_text(encoding="utf8"))
            if discovery.get("day")!=day or not discovery.get("not_pc_derived"):
                raise ValueError("discovery_day_or_provenance_invalid")
            for item in discovery.get("attempts",[]):
                if not item.get("file"):
                    continue
                name=item["file"]
                if not re.fullmatch(r"official_sp_discovery_[1-6]\.html",name):
                    raise ValueError("discovery_original_name_invalid")
                path=root/name
                if (not path.is_file() or path.is_symlink()
                    or hashlib.sha256(path.read_bytes()).hexdigest()!=item.get("sha256")
                    or not _utc(item.get("captured_at_utc"))):
                    raise ValueError("discovery_original_invalid")
                report["source_rows"].append({"filename":name,
                    "sha256":item["sha256"],
                    "captured_at_utc":item["captured_at_utc"]})
        if racewise:
            # The live all-12 adapter prefixes each original and its receipt.
            # Do not confuse a verified discovery page with verified race bytes.
            fields=(("official_sp_racecard.html","racecard"),
                    ("official_sp_odds_menu.html","sp_odds_menu"),
                    ("official_sp_odds_navigation_1.html","sp_odds_navigation_1"),
                    ("official_sp_odds_navigation_2.html","sp_odds_navigation_2"),
                    ("official_sp_quinella_odds.html","sp_quinella"),
                    ("official_sp_bracket_quinella_odds.html","sp_bracket_quinella"))
            checks={}
            report["sp_race_integrity"]=checks
            for number in range(1,13):
                prefix=f"r{number:02d}_"
                rp=root/(prefix+"sp_receipt.json")
                originals=[p for p in root.iterdir() if p.name.startswith(prefix+"official_sp_")]
                if not originals and not rp.exists() and not rp.is_symlink():
                    checks[str(number)]={"state":"NO_RACE_ORIGINAL","verified_files":0}
                    continue
                try:
                    if not discovery_path.is_file() or discovery_path.is_symlink():
                        raise ValueError("sp_discovery_receipt_missing")
                    if rp.is_symlink() or not rp.is_file() or rp.stat().st_size>1_500_000:
                        raise ValueError("sp_race_receipt_missing")
                    saved=json.loads(rp.read_text(encoding="utf8"))
                    if (saved.get("day")!=day or saved.get("channel")!="SP" or
                        type(saved.get("race_number")) is not int or saved["race_number"]!=number or
                        saved.get("local_target_race_key")!=f"KYOTO:{day}:{number:02d}"):
                        raise ValueError("sp_race_receipt_identity")
                    if any(p.name not in {prefix+name for name,_ in fields} for p in originals):
                        raise ValueError("sp_unknown_race_original")
                    race_rows=[]
                    for name,key in fields:
                        path=root/(prefix+name)
                        claimed=(key+"_sha256" in saved or key+"_captured_at_utc" in saved or
                                 (key=="racecard" and saved.get("racecard_fetched") is True))
                        if not claimed and not path.exists() and not path.is_symlink():continue
                        if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=1_500_000:
                            raise ValueError("sp_race_original_missing_or_unsafe")
                        digest=hashlib.sha256(path.read_bytes()).hexdigest()
                        stamp=saved.get(key+"_captured_at_utc")
                        if digest!=saved.get(key+"_sha256") or not _utc(stamp) or datetime.fromisoformat(stamp.replace("Z","+00:00")).strftime("%Y%m%d")!=day:
                            raise ValueError("sp_race_original_sha_or_day_utc_mismatch")
                        race_rows.append({"filename":path.name,"sha256":digest,"captured_at_utc":stamp})
                    report["source_rows"].extend(race_rows)
                    names={r["filename"] for r in race_rows}
                    checks[str(number)]={"state":"DIGEST_UTC_CHECKED_ONLY" if names else "NO_RACE_ORIGINAL",
                        "verified_files":len(names),"racecard_verified_bytes":prefix+"official_sp_racecard.html" in names,
                        "both_market_originals_verified_bytes":all(prefix+name in names for name in ("official_sp_quinella_odds.html","official_sp_bracket_quinella_odds.html"))}
                except (OSError,ValueError,TypeError,KeyError,AttributeError) as exc:
                    checks[str(number)]={"state":"RACE_ORIGINAL_REJECTED","verified_files":0,"error_class":type(exc).__name__}
            # Keep independently verified bytes from unaffected races. A bad
            # race prevents a lane-wide integrity claim, not the AES archive.
            rejected=any(v["state"]=="RACE_ORIGINAL_REJECTED" for v in checks.values())
            report["state"]="SP_RACEWISE_PARTIAL_INTEGRITY" if rejected else "SP_RAW_ORIGINALS_DIGEST_UTC_CONSISTENT_ONLY"
            report["source_verified"]=bool(report["source_rows"]) and not rejected
        else:
            report["state"]="SP_RAW_ORIGINALS_DIGEST_UTC_CONSISTENT_ONLY"
            report["source_verified"]=bool(report["source_rows"])
    except (ValueError,TypeError,KeyError,OSError) as exc:
        report["state"]="SP_PROVENANCE_REJECTED"
        report["source_verified"]=False
        report["error_class"]=type(exc).__name__
    return report

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--day",choices=("20261121","20261122","20261128","20261129"),required=True)
    p.add_argument("--channel",choices=("PC","SP"),required=True)
    p.add_argument("--root",type=Path,required=True)
    args=p.parse_args(argv)
    if not args.root.is_dir():
        print("NO_CAPTURED_SOURCE_TO_VALIDATE")
        return
    data=check_originals(args.root,day=args.day,channel=args.channel)
    path=args.root/"source_verification.json"
    with path.open("x",encoding="utf8") as fp:
        json.dump(data,fp,sort_keys=True,ensure_ascii=False,indent=2)
        fp.write("\n")
    print("SOURCE_POSTFLIGHT="+data["state"])
if __name__=="__main__":
    main()
