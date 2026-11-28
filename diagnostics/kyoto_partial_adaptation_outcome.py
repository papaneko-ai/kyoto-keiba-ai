"""Independent partial outcome review. Never changes acquisition or grants causal credit.
Uses the exact signed Saturday policy and authenticated Sunday handoff, even
when one lane or slot failed. No source HTTP or automatic code promotion.
"""
import argparse,hashlib,json,os,re,subprocess,sys,tempfile,time
from datetime import datetime,timezone,timedelta
from pathlib import Path

REPO="papaneko-ai/kyoto-keiba-ai"
READER="fed005c89fcfa940c479538ee983f211598a6640"
SOURCE_RUN=46142732553
SAT="20261128";SUN="20261129"
MODE="MARKET_OR_ROSTER_RECOVERY"
PATH=".github/workflows/kyoto-20261128-29-result-handoff.yml"
TIMES=("00:17","01:17","02:12","02:57")
POLICY={"BASELINE":(720,240),"MARKET_OR_ROSTER_RECOVERY":(720,360),"PROFILE_RECOVERY":(600,360)}
HEX=re.compile(r"[a-f0-9]{64}")
def canon(x):return json.dumps(x,ensure_ascii=True,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def digest(x):return hashlib.sha256(x).hexdigest()
def utc(x):
    t=datetime.fromisoformat(x.replace("Z","+00:00"))
    if t.utcoffset()!=timedelta(0):raise ValueError("not_utc")
    return t
def prestart(proof,start,day):
    try:return (proof.get("state")=="SOURCE_VERIFIED" and HEX.fullmatch(proof["sha256"]) is not None
        and str(proof["run_id"]).isascii() and str(proof["run_id"]).isdigit() and int(proof["run_id"])>0
        and utc(proof["utc"]).strftime("%Y%m%d")==day and utc(proof["utc"])<utc(start))
    except (KeyError,ValueError,TypeError,AttributeError):return False

def observed_counts(report,day):
    c=report.get("day_source_coverage",{})
    if (report.get("day")!=day or c.get("schema")!="kyoto_impl30_day_source_coverage.v1"
        or c.get("day")!=day or c.get("race_denominator")!=12 or set(c.get("races",{}))!=set(map(str,range(1,13)))):
        return {"state":"COVERAGE_NOT_VERIFIED","counts":None}
    counts=dict(racecards=0,paired_same_slot_races=0,registered_horses_known=0,profile=0,prior_form=0)
    fields={k:[] for k in ("racecards","paired_same_slot_races","profile","prior_form")}
    try:
        for n,row in c["races"].items():
            if row["state"]!="ROSTER_VERIFIED":continue
            start=row["start_utc"]
            if not prestart(row["racecard"],start,day):raise ValueError("racecard_proof")
            horses=row["horses"]
            if not isinstance(horses,dict) or not 2<=len(horses)<=18 or any(not re.fullmatch(r"(?:[1-9]|1[0-8])",k) for k in horses):raise ValueError("horse_identity")
            counts["racecards"]+=1;fields["racecards"].append(int(n))
            counts["registered_horses_known"]+=len(horses)
            if row["paired_same_slot"] is True:
                a,b=(row["markets"][k] for k in ("quinella","bracket_quinella"))
                if not all(prestart(x,start,day) for x in (a,b)) or a["run_id"]!=b["run_id"] or a["cancelled_horses"]!=b["cancelled_horses"]:raise ValueError("paired_proof")
                counts["paired_same_slot_races"]+=1;fields["paired_same_slot_races"].append(int(n))
            for h,hs in horses.items():
                for k in ("profile","prior_form"):
                    v=hs.get(k,{})
                    if v.get("state")=="SOURCE_VERIFIED":
                        if not prestart(v,start,day):raise ValueError("horse_field_proof")
                        counts[k]+=1;fields[k].append([int(n),int(h)])
        if any(type(c["totals"].get(k)) is not int or c["totals"][k]!=v for k,v in counts.items()):raise ValueError("count_mismatch")
    except (KeyError,ValueError,TypeError,AttributeError):
        return {"state":"COVERAGE_PROOF_REJECTED","counts":None}
    return {"state":"OBSERVED_SOURCE_LOWER_BOUND","counts":counts,"observed":fields,
            "horse_denominator_complete":counts["racecards"]==12,"complete_day_certified":False}

def partial_adoption(report,source_id,mode):
    ledger=report.get("external_dispatch_slot_ledger",{}).get("morning",{})
    expected=[f"2026-11-29T{x}:00+00:00" for x in TIMES]
    slots=ledger.get("slots",[])
    valid=(report.get("day")==SUN and ledger.get("schema")=="kyoto_external_dispatch_observations.v1"
      and ledger.get("day")==SUN and ledger.get("family")=="morning" and isinstance(slots,list)
      and len(slots)==4 and [s.get("planned_utc") for s in slots]==expected)
    rows=[]
    if not valid:
        return {"state":"SLOT_LEDGER_UNVERIFIED","rows":rows,"exact_bound_lanes":0,"expected_lanes":8}
    ids=[s.get("run_id") for s in slots if type(s.get("run_id")) is int]
    receipts=report.get("authenticated_applied_policies",[])
    for s in slots:
        rid=s.get("run_id")
        bound=(type(rid) is int and rid>0 and ids.count(rid)==1 and s.get("matching_run_ids")==[rid] and s.get("state")=="COMPLETED")
        for lane in ("PC","SP"):
            row={"planned_utc":s["planned_utc"],"run_id":rid if bound else None,"channel":lane,"state":"UNOBSERVED_OR_UNBOUND","actual_acquisition_certified":False}
            if not bound:
                row["next_action"]="RECONCILE_EXACT_DISPATCH_AND_JOB_INDEX"
            else:
                found=[x for x in receipts if x.get("run_id")==rid and x.get("channel")==lane and x.get("event")=="workflow_dispatch"]
                if s.get(lane.lower()+"_authenticated") is not True or len(found)!=1:
                    row.update(state="APPLIED_RECEIPT_NOT_VERIFIED",next_action="REOPEN_EXACT_SOURCE_ARTIFACT_AND_POLICY_RECEIPT")
                else:
                    p=found[0].get("policy",{})
                    try:
                        stamp=utc(p["observed_at_utc"])
                        selected=p["selected_policy"];reason=p["reason"]
                        if (p.get("schema")!="kyoto_nextday_applied_policy.v1" or p.get("day")!=SUN or p.get("channel")!=lane
                            or selected not in POLICY or (p.get("pc_market_seconds"),p.get("sp_seconds"))!=POLICY[selected]
                            or p.get("source_coverage_proved") is not False or p.get("improvement_proved") is not False
                            or not isinstance(reason,str) or not re.fullmatch(r"[A-Za-z0-9_]{1,200}",reason)
                            or stamp.strftime("%Y%m%d")!=SUN or stamp<utc(s["planned_utc"])):raise ValueError("policy_receipt")
                        exact=selected==mode and reason in {"AUTHENTICATED_SATURDAY_HANDOFF_"+str(source_id),"AUTHENTICATED_SATURDAY_DISPATCH_HANDOFF_"+str(source_id)}
                        row.update(state="EXACT_SIGNED_POLICY_APPLIED" if exact else "OTHER_OR_FALLBACK_POLICY",selected_policy=selected,
                            policy_receipt_sha256=digest(canon(p)),reason=reason,next_action="COMPARE_SOURCE_ORIGINALS_AND_REPLAY_FAILURE" if exact else "REOPEN_POLICY_AUTHENTICATION_AND_FALLBACK")
                    except (KeyError,ValueError,TypeError,AttributeError):
                        row.update(state="APPLIED_RECEIPT_REJECTED",next_action="REOPEN_EXACT_SOURCE_ARTIFACT_AND_POLICY_RECEIPT")
            rows.append(row)
    return {"state":"PARTIAL_OBSERVATION_NOT_FULL_EVALUATION","index_complete":ledger.get("index_complete") is True,
            "rows":rows,"exact_bound_lanes":sum(r["state"]=="EXACT_SIGNED_POLICY_APPLIED" for r in rows),"expected_lanes":8}

def review(sat,sun,source_id,mode):
    if type(source_id) is not int or source_id<=0 or mode not in POLICY:raise ValueError("source_identity")
    before=observed_counts(sat,SAT);after=observed_counts(sun,SUN)
    metrics={}
    if before["counts"] is not None and after["counts"] is not None:
        for k in ("racecards","paired_same_slot_races"):
            b=before["counts"][k];a=after["counts"][k]
            metrics[k]={"before_observed":[b,12],"after_observed":[a,12],
                "observed_delta":a-b,"causal_effect_proved":False}
        for k in ("profile","prior_form"):
            if before["horse_denominator_complete"] and after["horse_denominator_complete"]:
                b=before["counts"];a=after["counts"]
                metrics[k]={"before_observed":[b[k],b["registered_horses_known"]],"after_observed":[a[k],a["registered_horses_known"]],"causal_effect_proved":False}
    return {"schema":"kyoto_partial_adaptation_outcome.v1","source_run_id":source_id,"policy":mode,
        "adoption":partial_adoption(sun,source_id,mode),"before":before,"after":after,"observed_metrics":metrics,
        "causal_effect_proved":False,"full_acquisition_certified":False,"automatic_code_promotion":False,"new_source_http_requests":0}

def verified_reader(root):
    root=Path(root).resolve()
    if subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True,stderr=subprocess.DEVNULL,timeout=5).strip()!=READER:raise ValueError("reader_revision")
    return root
