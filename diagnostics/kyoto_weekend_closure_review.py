"""Independent day-close evidence review, without source HTTP or code promotion.

Use existing authenticated source replays. Detect missing executions as well as
data gaps. Never convert a workflow success or receipt flag into data credit.
"""
import argparse,hashlib,json,os,re,subprocess,tempfile
from datetime import datetime,timezone,timedelta
from pathlib import Path

REPO="papaneko-ai/kyoto-keiba-ai"
DAYS=("20261128","20261129")
PREFIX=".github/workflows/kyoto-20261128-29-"
SCHEDULE={
 "two-source-production-observer.yml":lambda d:("15 0","15 1","5 2","50 2") if d=="20261128" else ("15 0","15 1","10 2","55 2"),
 "auxiliary-refresh.yml":lambda d:("30 3","30 4","30 5","30 6"),
 "postrace-evidence.yml":lambda d:("0 10","0 13"),
 "result-handoff.yml":lambda d:("0 12",)}
LANES={"two-source-production-observer.yml":("pc","sp"),"auxiliary-refresh.yml":("auxiliary",),
 "postrace-evidence.yml":("postrace",),"result-handoff.yml":("handoff","cushion-day"),
 "workout-source.yml":("workout",),"cushion-source.yml":("cushion",)}
FAMILIES=("racecard","profile","prior_form","body_weight_kg","body_weight_change_kg","workout",
 "weather","turf_going","dirt_going","quinella","bracket_quinella","paired_market_same_slot","official_result","official_payout")
HORSE=FAMILIES[1:6]
TRACK=FAMILIES[6:9]
MARKETS=FAMILIES[9:11]
RACES=tuple(str(n) for n in range(1,13))
def canon(obj):return json.dumps(obj,sort_keys=True,ensure_ascii=True,separators=(",",":"),allow_nan=False).encode()
def digest(raw):return hashlib.sha256(raw).hexdigest()
def stamp(x):
    t=datetime.fromisoformat(x.replace("Z","+00:00"))
    if t.utcoffset()!=timedelta(0):raise ValueError("not_utc")
    return t
def is_sha(v):return isinstance(v,str) and re.fullmatch(r"[a-f0-9]{64}",v) is not None
def gh(path):
    return json.loads(subprocess.check_output(["gh","api",f"repos/{REPO}/{path}"],text=True,stderr=subprocess.DEVNULL,timeout=25))
def index(day,filename,doc):
    if day not in DAYS or filename not in LANES:raise ValueError("invalid_index_scope")
    rows=doc["workflow_runs"]
    if type(doc["total_count"]) is not int or doc["total_count"]!=len(rows) or len(rows)>100:raise ValueError("incomplete_run_index")
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
        title=f"kyoto-native:{cron} {day[-2:]} 11 *"
        exact=[r for r in runs if r["event"]=="schedule" and r["native_title"]==title]
        # Dispatches cannot be guessed to correspond to an exact slot.
        state="NOT_DUE" if now<due else "NATIVE_SLOT_NOT_OBSERVED" if not exact else "NATIVE_SLOT_AMBIGUOUS" if len(exact)!=1 else "NATIVE_RUN_UNFINISHED" if exact[0]["status"]!="completed" else "NATIVE_RUN_COMPLETED"
        out.append({"cron":title[13:],"due_utc":due.isoformat(),"state":state,"run_ids":[r["id"] for r in exact],
                    "late_seconds":max(0,int((stamp(exact[0]["created_at"])-due).total_seconds())) if len(exact)==1 else None})
    return out
def proof_ok(value,cutoff,day,after=False):
    try:
        utc=stamp(value["utc"])
        return value.get("state") in (None,"SOURCE_VERIFIED") and is_sha(value["sha256"]) and is_sha(value["value_digest"]) and str(value.get("run_id","1")).isdigit() and utc.strftime("%Y%m%d")==day and (utc>cutoff if after else utc<cutoff)
    except (TypeError,KeyError,ValueError,AttributeError):return False
