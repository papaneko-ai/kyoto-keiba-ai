"""A3: compare authenticated Saturday/Sunday source coverage, not betting performance.
No JRA HTTP, no auto-promotion, no change to acquisition. Evidence gaps are
UNKNOWN, never counted as measured zero. Day-over-day changes are observational.
"""
import argparse,json,os,re,subprocess,tempfile,time
from pathlib import Path
from datetime import datetime,timezone
from fractions import Fraction
from diagnostics.kyoto_impl30_nextday_adaptation import POLICY,WORKFLOW,NAME,accept

SAT="20261128"; SUN="20261129"

def receipt(raw,channel):
    if not isinstance(raw,dict): raise ValueError("invalid_policy_receipt")
    mode=raw.get("selected_policy"); reason=raw.get("reason")
    if (raw.get("schema")!="kyoto_nextday_applied_policy.v1" or raw.get("day")!=SUN
        or channel not in ("PC","SP") or raw.get("channel")!=channel or mode not in POLICY
        or not isinstance(reason,str) or not re.fullmatch(r"[A-Za-z0-9_]{1,200}",reason)
        or (raw.get("pc_market_seconds"),raw.get("sp_seconds"))!=POLICY[mode]
        or raw.get("source_coverage_proved") is not False or raw.get("improvement_proved") is not False):
        raise ValueError("invalid_policy_receipt")
    stamp=datetime.fromisoformat(raw["observed_at_utc"].replace("Z","+00:00"))
    if stamp.utcoffset()!=timezone.utc.utcoffset(None) or stamp.strftime("%Y%m%d")!=SUN:
        raise ValueError("invalid_policy_timestamp")
    return {k:raw[k] for k in ("schema","day","channel","selected_policy","reason","pc_market_seconds","sp_seconds","observed_at_utc","source_coverage_proved","improvement_proved")}

def _counts(report,day):
    c=report.get("day_source_coverage",{})
    from diagnostics.kyoto_impl39_dispatch_slots import bound_ids
    dispatch=bound_ids(report.get('external_dispatch_slot_ledger',{}).get('morning'),day,both=False)
    if (report.get("day")!=day or (report.get("all_run_metadata_screened") is not True and not dispatch)
        or report.get("github_run_listing_complete") is not True or c.get("day")!=day
        or c.get("schema")!="kyoto_impl30_day_source_coverage.v1" or c.get("race_denominator")!=12
        or type(c.get("authenticated_pc_slots")) is not int or c["authenticated_pc_slots"]<1
        or (not dispatch and c.get("unassessed_pc_slots",0)!=0)):
        raise ValueError("coverage_incomplete")
    # Recompute denominators and numerators from the independently extracted
    # source proofs. A missing roster is not a known horse denominator.
    races=c.get("races",{})
    if set(races)!=set(map(str,range(1,13))):raise ValueError("race_denominator")
    n=dict(racecards=0,paired_same_slot_races=0,registered_horses_known=0,profile=0,prior_form=0)
    for r in races.values():
        if r.get("state")!="ROSTER_VERIFIED" or r.get("racecard",{}).get("state")!="SOURCE_VERIFIED":continue
        n["racecards"]+=1
        n["paired_same_slot_races"]+=int(r.get("paired_same_slot") is True)
        for horse in r["horses"].values():
            n["registered_horses_known"]+=1
            for field in ("profile","prior_form"):
                n[field]+=int(horse.get(field,{}).get("state")=="SOURCE_VERIFIED")
    totals=c.get("totals",{})
    if any(type(totals.get(k)) is not int or totals[k]!=v for k,v in n.items()):raise ValueError("count_mismatch")
    return n