def reader_exec(root,script,args=()):
    env={"PATH":os.environ.get("PATH",""),"PYTHONPATH":str(root),"PYTHONUTF8":"1",
        "GH_TOKEN":os.environ["GH_TOKEN"],"ARCHIVE_KEY":os.environ["ARCHIVE_KEY"],
        "KYOTO_TARGET_DAY":SUN,"KYOTO_WEEKEND_HTTP_APPROVED":"NO","KYOTO_AUX_HTTP_APPROVED":"NO","KYOTO_POSTRACE_HTTP_APPROVED":"NO"}
    raw=subprocess.check_output([sys.executable,"-c",script,*map(str,args)],cwd=root,env=env,stderr=subprocess.DEVNULL,timeout=60)
    if not 0<len(raw)<=5_000_000:raise ValueError("reader_output_size")
    return json.loads(raw)
def preflight(root):
    script="import os,json;from diagnostics.kyoto_impl30_nextday_adaptation import recover;print(json.dumps(recover('20261129',repo='"+REPO+"',collector_sha='"+READER+"',key=os.environ['ARCHIVE_KEY'])))"
    mode,reason=reader_exec(root,script)
    exact=mode==MODE and reason=="AUTHENTICATED_SATURDAY_DISPATCH_HANDOFF_"+str(SOURCE_RUN)
    return {"schema":"kyoto_signed_policy_runtime_preflight.v1","reader_sha":READER,"source_run_id":SOURCE_RUN,
        "selected_policy":mode if mode in POLICY else "UNKNOWN","reason":reason if re.fullmatch(r"[A-Za-z0-9_]{1,200}",reason) else "REJECTED",
        "exact_signed_policy_recovered":exact,"actual_sunday_application_proved":False,"new_source_http_requests":0}
