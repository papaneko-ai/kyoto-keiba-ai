"""Independent day-close evidence review, without source HTTP or code promotion.

Use existing authenticated source replays. Detect missing executions as well as
data gaps. Never convert a workflow success or receipt flag into data credit.
"""
import argparse,hashlib,json,os,re,subprocess,tempfile,sys,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
if __package__:
    from .kyoto_repair_control import recover_collection
    from .kyoto_fixed_risk_worklist import worklist
    from .kyoto_job_artifact_state import classify_artifact, SKIPPED
    from .kyoto_day_supplemental_replay import review_sp, review_cushion
else:
    from kyoto_repair_control import recover_collection
    from kyoto_fixed_risk_worklist import worklist
    from kyoto_job_artifact_state import classify_artifact, SKIPPED
    from kyoto_day_supplemental_replay import review_sp, review_cushion

REPO="papaneko-ai/kyoto-keiba-ai"
DAYS=("20261128","20261129")
PREFIX=".github/workflows/kyoto-20261128-29-"
SCHEDULE={
 "two-source-production-observer.yml":lambda d:("15 0","15 1","5 2","50 2") if d=="20261128" else ("15 0","15 1","10 2","55 2"),
 "auxiliary-refresh.yml":lambda d:("30 3","30 4","30 5","30 6"),
 "postrace-evidence.yml":lambda d:("0 10","0 13"),
 "result-handoff.yml":lambda d:("0 12",),
 "workout-source.yml":lambda d:("30 11","30 22")}
LANES={"two-source-production-observer.yml":("pc","sp"),"auxiliary-refresh.yml":("auxiliary",),
 "postrace-evidence.yml":("postrace",),"result-handoff.yml":("handoff","cushion-day"),
 "workout-source.yml":("workout",),"cushion-source.yml":("cushion",)}
FAMILIES=("racecard","profile","prior_form","body_weight_kg","body_weight_change_kg","workout",
 "weather","turf_going","dirt_going","quinella","bracket_quinella","paired_market_same_slot","official_result","official_payout")
HORSE=FAMILIES[1:6]
TRACK=FAMILIES[6:9]
MARKETS=FAMILIES[9:11]
EXTRA=("turf_moisture_finish_pct","turf_moisture_turn4_pct","dirt_moisture_finish_pct","dirt_moisture_turn4_pct")
FAMILIES=FAMILIES+EXTRA
RACES=tuple(str(n) for n in range(1,13))
def canon(obj):return json.dumps(obj,sort_keys=True,ensure_ascii=True,separators=(",",":"),allow_nan=False).encode()
def digest(raw):return hashlib.sha256(raw).hexdigest()
def stamp(x):
    t=datetime.fromisoformat(x.replace("Z","+00:00"))
    if t.utcoffset()!=timedelta(0):raise ValueError("not_utc")
    return t
def is_sha(v):return isinstance(v,str) and re.fullmatch(r"[a-f0-9]{64}",v) is not None
def gh(path,trace=None):
    field="workflow_runs" if "/runs?created=" in path else "artifacts" if "/artifacts?" in path else "jobs" if "/jobs?" in path else None
    if field is None:raise ValueError("unsupported_metadata_scope")
    return recover_collection(path,field,trace=trace)
def index(day,filename,doc):
    if filename not in LANES or (day not in DAYS and not (filename=="workout-source.yml" and day=="20261127")):raise ValueError("invalid_index_scope")
    rows=doc["workflow_runs"]
    if type(doc["total_count"]) is not int or doc["total_count"]!=len(rows) or len(rows)>400:raise ValueError("incomplete_run_index")
    date=f"{day[:4]}-{day[4:6]}-{day[6:]}"
    seen=set();out=[]
    for r in rows:
        rid=r.get("id")
        if type(rid) is not int or rid<=0 or rid in seen or r.get("head_repository",{}).get("full_name")!=REPO or r.get("head_branch")!="main" or str(r.get("path","")).split("@",1)[0]!=PREFIX+filename or not re.fullmatch(r"[a-f0-9]{40}",r.get("head_sha","")):raise ValueError("run_identity_mismatch")
        seen.add(rid)
        if not str(r.get("created_at","")).startswith(date):raise ValueError("run_day_mismatch")
        if r.get("event") not in ("schedule","workflow_dispatch","workflow_run"):raise ValueError("run_event_mismatch")
        title=r.get("name","")
        out.append({"id":rid,"event":r["event"],"native_title":title if re.fullmatch(r"kyoto-native:[0-9 ]+11 \*",title) else None,
            "head_sha":r["head_sha"],"created_at":stamp(r["created_at"]).isoformat(),"status":r.get("status","unknown"),"conclusion":r.get("conclusion")})
    return sorted(out,key=lambda r:r["id"])