def evaluate(saturday,sunday,mode,source_run_id):
    out={"schema":"kyoto_impl31_improvement_evaluation.v1","source_day":SAT,"target_day":SUN,
         "source_run_id":str(source_run_id),"planned_policy":mode,"status":"INSUFFICIENT_EVIDENCE",
         "causal_effect_proved":False,"automatic_code_promotion_authorized":False,"metrics":{}}
    if mode not in POLICY:return out
    applied=sunday.get("authenticated_applied_policies",[])
    # Both source lanes must have authenticated records of the exact signed
    # policy. Mixed/fallback policies cannot be attributed to that strategy.
    try:
        from diagnostics.kyoto_impl39_dispatch_slots import bound_ids
        ledger=sunday.get("external_dispatch_slot_ledger",{}).get("morning")
        dispatch=bound_ids(ledger,SUN,both=True)
        event="workflow_dispatch" if ledger is not None else "schedule"
        if event=="workflow_dispatch" and len(dispatch)!=4:return out
        checked=[]
        seen=set()
        for item in applied:
            if item.get("event")!=event:continue
            if event=="workflow_dispatch" and item.get("run_id") not in dispatch:continue
            row=receipt(item["policy"],item["channel"])
            rid=item["run_id"]
            if type(rid) is not int or rid<=0 or (rid,item["channel"]) in seen:raise ValueError("duplicate_identity")
            seen.add((rid,item["channel"]))
            checked.append((rid,item["channel"],row))
        scheduled=sunday.get("scheduled_runs",[])
        expected=({(rid,lane) for rid in dispatch for lane in ("PC","SP")} if event=="workflow_dispatch" else {(r["run"]["id"],lane) for r in scheduled for lane in ("PC","SP")})
        if len(expected)!=8 or seen!=expected:return out
        valid_reasons={"AUTHENTICATED_SATURDAY_HANDOFF_"+str(source_run_id),"AUTHENTICATED_SATURDAY_DISPATCH_HANDOFF_"+str(source_run_id)}
        if any(row["selected_policy"]!=mode or row["reason"] not in valid_reasons for _,_,row in checked) or len({row["reason"] for _,_,row in checked})!=1:
            out["status"]="MIXED_OR_UNBOUND_POLICY";return out
        out["evaluated_launch_event"]=event
        before=_counts(saturday,SAT);after=_counts(sunday,SUN)
        for field in ("racecards","paired_same_slot_races","profile","prior_form"):
            if field in ("profile","prior_form"):
                if before["racecards"]!=12 or after["racecards"]!=12:continue
                d1=before["registered_horses_known"];d2=after["registered_horses_known"]
            else:d1=d2=12
            if not d1 or not d2:continue
            b=Fraction(before[field],d1);a=Fraction(after[field],d2)
            out["metrics"][field]={"before":[before[field],d1],"after":[after[field],d2],
              "direction":"IMPROVED" if a>b else "REGRESSED" if a<b else "UNCHANGED"}
        target={"MARKET_OR_ROSTER_RECOVERY":("racecards","paired_same_slot_races"),"PROFILE_RECOVERY":("profile","prior_form"),"BASELINE":()}[mode]
        if not target:
            out["status"]="BASELINE_NO_ADAPTATION";return out
        if any(k not in out["metrics"] for k in target):return out
        directions=[x["direction"] for x in out["metrics"].values()]
        if "REGRESSED" in directions:out["status"]="OBSERVED_REGRESSION_OR_TRADEOFF"
        elif any(out["metrics"][k]["direction"]=="IMPROVED" for k in target):out["status"]="OBSERVED_TARGET_IMPROVEMENT"
        else:out["status"]="NO_OBSERVED_TARGET_IMPROVEMENT"
        out["next_review"]="RETAIN_BASELINE_FOR_FUTURE_REVIEW" if out["status"]!="OBSERVED_TARGET_IMPROVEMENT" else "CANDIDATE_FOR_REVIEW_ONLY"
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError):pass
    return out

