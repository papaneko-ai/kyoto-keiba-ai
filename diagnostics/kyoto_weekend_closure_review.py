"""Independent day-close evidence review, without source HTTP or code promotion.

Use existing authenticated source replays. Detect missing executions as well as
data gaps. Never convert a workflow success or receipt flag into data credit.
"""
import argparse,hashlib,json,os,re,subprocess,tempfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
if __package__:
    from .kyoto_repair_control import recover_collection
    from .kyoto_fixed_risk_worklist import worklist
else:
    from kyoto_repair_control import recover_collection
    from kyoto_fixed_risk_worklist import worklist

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
def proof_ok(value,cutoff,day,allowed,after=False):
    try:
        utc=stamp(value["utc"])
        return (after or value.get("state")=="SOURCE_VERIFIED") and is_sha(value["sha256"]) and is_sha(value["value_digest"]) and str(value.get("run_id")) in allowed and utc.strftime("%Y%m%d")==day and (utc>cutoff if after else utc<cutoff)
    except (TypeError,KeyError,ValueError,AttributeError):return False
def coverage_gaps(day,coverage,allowed_run_ids):
    """Compute missing cells from independently replayed aggregate, not totals."""
    if coverage.get("day")!=day or coverage.get("schema")!="kyoto_impl30_day_source_coverage.v1" or coverage.get("race_denominator")!=12 or set(coverage.get("races",{}))!=set(RACES):raise ValueError("coverage_identity_incomplete")
    allowed=set(map(str,allowed_run_ids))
    totals={f:{"expected":0,"verified":0,"unknown_denominator_races":0} for f in FAMILIES}
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
        for h in sorted(horses,key=int):
            for f in HORSE:
                v=horses[h].get(f,{})
                check(f,proof_ok(v,cutoff,day,allowed),h,v)
        for section,keys in (("track",TRACK),("supplementary_track_observations",EXTRA)):
            for f in keys:
                v=row.get(section,{}).get(f,{})
                check(f,proof_ok(v,cutoff,day,allowed),proof=v)
        a,b=(row.get("markets",{}).get(f,{}) for f in MARKETS)
        for f,v in zip(MARKETS,(a,b)):check(f,proof_ok(v,cutoff,day,allowed),proof=v)
        cancelled=a.get("cancelled_horses")
        valid_cancel=isinstance(cancelled,list) and all(type(n) is int and str(n) in horses for n in cancelled) and len(set(cancelled))==len(cancelled)
        check("paired_market_same_slot",row.get("paired_same_slot") is True and proof_ok(a,cutoff,day,allowed) and proof_ok(b,cutoff,day,allowed) and a.get("run_id")==b.get("run_id") and valid_cancel and cancelled==b.get("cancelled_horses"))
        p=row.get("postrace",{})
        for f,k in (("official_result","result"),("official_payout","payout")):
            v=p.get(k,{})
            v={**v,"run_id":p.get("run_id")} if isinstance(v,dict) else {}
            check(f,p.get("state")=="DUAL_PAGE_FINAL_SOURCE_RECONCILED" and coverage.get("postrace_history_index_complete") is True and proof_ok(v,cutoff,day,allowed,True),proof=v)
        detail.append({"race":int(race),"state":"GAPS" if missing else "ALL_REVIEWED_CELLS_PRESENT","registered_horses":len(horses),"missing":missing,"bound_evidence":bound,"postrace_publication_only":p.get("state")=="DUAL_PAGE_OFFICIAL_PUBLISHED_PAYOUT"})
    return {"counts":totals,"races":detail,"all_reviewed_cells_present":all(t["expected"]==t["verified"] and not t["unknown_denominator_races"] for t in totals.values()),"full_acquisition_certified":False}
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
                    for lane in lanes:
                        name=f"kyoto-{lane}-{r['id']}-{day}"
                        a=[x for x in d["artifacts"] if x.get("name")==name]
                        r["artifacts"][lane]={"state":"PRESENT" if len(a)==1 and a[0].get("expired") is False else "MISSING_EXPIRED_OR_AMBIGUOUS","ids":[x["id"] for x in a]}
                except Exception as exc:r["artifact_index_error"]=type(exc).__name__
            reports[filename]={"index_complete":True,"runs":runs,"native_slots":slots(day,filename,runs,now),"metadata_recovery":recovery_trace}
        except Exception as exc:
            reports[filename]={"index_complete":False,"error_class":type(exc).__name__,"runs":[],"native_slots":[],"metadata_recovery":recovery_trace}
            errors.append(filename)
    return reports,errors
def review(day,now,out):
    metadata,errors=collect_metadata(day,now)
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    (out/"metadata_checkpoint.json").write_bytes(canon({"day":day,"workflows":metadata,"errors":errors})+b"\n")
    report={"schema":"kyoto_weekend_closure_review.v1","day":day,"observed_utc":now.isoformat(),"workflow_index_errors":errors,"workflows":metadata,
       "new_source_http_requests":0,"full_acquisition_certified":False,"all_risks_closed":False}
    # Reuse production's authenticated PC/auxiliary/market/result replay, not
    # unverified handoff totals. Same-day correction chain is reopened.
    try:
        from diagnostics.kyoto_impl30_postrace_runtime import recover_inputs
        from diagnostics.kyoto_impl30_postrace_replay import replay_history,prior_archives
        from diagnostics.kyoto_impl30_day_coverage import include_postrace
        key=os.environ["ARCHIVE_KEY"]
        roster,starts,_,proof=recover_inputs(day,REPO,key,include_coverage=True,allow_missing_seed=True)
        report["roster_verified_races"]=[n for n in range(1,13) if roster.get(n) and starts.get(n)]
        report["input_replay_errors"]={k:proof[k] for k in ("rejected_runs","conflicting_races","day_source_coverage_error") if k in proof}
        coverage=proof["day_source_coverage"]
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
        report["coverage"]=coverage_gaps(day,coverage,allowed)
    except Exception as exc:
        report["coverage_replay_error"]=type(exc).__name__
        report["coverage"]={"counts":{},"races":[{"race":n,"state":"NOT_EVALUATED","missing":[{"family":"day_coverage_unavailable"}],"unknown_horse_families":list(HORSE)} for n in range(1,13)],"all_reviewed_cells_present":False,"full_acquisition_certified":False}
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
        gaps=[(r["id"],k) for r in v["runs"] for k,a in r.get("artifacts",{}).items() if a["state"]!="PRESENT"]
        summary.append(f"- {name}: index={v['index_complete']}, runs={len(v['runs'])}, native gaps={[(s['cron'],s['state']) for s in missing]}, artifact gaps={gaps}")
    if "coverage_replay_error" in report:summary.append("- 原本再検証未完: "+report["coverage_replay_error"])
    if "coverage" in report:
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