def slots(day,filename,runs,now):
    if filename not in SCHEDULE:return []
    out=[]
    for cron in SCHEDULE[filename](day):
        minute,hour=map(int,cron.split())
        due=datetime(int(day[:4]),int(day[4:6]),int(day[6:]),hour,minute,tzinfo=timezone.utc)
        if filename=="workout-source.yml":due-=timedelta(days=1)
        title=f"kyoto-native:{cron} {due.day} 11 *"
        exact=[r for r in runs if r["event"]=="schedule" and r["native_title"]==title]
        # Dispatches cannot be guessed to correspond to an exact slot.
        state="NOT_DUE" if now<due else ("NATIVE_SLOT_GRACE" if now<due+timedelta(minutes=25) else "NATIVE_SLOT_NOT_OBSERVED") if not exact else "NATIVE_SLOT_AMBIGUOUS" if len(exact)!=1 else "NATIVE_RUN_UNFINISHED" if exact[0]["status"]!="completed" else "NATIVE_RUN_COMPLETED" if exact[0]["conclusion"]=="success" else "NATIVE_RUN_UNSUCCESSFUL"
        out.append({"cron":title[13:],"due_utc":due.isoformat(),"state":state,"run_ids":[r["id"] for r in exact],
                    "late_seconds":max(0,int((stamp(exact[0]["created_at"])-due).total_seconds())) if len(exact)==1 else None})
    return out
def external_slots(day,filename,runs,now):
    """Observe dispatches near the fixed plan; no provider or data credit."""
    out=[]
    for native in slots(day,filename,runs,now):
        due=stamp(native["due_utc"])+timedelta(minutes=2)
        exact=[r for r in runs if r["event"]=="workflow_dispatch" and due<=stamp(r["created_at"])<due+timedelta(minutes=5)]
        state=("NOT_DUE" if now<due else "DISPATCH_GRACE" if now<due+timedelta(minutes=5) else "DISPATCH_NOT_OBSERVED") if not exact else "DISPATCH_AMBIGUOUS" if len(exact)!=1 else "DISPATCH_UNFINISHED" if exact[0]["status"]!="completed" else "DISPATCH_COMPLETED" if exact[0]["conclusion"]=="success" else "DISPATCH_UNSUCCESSFUL"
        out.append({"due_utc":due.isoformat(),"state":state,"run_ids":[r["id"] for r in exact],"provider_proved":False,"source_success_certified":False})
    return out
def proof_ok(value,cutoff,day,allowed,after=False):
    try:
        utc=stamp(value["utc"])
        return (after or value.get("state")=="SOURCE_VERIFIED") and is_sha(value["sha256"]) and is_sha(value["value_digest"]) and str(value.get("run_id")) in allowed and utc.strftime("%Y%m%d")==day and (utc>cutoff if after else utc<cutoff)
    except (TypeError,KeyError,ValueError,AttributeError):return False
WORKOUT_READER_SHA="bd800bc30db60919e274eadac419016c963e77de"
def workout_proof_ok(v,cutoff,allowed):
    try:
        if v["state"]!="INDEPENDENT_WORKOUT_SOURCE_REPLAYED" or not is_sha(v["value_digest"]) or type(v["record_count"]) is not int or v["record_count"]<1:return False
        proofs=v["source_proofs"]
        if not isinstance(proofs,list) or not proofs or len(proofs)>300:return False
        providers=set()
        for p in proofs:
            t=stamp(p["utc"])
            if str(p["run_id"]) not in allowed or not is_sha(p["sha256"]) or not cutoff-timedelta(days=31)<=t<cutoff:return False
            if p["provider"] not in ("white-green.jp","umasiru.com","talmudic.net"):return False
            providers.add(p["provider"])
        return (v["mode"]=="PRIMARY" and providers=={"white-green.jp"}) or (v["mode"]=="SECONDARY_CORROBORATED" and len(providers)>=2 and providers<={"umasiru.com","talmudic.net"})
    except (ValueError,KeyError,TypeError,AttributeError):return False

