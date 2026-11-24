"""Day-wide source coverage from independently revalidated saved originals.

A source observation is not a model input or settlement certificate. Keep
one registered roster denominator per race, original SHA/UTC and run ID.
Dynamic observations may change over time; identical-time disagreements and
different registered rosters remain conflicts, never silently combined.
"""
from datetime import date
from hashlib import sha256
from pathlib import Path
import json,re,tarfile,tempfile
from diagnostics.kyoto_g03_independent_partial import verify_partial
from diagnostics.kyoto_g03_to_g06_input_adapter import records_from_g03
from diagnostics.kyoto_g04_all_horse_profiles import _utc,_metadata
from diagnostics.kyoto_impl30_profile_resume import candidates
from diagnostics.jra_prior_form_offline import parse_horse_history
from diagnostics.kyoto_g05_conditions import _race_fields,_body_weights
from diagnostics.kyoto_g06_nested_bundle import verify_bundle
from diagnostics.kyoto_g06_item_level_recovery import recover_saved_markets

MARKETS=("quinella","bracket_quinella")
TRACK=("weather","turf_going","dirt_going")
HORSE=("profile","prior_form","body_weight_kg","body_weight_change_kg","workout")
DAYS=("20261121","20261122","20261128","20261129")

def digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def proof(sha,utc,value=None):
    if not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{64}",sha):raise ValueError("invalid_original_digest")
    return {"sha256":sha,"utc":_utc(utc).isoformat(),"value_digest":digest(value)}

def extract_slot(root,day,run_id):
    """Called inside authenticated decryption scope, no extra downloads/HTTP."""
    if day not in DAYS or not str(run_id).isdigit():raise ValueError("slot_identity")
    root=Path(root)
    verified=verify_partial(root,expected_day=day)["verified_race_numbers"]
    records=records_from_g03(root,day=day,skip_invalid_races=True)
    g03=json.loads((root/"g03_receipt.json").read_text(encoding="utf8"))
    try:profiles=candidates(root,day,run_id)
    except (ValueError,TypeError,KeyError,OSError):profiles={}
    output={}
    for race in verified:
        rec=records[race]
        if rec is None:continue
        original=g03["races"][str(race)]
        roster=original["runners"]
        start=rec["verified_start_utc"]
        # Link token is part of the identity digest, never exported in plaintext.
        identity=digest([(h["number"],h["frame"],h["name"],h["profile_navigation"]) for h in roster])
        p=root/f"g03_official_racecard_{race:02d}.html"
        raw=p.read_bytes()
        stamp=original["captured_at_utc"]
        src=proof(original["original_sha256"],stamp,identity)
        row={"roster_digest":identity,"start_utc":start,"racecard":src,
             "horses":{str(h["number"]):{} for h in roster},"track":{},"markets":{}}
        output[str(race)]=row
        try:
            for field,value in _race_fields(raw).items():
                if field in TRACK and value is not None:
                    row["track"][field]=proof(src["sha256"],stamp,value)
        except (ValueError,TypeError,KeyError):pass
        try:
            for n,(mass,delta) in _body_weights(raw,[h["number"] for h in roster]).items():
                for field,value in (("body_weight_kg",mass),("body_weight_change_kg",delta)):
                    if value is not None:row["horses"][str(n)][field]=proof(src["sha256"],stamp,value)
        except (ValueError,TypeError,KeyError):pass
        for h in roster:
            n=h["number"];item=profiles.get((race,n))
            if not item:continue
            try:
                when=_utc(item["captured_at_utc"]);cutoff=_utc(start)
                if when>=cutoff:continue
                parsed=parse_horse_history(item["raw"],source_url=item["url"],fetched_at_utc=when,
                    prediction_cutoff_utc=cutoff,target_date=date.fromisoformat(f"{day[:4]}-{day[4:6]}-{day[6:]}"),
                    expected_horse_name=h["name"],allow_verified_no_history=True)
                if parsed["invalid_rows"]:continue
                meta=_metadata(item["raw"],h["name"])
                row["horses"][str(n)]["profile"]=proof(item["sha256"],item["captured_at_utc"],meta)
                # This is successful structured history parsing, not attestation
                # of every possible feature or independent permanent horse ID.
                row["horses"][str(n)]["prior_form"]=proof(item["sha256"],item["captured_at_utc"],{
                    k:parsed[k] for k in ("prior_rows","nonfinish_rows","administrative_events","excluded_rows","history_status")})
            except (ValueError,TypeError,KeyError,OSError):continue
    bundle=root/"g06_source_bundle.tar.gz"
    if bundle.is_file() and not bundle.is_symlink():
        try:
            verify_bundle(bundle)
            with tempfile.TemporaryDirectory(prefix="kyoto_day_markets_") as tmp:
                work=Path(tmp)
                with tarfile.open(bundle,"r:gz") as archive:
                    for member in archive.getmembers():
                        if re.fullmatch(r"r(0[1-9]|1[0-2])/(pc|sp|pc_recovery|sp_recovery)/(receipt\.json|official_racecard\.html|official_odds_menu\.html|official_odds_navigation_\d+\.html|quinella_original\.html|bracket_quinella_original\.html)",member.name):
                            dest=work/member.name
                            dest.parent.mkdir(parents=True,exist_ok=True)
                            dest.write_bytes(archive.extractfile(member).read(1_500_001))
                for key,row in output.items():
                    item=records[int(key)]
                    try:
                        verified=recover_saved_markets(work/f"r{int(key):02d}",race_spec=item["race_spec"],
                            active_runners=item["active_runners"],verified_start_utc=item["verified_start_utc"])
                        for market in MARKETS:
                            selected=verified["markets"][market]["selected"]
                            if selected:
                                row["markets"][market]={**proof(selected["sha256"],selected["captured_at_utc"],selected["sha256"]),
                                    "channel":selected["channel"],"pair_count":selected["pair_count"],
                                    "cancelled_horses":selected["cancelled_horses"]}
                        row["paired_same_slot"]=verified["both_markets_verified"]
                    except (ValueError,TypeError,KeyError,OSError):continue
        except (ValueError,TypeError,KeyError,OSError,tarfile.TarError):pass
    return {"day":day,"run_id":str(run_id),"races":output}