def load_saturday(repo,collector,key,source_id=None):
    end=time.monotonic()+35
    def timeout(cap):
        left=end-time.monotonic()
        if left<=0:raise TimeoutError("evaluation_deadline")
        return min(left,cap)
    def api(endpoint):
        return json.loads(subprocess.check_output(["gh","api",endpoint],text=True,stderr=subprocess.DEVNULL,timeout=timeout(8)))
    index=api(f"repos/{repo}/actions/workflows/{WORKFLOW}/runs?created=2026-11-28&per_page=100")
    runs=index["workflow_runs"]
    if index["total_count"]!=len(runs) or len(runs)>100:raise ValueError("incomplete_index")
    from diagnostics.kyoto_impl25_c12_all_runs_handoff import run_name_matches
    eligible=[r for r in runs if run_name_matches(r,NAME,WORKFLOW,SAT) and (r.get("event")=="schedule" or (r.get("event")=="workflow_dispatch" and r.get("head_branch")=="main")) and r.get("status")=="completed" and r.get("conclusion")=="success" and r.get("created_at","")[:10]=="2026-11-28" and r.get("head_repository",{}).get("full_name")==repo and r.get("path","").split("@",1)[0]==".github/workflows/"+WORKFLOW]
    if source_id is not None:eligible=[r for r in eligible if r["id"]==source_id]
    elif len([r for r in eligible if r.get("event")=="schedule"])==1:eligible=[r for r in eligible if r.get("event")=="schedule"]
    if len(eligible)!=1:raise ValueError("ambiguous_saturday")
    rid=eligible[0]["id"]
    if type(rid) is not int or rid<=0:raise ValueError("run_identity")
    name=f"kyoto-handoff-{rid}-{SAT}"
    arts=api(f"repos/{repo}/actions/runs/{rid}/artifacts?per_page=100")
    if arts["total_count"]!=len(arts["artifacts"]) or len([a for a in arts["artifacts"] if a.get("name")==name and a.get("expired") is False])!=1:raise ValueError("artifact_identity")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["gh","run","download",str(rid),"--repo",repo,"--name",name,"--dir",tmp],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=timeout(15))
        def read(name):
            p=Path(tmp)/name
            if p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=5_000_000:raise ValueError("artifact_file")
            return json.loads(p.read_text())
        report=read("report.json");doc=read("nextday_policy.json")
        from diagnostics.kyoto_impl30_nextday_adaptation import SATURDAY_HANDOFF_COLLECTOR,SATURDAY_HANDOFF_UPDATED_COLLECTOR,NOV28_INCIDENT_REPO,OBSERVER,OBSERVER_NAME
        signer=doc.get("body",{}).get("collector_sha")
        expected_signer=signer if repo==NOV28_INCIDENT_REPO and signer in (SATURDAY_HANDOFF_COLLECTOR,SATURDAY_HANDOFF_UPDATED_COLLECTOR) else collector
        mode=accept(doc,report,repo=repo,run_id=rid,collector_sha=expected_signer,key=key)
        # Historical Saturday signer is immutable. Extend its authenticated
        # PC observations only with a fresh exact workflow index, after HMAC.
        if eligible[0].get("event")=="workflow_dispatch" and "external_dispatch_slot_ledger" not in report:
            try:
                from diagnostics.kyoto_impl39_dispatch_slots import observe
                idx=api(f"repos/{repo}/actions/workflows/{OBSERVER}/runs?created=2026-11-28&per_page=100")
                rows=idx["workflow_runs"]
                complete=idx["total_count"]==len(rows) and len(rows)<=100
                valid=[r for r in rows if run_name_matches(r,OBSERVER_NAME,OBSERVER,SAT) and r.get("head_repository",{}).get("full_name")==repo and r.get("path","").split("@",1)[0]==".github/workflows/"+OBSERVER and r.get("created_at","")[:10]=="2026-11-28"]
                manual=report.get("manual_source_assessment",[])
                if len({r["run_id"] for r in manual})!=len(manual):raise ValueError("duplicate_manual")
                report["external_dispatch_slot_ledger"]={"morning":observe(SAT,[{"run":r} for r in valid],complete=complete and len(valid)==len(rows),legacy_pc={r["run_id"]:r.get("authenticated_pc_slot") for r in manual})}
            except Exception:pass
        return report,mode,rid

def main():
    p=argparse.ArgumentParser();p.add_argument("--report",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    try:
        sunday=json.loads(a.report.read_text())
        collector=subprocess.check_output(["git","rev-parse","HEAD"],text=True,timeout=3).strip()
        reasons={x.get("policy",{}).get("reason","") for x in sunday.get("authenticated_applied_policies",[]) if x.get("event") in ("schedule","workflow_dispatch")}
        candidates={int(m.group(1)) for x in reasons if isinstance(x,str) and (m:=re.fullmatch(r"AUTHENTICATED_SATURDAY_(?:DISPATCH_)?HANDOFF_(\d+)",x))}
        source_id=next(iter(candidates)) if len(candidates)==1 else None
        sat,mode,rid=load_saturday(os.environ["GITHUB_REPOSITORY"],collector,os.environ["ARCHIVE_KEY"],source_id)
        out=evaluate(sat,sunday,mode,rid)
    except Exception as exc:
        out={"schema":"kyoto_impl31_improvement_evaluation.v1","status":"INSUFFICIENT_EVIDENCE","error_class":type(exc).__name__,"causal_effect_proved":False,"automatic_code_promotion_authorized":False}
    with a.out.open("x",encoding="utf8") as f:json.dump(out,f,sort_keys=True)
    print("A3_EVALUATION="+out["status"])
if __name__=="__main__":main()
