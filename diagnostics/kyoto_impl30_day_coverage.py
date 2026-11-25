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
TRACK_EXTRA=("turf_moisture_finish_pct","turf_moisture_turn4_pct","dirt_moisture_finish_pct","dirt_moisture_turn4_pct")
HORSE=("profile","prior_form","body_weight_kg","body_weight_change_kg","workout")
DAYS=("20261121","20261122","20261128","20261129")

def digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def proof(sha,utc,value=None):
    if not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{64}",sha):raise ValueError("invalid_original_digest")
    return {"sha256":sha,"utc":_utc(utc).isoformat(),"value_digest":digest(value)}

def independent_track(root,day):
    """Replay the independent official track original, not its summary flags."""
    from diagnostics.kyoto_g05_official_track import parse_kyoto_track,KYOTO_TRACK_PAGE,MAX_HTML
    original=root/"g05_official_kyoto_track.html"
    receipt=root/"g05_track_receipt.json"
    if any(p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=MAX_HTML for p in (original,receipt)):
        return {}
    try:
        stored=json.loads(receipt.read_text(encoding="utf8"))
        stamp=_utc(stored["captured_at_utc"])
        requested=_utc(stored["requested_at_utc"])
        if stamp.strftime("%Y%m%d")!=day or requested.strftime("%Y%m%d")!=day or requested>stamp:return {}
        replay=parse_kyoto_track(original.read_bytes(),day,KYOTO_TRACK_PAGE,stamp.isoformat())
        if stored!={**replay,"requested_at_utc":requested.isoformat()} or replay["same_day_official_meeting_heading_verified"] is not True:return {}
        return {k:{**proof(replay["source_sha256"],stamp.isoformat(),replay[k]),
                   "source_kind":"OFFICIAL_INDEPENDENT_TRACK_PAGE","publication_time_independently_verified":False}
                for k in TRACK+TRACK_EXTRA if replay.get(k) is not None}
    except (OSError,ValueError,KeyError,TypeError,AttributeError):return {}