def sunday_report(rid):
    def api(path):return json.loads(subprocess.check_output(["gh","api",f"repos/{REPO}/"+path],text=True,stderr=subprocess.DEVNULL,timeout=10))
    run=api(f"actions/runs/{rid}")
    if (run.get("id")!=rid or run.get("path","").split("@",1)[0]!=PATH or run.get("head_branch")!="main" or run.get("head_repository",{}).get("full_name")!=REPO
        or run.get("event")!="workflow_dispatch" or run.get("status")!="completed" or run.get("created_at","")[:10]!="2026-11-29"):
        raise ValueError("sunday_run_identity")
    arts=api(f"actions/runs/{rid}/artifacts?per_page=100")
    name=f"kyoto-handoff-{rid}-{SUN}"
    matches=[a for a in arts["artifacts"] if a.get("name")==name and a.get("expired") is False]
    if arts["total_count"]!=len(arts["artifacts"]) or len(matches)!=1:raise ValueError("sunday_artifact_identity")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["gh","run","download",str(rid),"--repo",REPO,"--name",name,"--dir",tmp],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
        p=Path(tmp)/"report.json";q=Path(tmp)/"report.sha256"
        if p.is_symlink() or q.is_symlink() or not 0<p.stat().st_size<=5_000_000 or not 0<q.stat().st_size<=256:raise ValueError("report_size")
        raw=p.read_bytes()
        if q.read_text().split()[0]!=digest(raw):raise ValueError("report_sha")
        doc=json.loads(raw)
        if doc.get("day")!=SUN:raise ValueError("report_day")
        return doc,{"run_id":rid,"artifact_id":matches[0]["id"],"report_sha256":digest(raw)}
def main():
    p=argparse.ArgumentParser();p.add_argument("--reader",required=True);p.add_argument("--out",required=True);p.add_argument("--sunday-run",type=int);p.add_argument("--preflight",action="store_true");a=p.parse_args()
    if os.environ.get("GITHUB_REPOSITORY")!=REPO or a.preflight==(a.sunday_run is not None):raise ValueError("runtime_identity")
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True);root=verified_reader(a.reader)
    if a.preflight:
        v=preflight(root)
    else:
        try:
            script="import os,json;from diagnostics.kyoto_impl31_improvement_evaluation import load_saturday;print(json.dumps(load_saturday('"+REPO+"','"+READER+"',os.environ['ARCHIVE_KEY'],source_id="+str(SOURCE_RUN)+")))"
            sat,mode,rid=reader_exec(root,script)
            if rid!=SOURCE_RUN or mode!=MODE:raise ValueError("signed_policy_identity")
            sun,binding=sunday_report(a.sunday_run)
            v=review(sat,sun,rid,mode);v["sunday_source"]=binding
        except Exception as exc:
            v={"schema":"kyoto_partial_adaptation_outcome.v1","source_run_id":SOURCE_RUN,"sunday_run_id":a.sunday_run,
               "state":"REPLAY_INPUT_UNAVAILABLE","error_class":type(exc).__name__,"causal_effect_proved":False,
               "full_acquisition_certified":False,"new_source_http_requests":0}
    (out/"outcome.json").write_bytes(canon(v)+b"\n")
    if a.preflight:
        print("SIGNED_POLICY_RUNTIME_PREFLIGHT="+json.dumps(v,sort_keys=True))
        if not v["exact_signed_policy_recovered"]:raise SystemExit(1)
    else:
        print("PARTIAL_POLICY_OUTCOME="+json.dumps({"state":v.get("state","OBSERVED"),"exact_bound_lanes":v.get("adoption",{}).get("exact_bound_lanes"),"metrics":v.get("observed_metrics",{})},sort_keys=True))
if __name__=="__main__":main()