def review_workouts(day,metadata,coverage,roster,starts,key,reader):
    # Bind the same independently replayed official names/frame/numbers used
    # for the day coverage. Never count a producer's normalized receipt alone.
    from diagnostics.kyoto_impl30_day_coverage import digest as roster_digest
    bound={}
    for n in range(1,13):
        row=coverage["races"][str(n)]
        named=roster.get(n)
        if row.get("state")!="ROSTER_VERIFIED" or not named or not starts.get(n):continue
        if row.get("named_roster_digest")!=roster_digest(named) or stamp(row["start_utc"])!=stamp(starts[n]):continue
        names={str(h):name for h,frame,name in named}
        if set(names)!=set(row["horses"]):continue
        bound[str(n)]={"roster":names,"start":row["start_utc"],"named_roster_digest":row["named_roster_digest"]}
    w=metadata["workout-source.yml"]
    candidates=[r for r in w["runs"] if r.get("artifacts",{}).get("workout",{}).get("state")=="PRESENT"]
    candidates=sorted(candidates,key=lambda x:x["id"],reverse=True)
    errors=[];archives=[];end=time.monotonic()+120
    if not w["index_complete"]:errors.append({"error_class":"WORKOUT_RUN_INDEX_INCOMPLETE"})
    if len(candidates)>16:errors.append({"error_class":"WORKOUT_ARCHIVE_BOUND"})
    reader=Path(reader).resolve()
    if subprocess.check_output(["git","rev-parse","HEAD"],cwd=reader,text=True,stderr=subprocess.DEVNULL,timeout=5).strip()!=WORKOUT_READER_SHA:
        raise ValueError("workout_reader_revision")
    with tempfile.TemporaryDirectory(prefix="kyoto_day_workout_") as tmp:
        root=Path(tmp)
        for r in candidates[:16]:
            rid=r["id"]
            try:
                left=end-time.monotonic()
                if left<=0:raise TimeoutError()
                target=root/str(rid);target.mkdir()
                subprocess.run(["gh","run","download",str(rid),"--repo",REPO,"--name",f"kyoto-workout-{rid}-{day}","--dir",str(target)],
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=min(25,left),check=True)
                archives.append([rid,str(target)])
            except Exception as exc:errors.append({"run_id":str(rid),"error_class":type(exc).__name__})
        p=root/"config.json";p.write_text(json.dumps({"day":day,"rosters":bound,"archives":archives},ensure_ascii=False),encoding="utf8")
        script=Path(__file__).with_name("kyoto_day_workout_replay.py").resolve()
        env={"PATH":os.environ.get("PATH",""),"PYTHONPATH":str(reader),"PYTHONUTF8":"1","ARCHIVE_KEY":key}
        raw=subprocess.check_output([sys.executable,str(script),str(p)],cwd=reader,env=env,stderr=subprocess.DEVNULL,timeout=120)
        if len(raw)>5_000_000:raise ValueError("workout_replay_size")
        doc=json.loads(raw)
    if doc["day"]!=day or doc["schema"]!="kyoto_independent_workout_day_replay.v1" or doc["source_http_requests"]!=0 or doc["production_coverage_authorized"] is not False:raise ValueError("workout_replay_identity")
    doc["errors"]+=errors
    doc["reader_sha"]=WORKOUT_READER_SHA
    doc["examined_archive_run_ids"]=[str(rid) for rid,p in archives]
    doc["archive_index_complete"]=not doc["errors"] and len(archives)==len(candidates) and w["index_complete"]
    return doc

WEIGHT_FIELDS=("body_weight_kg","body_weight_change_kg")
def cancellation_set(day,row,evidence,allowed):
    """Exempt only the two weight fields of a positively verified cancellation.
    A missing value, receipt total, result row or mismatched card is not proof.
    """
    try:
        card=row["racecard"];cutoff=stamp(row["start_utc"])
        if not proof_ok(card,cutoff,day,allowed):return None
        if evidence["state"]!="CANCELLATION_STATUS_FROM_REPLAYED_CARD" or evidence["day"]!=day:return None
        if any(evidence[k]!=card[k] for k in ("run_id","sha256","utc")):return None
        if evidence["named_roster_digest"]!=row["named_roster_digest"] or evidence["roster_digest"]!=row["roster_digest"]:return None
        if evidence["start_utc"]!=row["start_utc"] or evidence["registered_horse_count"]!=len(row["horses"]):return None
        ns=evidence["cancelled_horses"]
        if not isinstance(ns,list) or any(type(n) is not int or str(n) not in row["horses"] for n in ns) or len(set(ns))!=len(ns) or len(ns)==len(row["horses"]):return None
        return set(map(str,ns))
    except (TypeError,KeyError,ValueError,AttributeError):return None

def replay_cancelled_card(raw,day,race,row,run_id):
    # These are the existing exact G03 and adapter readers, not a second parser.
    from diagnostics.kyoto_g03_independent_partial import verify_partial
    from diagnostics.kyoto_g03_to_g06_input_adapter import records_from_g03
    from diagnostics.kyoto_impl30_day_coverage import digest as source_digest
    root=Path(raw)
    if race not in verify_partial(root,expected_day=day)["verified_race_numbers"]:raise ValueError("race_not_verified")
    rec=records_from_g03(root,day=day,skip_invalid_races=True)[race]
    if rec is None:raise ValueError("adapter_unverified")
    item=json.loads((root/"g03_receipt.json").read_text(encoding="utf8"))["races"][str(race)]
    horses=item["runners"]
    ident=source_digest([(h["number"],h["frame"],h["name"],h["profile_navigation"]) for h in horses])
    named=source_digest(rec["expected_named_runners"])
    e={"state":"CANCELLATION_STATUS_FROM_REPLAYED_CARD","day":day,"run_id":str(run_id),
       "sha256":item["original_sha256"],"utc":stamp(item["captured_at_utc"]).isoformat(),
       "roster_digest":ident,"named_roster_digest":named,"start_utc":rec["verified_start_utc"],
       "registered_horse_count":len(horses),"cancelled_horses":sorted(h["number"] for h in horses if h.get("cancelled") is True)}
    if cancellation_set(day,row,e,{str(run_id)}) is None:raise ValueError("cancellation_card_binding")
    return e