def extract_slot(root,day,run_id):
    """Called inside authenticated decryption scope, no extra downloads/HTTP."""
    if day not in DAYS or not str(run_id).isdigit():raise ValueError("slot_identity")
    root=Path(root)
    track=independent_track(root,day) if day in ("20261128","20261129") else {}
    try:
        verified=verify_partial(root,expected_day=day)["verified_race_numbers"]
        records=records_from_g03(root,day=day,skip_invalid_races=True)
        g03=json.loads((root/"g03_receipt.json").read_text(encoding="utf8"))
    except (OSError,ValueError,KeyError,TypeError):
        if not track:raise
        # Track evidence survives an unrelated racecard failure. No roster
        # or race coverage is inferred from the course-level page.
        return {"day":day,"run_id":str(run_id),"races":{},"independent_track":track}
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
        row={"roster_digest":identity,"named_roster_digest":digest(rec["expected_named_runners"]),"start_utc":start,"racecard":src,
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
    return {"day":day,"run_id":str(run_id),"races":output,**({"independent_track":track} if track else {})}

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
        signatures={(x["roster_digest"],x["named_roster_digest"],x["start_utc"],tuple(sorted(x["horses"]))) for _,x in rows}
        if len(signatures)!=1:
            row["state"]="ROSTER_OR_START_CONFLICT"
            row["missing"]=["resolve_roster_or_start_conflict"]
            continue
        ident,named,start,numbers=next(iter(signatures));cutoff=_utc(start)
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
        row.update(state="ROSTER_VERIFIED",roster_digest=ident,named_roster_digest=named,start_utc=start,racecard=choose([(r,x["racecard"]) for r,x in rows]))
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
                if section=="track" and result["state"]=="MISSING" and day in ("20261128","20261129"):
                    # Fill only a missing field; never override a racecard
                    # observation or suppress a same-timestamp conflict.
                    # The existing choose() enforces the race start cutoff.
                    result=choose([(s["run_id"],s.get("independent_track",{}).get(f)) for s in accepted])
                row[section][f]=result
                totals[f]+=int(result["state"]=="SOURCE_VERIFIED")
                if result["state"]!="SOURCE_VERIFIED":row["missing"].append(f"{f}:{result['state']}")
        # Individual market coverage does not imply a coherent pair snapshot.
        a,b=(row["markets"][m] for m in MARKETS)
        row["paired_same_slot"]=a["state"]==b["state"]=="SOURCE_VERIFIED" and a["run_id"]==b["run_id"] and a["cancelled_horses"]==b["cancelled_horses"] and any(str(r)==a["run_id"] and x.get("paired_same_slot") is True for r,x in rows)
        totals["paired_same_slot_races"]+=int(row["paired_same_slot"])
        if not row["paired_same_slot"]:row["missing"].append("paired_market_same_slot")
        row["missing"]+=["official_result","official_payout"]
    # Supplementary moisture observations remain separate from the fixed
    # coverage counters and are never treated as measured publication times.
    if day in ("20261128","20261129"):
        for row in races.values():
            if row.get("state")!="ROSTER_VERIFIED":continue
            cutoff=_utc(row["start_utc"])
            observations={}
            for field in TRACK_EXTRA:
                eligible=[]
                for slot in accepted:
                    p=slot.get("independent_track",{}).get(field)
                    if not p:continue
                    try:
                        stamp=_utc(p["utc"])
                        if stamp.strftime("%Y%m%d")==day and stamp<cutoff and re.fullmatch(r"[0-9a-f]{64}",p["sha256"]):eligible.append((stamp,slot["run_id"],p))
                    except (ValueError,TypeError,KeyError,AttributeError):continue
                if not eligible:continue
                latest=max(x[0] for x in eligible);same=[x for x in eligible if x[0]==latest]
                if len({x[2]["value_digest"] for x in same})!=1:continue
                _,rid,p=max(same,key=lambda x:str(x[1]));observations[field]={"state":"SOURCE_VERIFIED", "run_id":rid,**p}
            row["supplementary_track_observations"]=observations
    return {"schema":"kyoto_impl30_day_source_coverage.v1","day":day,"authenticated_pc_slots":len(accepted),
            "totals":totals,"race_denominator":12,"horse_denominator_complete":totals["racecards"]==12,
            "races":races,"full_data_acquisition_certified":False,"prediction_ready":False}

def include_postrace(coverage,revisions,*,roster,starts):
    """Bind the independently replayed final-page observation to the same race
    denominator. No summary is promoted to settlement or full certification.
    Called only after replay_history has reopened authenticated original bytes.
    """
    import copy
    report=copy.deepcopy(coverage)
    day=report["day"]
    if revisions.get("day")!=day or revisions.get("schema")!="kyoto_impl30_postrace_replay.v1":
        raise ValueError("postrace_day_or_schema")
    report["postrace_history_index_complete"]=revisions.get("prior_artifact_index_complete") is True
    report["totals"].update(official_result=0,official_payout=0,dual_page_published_source=0,official_published_payout=0)
    for race in range(1,13):
        row=report["races"][str(race)]
        post=revisions["races"].get(str(race),{})
        row["postrace"]={"state":"MISSING_OR_UNVERIFIED"}
        if row["state"]!="ROSTER_VERIFIED" or not roster.get(race) or not starts.get(race):
            continue
        if row["named_roster_digest"]!=digest(roster[race]) or _utc(row["start_utc"])!=_utc(starts[race]):
            row["postrace"]["state"]="ROSTER_OR_START_CONFLICT"
            continue
        # Source publication and explicit finality are separate; no settlement
        # permission is implied by either acquisition counter.
        chain=revisions.get("published_payout_chains",{}).get(str(race),{})
        if chain.get("state")=="CONFLICT":
            row["postrace"]["state"]="PUBLISHED_PAYOUT_CONFLICT"
            continue
        if chain.get("state")=="OFFICIAL_PUBLISHED_PAYOUT_CHAIN" and report["postrace_history_index_complete"]:
            entries=chain.get("revisions",[])
            if entries:
                latest=entries[-1]
                obs=latest.get("observation",{})
                try:
                    if obs.get("official_payout_publication_verified") is not True or obs.get("day")!=day or obs.get("race")!=race:raise ValueError("published_identity")
                    if any(_utc(obs[k])<=_utc(starts[race]) for k in ("result_utc","payout_utc")) or set(obs["markets"])!=set(MARKETS):raise ValueError("published_cutoff_or_markets")
                    row["postrace"].update(state="DUAL_PAGE_OFFICIAL_PUBLISHED_PAYOUT",run_id=latest["run_id"],
                        published_revision=latest["version"],published_chain_sha256=latest["sha256"],
                        result=proof(obs["result_sha256"],obs["result_utc"],obs["markets"]),
                        payout=proof(obs["payout_sha256"],obs["payout_utc"],obs["markets"]),
                        settlement_authorized=False)
                    report["totals"]["dual_page_published_source"]+=1
                    report["totals"]["official_published_payout"]+=1
                except (ValueError,KeyError,TypeError):pass
        if post.get("state")!="SOURCE_REVISION_CHAIN":continue
        if not report["postrace_history_index_complete"]:
            row["postrace"]["state"]="REVISION_HISTORY_INCOMPLETE"
            continue
        entries=post.get("revisions",[])
        if not entries:continue
        latest=entries[-1]
        obs=latest.get("observation",{})
        if obs.get("state")!="DUAL_PAGE_EXPLICIT_FINAL" or obs.get("day")!=day or obs.get("race")!=race:
            continue
        try:
            if any(_utc(obs[k])<=_utc(starts[race]) for k in ("result_utc","payout_utc")):continue
            if set(obs["markets"])!=set(MARKETS):continue
            result=proof(obs["result_sha256"],obs["result_utc"],obs["markets"])
            payout=proof(obs["payout_sha256"],obs["payout_utc"],obs["markets"])
        except (ValueError,KeyError,TypeError):continue
        row["postrace"]={"state":"DUAL_PAGE_FINAL_SOURCE_RECONCILED",
                         "result":result,"payout":payout,"run_id":latest["run_id"],
                         "revision":latest["version"],"settlement_authorized":False}
        report["totals"]["official_result"]+=1
        report["totals"]["official_payout"]+=1
        row["missing"]=[x for x in row["missing"] if x not in ("official_result","official_payout")]
    return report