def combine(day,slots):
    """Union by exact roster, never sum slot totals; latest bound observations."""
    if day not in DAYS:raise ValueError("day_identity")
    ids=set();accepted=[]
    for slot in slots:
        if slot["day"]!=day or not str(slot["run_id"]).isdigit() or str(slot["run_id"]) in ids:raise ValueError("duplicate_or_wrong_slot")
        ids.add(str(slot["run_id"]));accepted.append(slot)
    races={};totals={"racecards":0,"registered_horses_known":0,"paired_same_slot_races":0,
                     **{k:0 for k in HORSE+TRACK+MARKETS}}
    for n in range(1,13):
        key=str(n)
        rows=[(s["run_id"],s["races"][key]) for s in accepted if key in s["races"]]
        row={"state":"NO_VERIFIED_ROSTER","horses":{},"track":{},"markets":{},"paired_same_slot":False,
             "missing":[]}
        races[key]=row
        if not rows:
            row["missing"]=["racecard","roster",*TRACK,*MARKETS,"horse_denominator_unknown","official_result","official_payout"]
            continue
        signatures={(x["roster_digest"],x["start_utc"],tuple(sorted(x["horses"]))) for _,x in rows}
        if len(signatures)!=1:
            row["state"]="ROSTER_OR_START_CONFLICT"
            row["missing"]=["resolve_roster_or_start_conflict"]
            continue
        ident,start,numbers=next(iter(signatures));cutoff=_utc(start)
        def choose(pairs):
            valid=[]
            for rid,p in pairs:
                if not p:continue
                try:
                    stamp=_utc(p["utc"])
                    if stamp>=cutoff or not re.fullmatch(r"[0-9a-f]{64}",p["sha256"]):continue
                    valid.append((stamp,str(rid),p))
                except (ValueError,KeyError,TypeError):continue
            if not valid:return {"state":"MISSING"}
            latest=max(x[0] for x in valid)
            simultaneous=[x for x in valid if x[0]==latest]
            if len({x[2]["value_digest"] for x in simultaneous})!=1:
                return {"state":"SAME_TIMESTAMP_CONFLICT"}
            _,rid,p=max(simultaneous,key=lambda x:(x[1],x[2]["sha256"]))
            return {"state":"SOURCE_VERIFIED","run_id":rid,**p}
        row.update(state="ROSTER_VERIFIED",roster_digest=ident,start_utc=start,racecard=choose([(r,x["racecard"]) for r,x in rows]))
        totals["racecards"]+=int(row["racecard"]["state"]=="SOURCE_VERIFIED")
        totals["registered_horses_known"]+=len(numbers)
        for h in numbers:
            row["horses"][h]={}
            for f in HORSE:
                result=choose([(r,x["horses"][h].get(f)) for r,x in rows])
                row["horses"][h][f]=result
                totals[f]+=int(result["state"]=="SOURCE_VERIFIED")
                if result["state"]!="SOURCE_VERIFIED":row["missing"].append(f"horse_{h}:{f}:{result['state']}")
        for section,fields in (("track",TRACK),("markets",MARKETS)):
            for f in fields:
                result=choose([(r,x[section].get(f)) for r,x in rows])
                row[section][f]=result
                totals[f]+=int(result["state"]=="SOURCE_VERIFIED")
                if result["state"]!="SOURCE_VERIFIED":row["missing"].append(f"{f}:{result['state']}")
        # Individual market coverage does not imply a coherent pair snapshot.
        a,b=(row["markets"][m] for m in MARKETS)
        row["paired_same_slot"]=a["state"]==b["state"]=="SOURCE_VERIFIED" and a["run_id"]==b["run_id"] and a["cancelled_horses"]==b["cancelled_horses"] and any(str(r)==a["run_id"] and x.get("paired_same_slot") is True for r,x in rows)
        totals["paired_same_slot_races"]+=int(row["paired_same_slot"])
        if not row["paired_same_slot"]:row["missing"].append("paired_market_same_slot")
        row["missing"]+=["official_result","official_payout"]
    return {"schema":"kyoto_impl30_day_source_coverage.v1","day":day,"authenticated_pc_slots":len(accepted),
            "totals":totals,"race_denominator":12,"horse_denominator_complete":totals["racecards"]==12,
            "races":races,"full_data_acquisition_certified":False,"prediction_ready":False}