def review_cancellations(day,metadata,coverage,key):
    from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
    lane_by_run={}
    for filename,lane in (("two-source-production-observer.yml","pc"),("auxiliary-refresh.yml","auxiliary")):
        for r in metadata[filename]["runs"]:
            if r.get("artifacts",{}).get(lane,{}).get("state")=="PRESENT":
                lane_by_run.setdefault(str(r["id"]),[]).append(lane)
    by={}
    for n,row in coverage["races"].items():
        if row.get("state")!="ROSTER_VERIFIED":continue
        card=row.get("racecard",{});rid=str(card.get("run_id"))
        if card.get("state")=="SOURCE_VERIFIED":by.setdefault(rid,[]).append((int(n),row))
    result={};errors=[];end=time.monotonic()+120
    for rid,rows in sorted(by.items(),key=lambda x:x[0]):
        try:
            lanes=lane_by_run.get(rid,[])
            if len(lanes)!=1:raise ValueError("missing_or_ambiguous_archive_lane")
            left=end-time.monotonic()
            if left<=0:raise TimeoutError("cancellation_replay_budget")
            with tempfile.TemporaryDirectory(prefix="kyoto_cancel_review_") as td:
                root=Path(td);cipher=root/"cipher";cipher.mkdir()
                subprocess.run(["gh","run","download",rid,"--repo",REPO,"--name",f"kyoto-{lanes[0]}-{rid}-{day}","--dir",str(cipher)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=min(25,left))
                raw=root/"raw";decrypt_evidence(cipher,raw,key_hex=key,repo=REPO,run_id=rid)
                for n,row in rows:
                    try:result[str(n)]=replay_cancelled_card(raw,day,n,row,rid)
                    except Exception as exc:errors.append({"run_id":rid,"race":n,"error_class":type(exc).__name__})
        except Exception as exc:errors.append({"run_id":rid,"error_class":type(exc).__name__})
    return {"schema":"kyoto_independent_cancellation_review.v1","day":day,"races":result,"errors":errors,"source_http_requests":0}

def coverage_gaps(day,coverage,allowed_run_ids,workout_review=None,allowed_workout_run_ids=(),cancellation_review=None,allowed_sp_market_run_ids=()):
    """Compute missing cells from independently replayed aggregate, not totals."""
    if coverage.get("day")!=day or coverage.get("schema")!="kyoto_impl30_day_source_coverage.v1" or coverage.get("race_denominator")!=12 or set(coverage.get("races",{}))!=set(RACES):raise ValueError("coverage_identity_incomplete")
    allowed=set(map(str,allowed_run_ids))
    allowed_workout=set(map(str,allowed_workout_run_ids))
    allowed_markets=allowed|set(map(str,allowed_sp_market_run_ids))
    workout_review=workout_review or {}
    workout_rows=workout_review.get("races",{}) if workout_review.get("day")==day and workout_review.get("schema")=="kyoto_independent_workout_day_replay.v1" else {}
    cancellation_review=cancellation_review or {}
    cancel_rows=cancellation_review.get("races",{}) if cancellation_review.get("day")==day and cancellation_review.get("schema")=="kyoto_independent_cancellation_review.v1" else {}
    totals={f:{"expected":0,"verified":0,"unknown_denominator_races":0} for f in FAMILIES}
    exemptions={f:0 for f in WEIGHT_FIELDS}
    detail=[]
    for race in RACES:
        row=coverage["races"][race];missing=[];bound=[]
        def check(f,good,horse=None,proof=None):
            t=totals[f];t["expected"]+=1;t["verified"]+=int(bool(good))
            if not good:missing.append({"family":f,**({"horse":horse} if horse else {})})
            elif proof is not None:bound.append({"family":f,**({"horse":horse} if horse else {}),**{k:proof[k] for k in ("run_id","utc","sha256")}})
        try:
            cutoff=stamp(row["start_utc"])
            horses=row["horses"]
            roster=(row.get("state")=="ROSTER_VERIFIED" and is_sha(row["roster_digest"]) and is_sha(row["named_roster_digest"]) and cutoff.strftime("%Y%m%d")==day and isinstance(horses,dict) and 2<=len(horses)<=18 and set(horses)=={str(n) for n in range(1,len(horses)+1)})
        except (ValueError,KeyError,TypeError,AttributeError):roster=False
        if not roster:
            for f in FAMILIES:
                if f in HORSE:totals[f]["unknown_denominator_races"]+=1
                else:check(f,False)
            detail.append({"race":int(race),"state":"ROSTER_OR_START_UNPROVED","missing":missing,"unknown_horse_families":list(HORSE)})
            continue
        card=row.get("racecard",{})
        check("racecard",proof_ok(card,cutoff,day,allowed),proof=card)
        cancelled_weights=cancellation_set(day,row,cancel_rows.get(race,{}),allowed)
        not_applicable=[]
        for h in sorted(horses,key=int):
            for f in HORSE:
                if f in WEIGHT_FIELDS and cancelled_weights is not None and h in cancelled_weights:
                    exemptions[f]+=1
                    not_applicable.append({"family":f,"horse":h,"reason":"OFFICIAL_PRESTART_CANCELLATION"})
                    continue
                if f=="workout":
                    wr=workout_rows.get(race,{})
                    v=wr.get("horses",{}).get(h,{}) if wr.get("named_roster_digest")==row["named_roster_digest"] and wr.get("start")==row["start_utc"] else {}
                    ok=workout_proof_ok(v,cutoff,allowed_workout)
                    check(f,ok,h)
                    if ok:bound.append({"family":f,"horse":h,"record_count":v["record_count"],"value_digest":v["value_digest"],"source_proofs":v["source_proofs"]})
                else:
                    v=horses[h].get(f,{})
                    check(f,proof_ok(v,cutoff,day,allowed),h,v)
        for section,keys in (("track",TRACK),("supplementary_track_observations",EXTRA)):
            for f in keys:
                v=row.get(section,{}).get(f,{})
                check(f,proof_ok(v,cutoff,day,allowed),proof=v)
        a,b=(row.get("markets",{}).get(f,{}) for f in MARKETS)
        for f,v in zip(MARKETS,(a,b)):check(f,proof_ok(v,cutoff,day,allowed_markets),proof=v)
        cancelled=a.get("cancelled_horses")
        valid_cancel=isinstance(cancelled,list) and all(type(n) is int and str(n) in horses for n in cancelled) and len(set(cancelled))==len(cancelled)
        check("paired_market_same_slot",row.get("paired_same_slot") is True and proof_ok(a,cutoff,day,allowed_markets) and proof_ok(b,cutoff,day,allowed_markets) and a.get("run_id")==b.get("run_id") and valid_cancel and cancelled==b.get("cancelled_horses"))
        p=row.get("postrace",{})
        for f,k in (("official_result","result"),("official_payout","payout")):
            v=p.get(k,{})
            v={**v,"run_id":p.get("run_id")} if isinstance(v,dict) else {}
            check(f,p.get("state")=="DUAL_PAGE_FINAL_SOURCE_RECONCILED" and coverage.get("postrace_history_index_complete") is True and proof_ok(v,cutoff,day,allowed,True),proof=v)
        detail.append({"race":int(race),"state":"GAPS" if missing else "ALL_REVIEWED_CELLS_PRESENT","registered_horses":len(horses),"missing":missing,"bound_evidence":bound,"weight_not_applicable":not_applicable,"cancellation_status_verified":cancelled_weights is not None,"postrace_publication_only":p.get("state")=="DUAL_PAGE_OFFICIAL_PUBLISHED_PAYOUT"})
    return {"counts":totals,"races":detail,"weight_not_applicable_counts":exemptions,"all_reviewed_cells_present":all(t["expected"]==t["verified"] and not t["unknown_denominator_races"] for t in totals.values()),"full_acquisition_certified":False}
def collect_metadata(day,now):
    date=f"{day[:4]}-{day[4:6]}-{day[6:]}"
    reports={};errors=[]
    for filename,lanes in LANES.items():
        recovery_trace=[]
        try:
            days=(str(int(day)-1),day) if filename=="workout-source.yml" else (day,)
            runs=[]
            for index_day in days:
                iso=f"{index_day[:4]}-{index_day[4:6]}-{index_day[6:]}"
                attempt=[]
                try:runs.extend(index(index_day,filename,gh(f"actions/workflows/kyoto-20261128-29-{filename}/runs?created={iso}&per_page=100",attempt)))
                finally:recovery_trace.append({"scope":"run_index","date":iso,"attempts":attempt})
            if len({r["id"] for r in runs})!=len(runs):raise ValueError("duplicate_run_id")
            for r in runs:
                if r["status"]!="completed":continue
                try:
                    attempt=[]
                    try:d=gh(f"actions/runs/{r['id']}/artifacts?per_page=100",attempt)
                    finally:recovery_trace.append({"scope":"artifact_index","run_id":r["id"],"attempts":attempt})
                    if d["total_count"]!=len(d["artifacts"]):raise ValueError("artifact_index_incomplete")
                    # Preview and next-day workout artifacts must not be
                    # mistaken for the requested meeting or missing originals.
                    if filename=="workout-source.yml":
                        other=[x for x in d["artifacts"] if re.fullmatch(r"kyoto-workout-"+str(r["id"])+r"-20[0-9]{6}",x.get("name","")) and x["name"]!=f"kyoto-workout-{r['id']}-{day}"]
                        if other and not any(x.get("name")==f"kyoto-workout-{r['id']}-{day}" for x in d["artifacts"]):
                            r["other_target_day_artifact_ids"]=[x["id"] for x in other];continue
                    # Include exact artifact IDs even for expired or missing originals.
                    r["artifacts"]={}
                    matches={lane:[x for x in d["artifacts"] if x.get("name")==f"kyoto-{lane}-{r['id']}-{day}"] for lane in lanes}
                    jobs=None
                    if any(not a for a in matches.values()):
                        attempt=[]
                        try:jobs=gh(f"actions/runs/{r['id']}/jobs?per_page=100",attempt)
                        except Exception as exc:r["job_index_error"]=type(exc).__name__
                        finally:recovery_trace.append({"scope":"job_index","run_id":r["id"],"attempts":attempt})
                    for lane,a in matches.items():
                        r["artifacts"][lane]=classify_artifact(filename,lane,r["id"],a,jobs)
                except Exception as exc:r["artifact_index_error"]=type(exc).__name__
            reports[filename]={"index_complete":True,"runs":runs,"native_slots":slots(day,filename,runs,now),"external_dispatch_slots":external_slots(day,filename,runs,now),"metadata_recovery":recovery_trace}
        except Exception as exc:
            reports[filename]={"index_complete":False,"error_class":type(exc).__name__,"runs":[],"native_slots":[],"external_dispatch_slots":[],"metadata_recovery":recovery_trace}
            errors.append(filename)
    return reports,errors
def review(day,now,out):
    metadata,errors=collect_metadata(day,now)
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    (out/"metadata_checkpoint.json").write_bytes(canon({"day":day,"workflows":metadata,"errors":errors})+b"\n")
    report={"schema":"kyoto_weekend_closure_review.v1","day":day,"observed_utc":now.isoformat(),"workflow_index_errors":errors,"workflows":metadata,
       "new_source_http_requests":0,"full_acquisition_certified":False,"all_risks_closed":False}
    sp_attempted=False
    sp_allowed=[]
    # Reuse production's authenticated PC/auxiliary/market/result replay, not
    # unverified handoff totals. Same-day correction chain is reopened.
    try:
        from diagnostics.kyoto_impl30_postrace_runtime import recover_inputs
        from diagnostics.kyoto_impl30_postrace_replay import replay_history,prior_archives
        from diagnostics.kyoto_impl30_day_coverage import include_postrace
        key=os.environ["ARCHIVE_KEY"]
        roster,starts,_,proof=recover_inputs(day,REPO,key,include_coverage=True,allow_missing_seed=True,**({"return_coverage_slots":True} if day=="20261129" else {}))
        report["roster_verified_races"]=[n for n in range(1,13) if roster.get(n) and starts.get(n)]
        report["input_replay_errors"]={k:proof[k] for k in ("rejected_runs","conflicting_races","day_source_coverage_error") if k in proof}
        coverage=proof["day_source_coverage"]
        if day=="20261129":
            # Reopen each SP archive once with exact authenticated PC context.
            # Failure of supplemental replay must not erase existing PC/aux data.
            try:
                from diagnostics.kyoto_impl39_sp_market_union import context
                from diagnostics.kyoto_impl30_day_coverage import combine
                verified_slots=proof["authenticated_coverage_slots"]
                sp_attempted=True
                sp=review_sp(day,metadata["two-source-production-observer.yml"],sp_context=context(verified_slots,day))
                report["independent_sp_source_coverage"]=sp
                market_slots=sp["verified_market_slots"]
                merged=combine(day,verified_slots,sp_slots=market_slots)
                for k in ("authenticated_pc_slots","authenticated_auxiliary_slots","auxiliary_errors","slot_errors"):
                    merged[k]=coverage[k]
                coverage=merged
                sp_allowed=[int(s["run_id"]) for s in market_slots]
                report["sp_market_replay"]={"authenticated_run_ids":sp_allowed,"source_http_requests":0}
            except Exception as exc:report["independent_sp_market_replay_error"]=type(exc).__name__
        # Existing replay_history includes the current run. For day close
        # use the latest actual postrace archive as current (not this workflow).
        post=[r for r in metadata["postrace-evidence.yml"]["runs"] if r.get("artifacts",{}).get("postrace",{}).get("state")=="PRESENT"]
        if post:
            rid=max(post,key=lambda r:r["id"])["id"]
            from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
            from diagnostics.kyoto_impl25_c12_all_runs_handoff import _download
            with tempfile.TemporaryDirectory(prefix="kyoto_closure_") as tmp:
                root=Path(tmp);cipher=root/"cipher";cipher.mkdir()
                _download(rid,f"kyoto-postrace-{rid}-{day}",cipher,REPO)
                raw=root/"raw";decrypt_evidence(cipher,raw,key_hex=key,repo=REPO,run_id=str(rid))
                history=replay_history(raw,day=day,repo=REPO,key=key,current_run=str(rid),roster=roster,starts=starts)
                coverage=include_postrace(coverage,history,roster=roster,starts=starts)
                report["postrace_history_index_complete"]=history["prior_artifact_index_complete"]
        allowed={r["id"] for filename,lane in (("two-source-production-observer.yml","pc"),("auxiliary-refresh.yml","auxiliary"),("postrace-evidence.yml","postrace")) for r in metadata[filename]["runs"] if r.get("artifacts",{}).get(lane,{}).get("state")=="PRESENT"}
        # Workout replay is independently authenticated, linked to the same
        # roster, and never allowed to erase other source evidence on failure.
        wr=None;workout_allowed=[]
        try:
            workout_allowed=[r["id"] for r in metadata["workout-source.yml"]["runs"] if r.get("artifacts",{}).get("workout",{}).get("state")=="PRESENT"]
            wr=review_workouts(day,metadata,coverage,roster,starts,key,os.environ["KYOTO_WORKOUT_READER"])
            report["workout_day_replay"]=wr
        except Exception as exc:report["workout_day_replay_error"]=type(exc).__name__
        cr=None
        try:
            cr=review_cancellations(day,metadata,coverage,key)
            report["cancellation_review"]=cr
        except Exception as exc:report["cancellation_review_error"]=type(exc).__name__
        report["coverage"]=coverage_gaps(day,coverage,allowed,wr,workout_allowed,cr,allowed_sp_market_run_ids=sp_allowed)
        try:
            report["independent_cushion_day_replay"]=review_cushion(day,metadata["cushion-source.yml"],coverage,key,os.environ["KYOTO_CUSHION_READER"])
        except Exception as exc:report["independent_cushion_day_replay_error"]=type(exc).__name__
    except Exception as exc:
        report["coverage_replay_error"]=type(exc).__name__
        report["coverage"]={"counts":{},"races":[{"race":n,"state":"NOT_EVALUATED","missing":[{"family":"day_coverage_unavailable"}],"unknown_horse_families":list(HORSE)} for n in range(1,13)],"all_reviewed_cells_present":False,"full_acquisition_certified":False}
    if not sp_attempted:
        try:report["independent_sp_source_coverage"]=review_sp(day,metadata["two-source-production-observer.yml"])
        except Exception as exc:report["independent_sp_source_coverage_error"]=type(exc).__name__
    try:
        register=Path(os.environ.get("KYOTO_FIXED_RISK_REGISTER","docs/diagnostics/KYOTO_REVERSE_FMEA_GAP_REGISTER_20261116.json"))
        report["fixed_risks"]=worklist(report,register.read_bytes())
        (out/"fixed_risk_worklist.json").write_bytes(canon(report["fixed_risks"])+b"\n")
    except Exception as exc:report["fixed_risk_worklist_error"]=type(exc).__name__
    report["release_state"]="REPAIR_REQUIRED_OR_INDEPENDENT_CERTIFICATION_PENDING"
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    raw=canon(report);(out/"review.json").write_bytes(raw+b"\n")
    summary=[f"<!-- kyoto-day-review:{day}:{digest(raw)} -->",f"## {day} 全工程・実データ独立点検",f"Evidence SHA256: {digest(raw)}","取得成否と原因閉鎖を区別。元の取得器には変更を加えない。"]
    for name,v in metadata.items():
        missing=[s for s in v["native_slots"] if s["state"] not in ("NOT_DUE","NATIVE_RUN_COMPLETED")]
        gaps=[(r["id"],k,a["state"]) for r in v["runs"] for k,a in r.get("artifacts",{}).items() if a["state"] not in ("PRESENT",SKIPPED)]
        skips=[(r["id"],k,a["job_id"]) for r in v["runs"] for k,a in r.get("artifacts",{}).items() if a["state"]==SKIPPED]
        summary.append(f"- {name}: index={v['index_complete']}, runs={len(v['runs'])}, historical native gaps (not external launch credit)={[(s['cron'],s['state']) for s in missing]}, external dispatch observations={[(s['due_utc'],s['state'],s['run_ids']) for s in v.get('external_dispatch_slots',[])]}, artifact gaps={gaps}, skipped producer jobs (reason unverified)={skips}")
    if "sp_market_replay" in report:summary.append("- SP市場原本の独立照合: "+str(report["sp_market_replay"]))
    if "independent_sp_market_replay_error" in report:summary.append("- SP市場照合未完: "+report["independent_sp_market_replay_error"])
    if "coverage_replay_error" in report:summary.append("- 原本再検証未完: "+report["coverage_replay_error"])
    if "workout_day_replay" in report:
        w=report["workout_day_replay"]
        summary.append(f"- 調教原本独立再解析: archives={len(w['examined_archive_run_ids'])}, authenticated_snapshots={w['authenticated_snapshots']}, records={sum(x['canonical_records'] for x in w['races'].values())}, index_complete={w['archive_index_complete']}; source evidence only, no model promotion.")
    elif "workout_day_replay_error" in report:summary.append("- 調教原本独立再解析未完: "+report["workout_day_replay_error"])
    if "independent_sp_source_coverage" in report:
        s=report["independent_sp_source_coverage"]
        summary.append(f"- SP独立構造証拠: audited_runs={s['audited_sp_runs']}, native={s['scheduled']['structural_roster_races']}/12, dispatch={s['manual']['structural_roster_races']}/12; separate ledger, no PC/prestart/market credit.")
    elif "independent_sp_source_coverage_error" in report:summary.append("- SP独立証拠未完: "+report["independent_sp_source_coverage_error"])
    if "independent_cushion_day_replay" in report:
        c=report["independent_cushion_day_replay"]
        summary.append(f"- クッション値独立原本: authenticated={len(c['authenticated_observations'])}, prestart={c['prestart_verified_races']}/12, replay_errors={len(c['replay_errors'])}; separate ledger, no full acquisition credit.")
    elif "independent_cushion_day_replay_error" in report:summary.append("- クッション値独立照合未完: "+report["independent_cushion_day_replay_error"])
    if "cancellation_review" in report:
        c=report["cancellation_review"]
        summary.append(f"- 取消馬独立照合: races={len(c['races'])}, replay_errors={len(c['errors'])}; 馬体重・増減のみ対象外（登録馬・他項目の分母は維持）。")
    if "coverage" in report:
        if report["coverage"].get("weight_not_applicable_counts"):summary.append("- 取消馬の対象外項目: "+str(report["coverage"]["weight_not_applicable_counts"]))
        for f,t in report["coverage"]["counts"].items():summary.append(f"- {f}: {t['verified']}/{t['expected']} (unknown denominator races={t['unknown_denominator_races']})")
        for r in report["coverage"]["races"]:
            families=sorted({m["family"] for m in r["missing"]})
            if families or r.get("unknown_horse_families"):summary.append(f"- R{r['race']:02d}: {r['state']}: {', '.join(families)}")
    else:summary.append("- 原本再検証未完: "+report.get("coverage_replay_error","UNKNOWN"))
    if "fixed_risks" in report:
        summary.append("- 固定25リスク: 25件の根拠・実行ID・必要証拠をfixed_risk_worklist.jsonへ収録。独立解消認定0/25。")
    else:summary.append("- 固定リスク照合失敗: "+report.get("fixed_risk_worklist_error","UNKNOWN"))
    for name,v in metadata.items():
        for a in v.get("metadata_recovery",[]):
            if any(x["state"]!="COMPLETE" for x in a["attempts"]):summary.append(f"- 自動メタデータ復旧: {name} {a}")
    summary.append("次回前に欠落原本・実行IDから原因再現、同根探索、隔離修正、反例試験、本番SHA照合を行う。独立証明のない欠落を完了扱いしない。")
    (out/"summary.md").write_text("\n".join(summary)+"\n",encoding="utf8")
    print("CLOSURE_REVIEW",json.dumps({"day":day,"index_errors":errors,"source_runs":sum(len(x["runs"]) for x in metadata.values()),"native_slots":sum(len(x["native_slots"]) for x in metadata.values()),"coverage_counts":report.get("coverage",{}).get("counts",{}),"coverage_replay_error":report.get("coverage_replay_error"),"fixed_risk_rows":len(report.get("fixed_risks",{}).get("rows",[])),"fixed_risk_worklist_error":report.get("fixed_risk_worklist_error"),"full_acquisition_certified":False},sort_keys=True))
def main():
    p=argparse.ArgumentParser();p.add_argument("--day",choices=DAYS,required=True);p.add_argument("--out",required=True);a=p.parse_args()
    if os.environ.get("GITHUB_REPOSITORY")!=REPO:raise ValueError("repo_identity")
    review(a.day,datetime.now(timezone.utc),a.out)
if __name__=="__main__":main()