def coverage_gaps(day,coverage):
    """Compute missing cells from independently replayed aggregate, not totals."""
    if coverage.get("day")!=day or coverage.get("schema")!="kyoto_impl30_day_source_coverage.v1" or set(coverage.get("races",{}))!=set(RACES):raise ValueError("coverage_identity_incomplete")
    totals={f:{"expected":0,"verified":0,"unknown_denominator_races":0} for f in FAMILIES}
    detail=[]
    for race in RACES:
        row=coverage["races"][race];missing=[]
        def check(f,good,horse=None):
            t=totals[f];t["expected"]+=1;t["verified"]+=int(bool(good))
            if not good:missing.append({"family":f,**({"horse":horse} if horse else {})})
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
        check("racecard",proof_ok(row.get("racecard",{}),cutoff,day))
        for h in sorted(horses,key=int):
            for f in HORSE:check(f,proof_ok(horses[h].get(f,{}),cutoff,day),h)
        for f in TRACK:check(f,proof_ok(row.get("track",{}).get(f,{}),cutoff,day))
        a,b=(row.get("markets",{}).get(f,{}) for f in MARKETS)
        for f,v in zip(MARKETS,(a,b)):check(f,proof_ok(v,cutoff,day))
        check("paired_market_same_slot",row.get("paired_same_slot") is True and proof_ok(a,cutoff,day) and proof_ok(b,cutoff,day) and bool(a.get("run_id")) and a.get("run_id")==b.get("run_id") and a.get("cancelled_horses")==b.get("cancelled_horses"))
        p=row.get("postrace",{})
        for f,k in (("official_result","result"),("official_payout","payout")):
            check(f,p.get("state")=="DUAL_PAGE_FINAL_SOURCE_RECONCILED" and proof_ok(p.get(k,{}),cutoff,day,True))
        detail.append({"race":int(race),"state":"GAPS" if missing else "ALL_REVIEWED_CELLS_PRESENT","missing":missing})
    return {"counts":totals,"races":detail,"all_reviewed_cells_present":all(t["expected"]==t["verified"] and not t["unknown_denominator_races"] for t in totals.values()),"full_acquisition_certified":False}
def collect_metadata(day,now):
    date=f"{day[:4]}-{day[4:6]}-{day[6:]}"
    reports={};errors=[]
    for filename,lanes in LANES.items():
        try:
            runs=index(day,filename,gh(f"actions/workflows/kyoto-20261128-29-{filename}/runs?created={date}&per_page=100"))
            for r in runs:
                if r["status"]!="completed":continue
                try:
                    d=gh(f"actions/runs/{r['id']}/artifacts?per_page=100")
                    if d["total_count"]!=len(d["artifacts"]):raise ValueError("artifact_index_incomplete")
                    # Include exact artifact IDs even for expired or missing originals.
                    r["artifacts"]={}
                    for lane in lanes:
                        name=f"kyoto-{lane}-{r['id']}-{day}"
                        a=[x for x in d["artifacts"] if x.get("name")==name]
                        r["artifacts"][lane]={"state":"PRESENT" if len(a)==1 and a[0].get("expired") is False else "MISSING_EXPIRED_OR_AMBIGUOUS","ids":[x["id"] for x in a]}
                except Exception as exc:r["artifact_index_error"]=type(exc).__name__
            reports[filename]={"index_complete":True,"runs":runs,"native_slots":slots(day,filename,runs,now)}
        except Exception as exc:
            reports[filename]={"index_complete":False,"error_class":type(exc).__name__,"runs":[],"native_slots":[]}
            errors.append(filename)
    return reports,errors
def review(day,now,out):
    metadata,errors=collect_metadata(day,now)
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
        report["coverage"]=coverage_gaps(day,coverage)
    except Exception as exc:
        report["coverage_replay_error"]=type(exc).__name__
    report["release_state"]="REPAIR_REQUIRED_OR_INDEPENDENT_CERTIFICATION_PENDING"
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    raw=canon(report);(out/"review.json").write_bytes(raw+b"\n")
    summary=[f"<!-- kyoto-day-review:{day}:{digest(raw)} -->",f"## {day} 全工程・実データ独立点検",f"Evidence SHA256: {digest(raw)}","取得成否と原因閉鎖を区別。元の取得器には変更を加えない。"]
    for name,v in metadata.items():
        missing=[s for s in v["native_slots"] if s["state"] not in ("NOT_DUE","NATIVE_RUN_COMPLETED")]
        gaps=[(r["id"],k) for r in v["runs"] for k,a in r.get("artifacts",{}).items() if a["state"]!="PRESENT"]
        summary.append(f"- {name}: index={v['index_complete']}, runs={len(v['runs'])}, native gaps={[(s['cron'],s['state']) for s in missing]}, artifact gaps={gaps}")
    if "coverage" in report:
        for f,t in report["coverage"]["counts"].items():summary.append(f"- {f}: {t['verified']}/{t['expected']} (unknown denominator races={t['unknown_denominator_races']})")
        for r in report["coverage"]["races"]:
            families=sorted({m["family"] for m in r["missing"]})
            if families or r.get("unknown_horse_families"):summary.append(f"- R{r['race']:02d}: {r['state']}: {', '.join(families)}")
    else:summary.append("- 原本再検証未完: "+report.get("coverage_replay_error","UNKNOWN"))
    summary.append("次回前に欠落原本・実行IDから原因再現、同根探索、隔離修正、反例試験、本番SHA照合を行う。独立証明のない欠落を完了扱いしない。")
    (out/"summary.md").write_text("\n".join(summary)+"\n",encoding="utf8")
def main():
    p=argparse.ArgumentParser();p.add_argument("--day",choices=DAYS,required=True);p.add_argument("--out",required=True);a=p.parse_args()
    if os.environ.get("GITHUB_REPOSITORY")!=REPO:raise ValueError("repo_identity")
    review(a.day,datetime.now(timezone.utc),a.out)
if __name__=="__main__":main()
