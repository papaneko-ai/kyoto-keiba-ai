"""Authenticated next-day operational adaptation, no arbitrary code or secret changes.

The Saturday evidence handoff signs a bounded policy selected from revalidated
coverage. Sunday prefers the scheduled run's signed artifact and can use a
verified main-branch dispatch of the same handoff workflow as recovery.
Missing or inconsistent evidence preserves baseline; no acquisition veto.
"""
import argparse,hashlib,hmac,json,os,re,subprocess,tempfile,time
from pathlib import Path
from diagnostics.kyoto_impl25_c12_all_runs_handoff import run_name_matches

SOURCE_DAY="20261128"
TARGET_DAY="20261129"
WORKFLOW="kyoto-20261128-29-result-handoff.yml"
NAME="Kyoto Nov28-29 authenticated all-run handoff"
POLICY={"BASELINE":(720,240),"MARKET_OR_ROSTER_RECOVERY":(720,360),"PROFILE_RECOVERY":(600,360)}
SCHEMA="kyoto_nextday_adaptation.v1"
OBSERVER="kyoto-20261128-29-two-source-production-observer.yml"
OBSERVER_NAME="Kyoto Nov28-29 independent encrypted original collection"
# Exact source revision used by the fixed Saturday handoff workflow; the
# policy is authenticated evidence, not executable code. Never accept arbitrary SHA.
SATURDAY_HANDOFF_COLLECTOR="3f4b3d77357745ead05a9f78db34eb6ac2d78637"
# Independently decrypted four actual Nov28 dispatch artifacts proved no G03
# or SP racecard link discovery (incident #141; runs 46100456028, 46100842649).
NOV28_INCIDENT_REPO="papaneko-ai/kyoto-keiba-ai"
NOV28_INCIDENT_RUN_IDS=(46087080554,46092343351,46096495437,46100155324)

def confirmed_failure_lanes(run,jobs):
    """Positive job failure only, never infer failure from absence of originals."""
    from diagnostics.kyoto_weekend_day21_triage import STAGES
    rid=run.get("id")
    if type(rid) is not int or rid<=0 or run.get("status")!="completed" or not isinstance(jobs,list):return []
    found=[]
    for lane,name in (("PC","pc-originals-independent"),("SP","sp-originals-independent")):
        matches=[j for j in jobs if isinstance(j,dict) and j.get("name")==name]
        if len(matches)!=1:continue
        job=matches[0]
        if job.get("run_id")!=rid or job.get("status")!="completed" or job.get("conclusion")!="failure":continue
        steps=job.get("steps",[])
        if not isinstance(steps,list):continue
        stages=[STAGES.get(step.get("name")) for step in steps if isinstance(step,dict) and step.get("conclusion")=="failure"]
        valid=[x for x in stages if x in {"PRE_HTTP_GUARD","PC_CAPTURE","SP_CAPTURE","OFFLINE_REGRESSION","ENCRYPTION_OR_STOP","ARTIFACT"}]
        if valid:found.append({"run_id":rid,"lane":lane,"stage":valid[0]})
    return found


def recover_from_metadata(api, repo):
    """Independent, read-only fallback: positive failure evidence only.

    GitHub API provenance is supplied by the authenticated runtime gh client.
    No source coverage, raw data, or successful acquisition is inferred.
    """
    index=api(f"repos/{repo}/actions/workflows/{OBSERVER}/runs?created=2026-11-28&per_page=100")
    runs=index["workflow_runs"]
    if not isinstance(runs,list) or index["total_count"]!=len(runs) or len(runs)>100:
        raise ValueError("incomplete_observer_index")
    ids=[r["id"] for r in runs]
    if any(type(i) is not int or i<=0 for i in ids) or len(set(ids))!=len(ids):
        raise ValueError("invalid_observer_run_identity")
    eligible=[r for r in runs if run_name_matches(r,OBSERVER_NAME,OBSERVER,SOURCE_DAY)
              and r.get("created_at","")[:10]=="2026-11-28"
              and (r.get("event")=="schedule" or (r.get("event")=="workflow_dispatch" and r.get("head_branch")=="main"))
              and r.get("status")=="completed"
              and r.get("head_repository",{}).get("full_name")==repo
              and r.get("path","").split("@",1)[0]==".github/workflows/"+OBSERVER]
    # Most recent completed failure first. A positive failure observation
    # does not require every other run to have been inspected.
    for r in sorted(eligible,key=lambda r:(r["created_at"],r["id"]),reverse=True)[:4]:
        rid=r["id"]
        jobs_doc=api(f"repos/{repo}/actions/runs/{rid}/jobs?per_page=100")
        jobs=jobs_doc["jobs"]
        if not isinstance(jobs,list) or jobs_doc["total_count"]!=len(jobs) or len(jobs)>100:
            continue
        failures=confirmed_failure_lanes(r,jobs)
        if failures:
            f=failures[0]
            prefix="OBSERVER_DISPATCH_FAILURE_METADATA_ONLY" if r["event"]=="workflow_dispatch" else "OBSERVER_FAILURE_METADATA_ONLY"
            return "MARKET_OR_ROSTER_RECOVERY",f"{prefix}_{rid}_{f['lane']}"
    # A successful Actions job is not a successful acquisition. These exact
    # known runs were independently authenticated and investigated on Nov28.
    # Verify their presence in the same official workflow before using the
    # incident as a bounded fallback. This never grants source/model credit.
    if repo==NOV28_INCIDENT_REPO:
        incident={r["id"] for r in eligible if r["id"] in NOV28_INCIDENT_RUN_IDS}
        if incident==set(NOV28_INCIDENT_RUN_IDS):
            return "MARKET_OR_ROSTER_RECOVERY","NOV28_AUTHENTICATED_SOURCE_GAP_INCIDENT_141"
    return "BASELINE","NO_CONFIRMED_OBSERVER_FAILURE"


def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()

def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()

def _key(key):
    if not isinstance(key,str) or not re.fullmatch(r"[a-fA-F0-9]{64}",key):
        raise ValueError("bad_archive_key")
    return hmac.digest(bytes.fromhex(key),b"kyoto-nextday-policy-v1","sha256")

def derive(report):
    """Only a complete Saturday run index plus original-bound coverage can adapt.

    The profile-focus alternative still acquires markets first; SP receives a
    longer fallback window. All configurations preserve the PC 17-min archive
    boundary and never change the start-time, identity or request-rate gates.
    """
    if report.get("day")!=SOURCE_DAY or report.get("next_day")!=TARGET_DAY:
        raise ValueError("wrong_source_day")
    # A confirmed execution failure is evidence for a bounded recovery
    # strategy even when no original was acquired. It is NOT source coverage.
    # Nov21's P0 incident had precisely this shape.
    runs=report.get("scheduled_runs",[])
    known_failures=[]
    seen=set()
    for item in runs if isinstance(runs,list) else []:
        run=item.get("run",{}) if isinstance(item,dict) else {}
        rid=run.get("id")
        if (type(rid) is not int or rid<=0 or rid in seen or
            run.get("event")!="schedule" or run.get("created_at","")[:10]!="2026-11-28" or
            run.get("status")!="completed" or item.get("state")!="ALL_LANES_CLASSIFIED"):
            continue
        seen.add(rid)
        for lane in ("PC","SP"):
            row=item.get("lanes",{}).get(lane,{})
            if (row.get("artifact_evidence_state")=="PRE_HTTP_SAFE_STOP_NO_SOURCE" or
                (row.get("job_conclusion")=="failure" and row.get("job_state") in ("NO_ARTIFACT","FAILED_WITH_ARTIFACT"))):
                known_failures.append({"run_id":rid,"lane":lane,"stage":row.get("failure_stage","UNKNOWN")})
    # Handoff builder adds this separate evidence only for same-day main
    # dispatches with authenticated API run/job identity; native counts stay fixed.
    manual_failures=report.get("manual_failure_assessment",[])
    for row in manual_failures if isinstance(manual_failures,list) else []:
        if not isinstance(row,dict):continue
        rid=row.get("run_id");lane=row.get("lane");stage=row.get("stage")
        if (type(rid) is int and rid>0 and rid not in seen and lane in ("PC","SP")
            and stage in {"PRE_HTTP_GUARD","PC_CAPTURE","SP_CAPTURE","OFFLINE_REGRESSION","ENCRYPTION_OR_STOP","ARTIFACT"}
            and row.get("event")=="workflow_dispatch" and row.get("head_branch")=="main"
            and row.get("created_at","")[:10]=="2026-11-28"):
            f={"run_id":rid,"lane":lane,"stage":stage}
            if f not in known_failures:known_failures.append(f)
    def incomplete(reason):
        if known_failures:
            return {"mode":"MARKET_OR_ROSTER_RECOVERY","reason":"SATURDAY_EXECUTION_FAILURE_WITH_INCOMPLETE_SOURCE_EVIDENCE",
                    "known_failures":sorted(known_failures,key=lambda r:(r["run_id"],r["lane"])),
                    "source_coverage_proved":False}
        return {"mode":"BASELINE","reason":reason}
    c=report.get("day_source_coverage",{})
    # A late or missing native schedule must not invalidate independently
    # authenticated originals from an authorized same-day dispatch. C12 keeps
    # those observations separate; this does not certify the scheduled slots.
    manual=report.get("manual_source_assessment",[])
    manual_verified=isinstance(manual,list) and any(
        isinstance(m,dict) and type(m.get("run_id")) is int and m["run_id"]>0
        and m.get("authenticated_pc_slot") is True for m in manual)
    if ((report.get("all_run_metadata_screened") is not True and not manual_verified) or
        report.get("github_run_listing_complete") is not True or
        c.get("schema")!="kyoto_impl30_day_source_coverage.v1" or
        c.get("day")!=SOURCE_DAY or c.get("race_denominator")!=12 or
        type(c.get("authenticated_pc_slots")) is not int or c["authenticated_pc_slots"]<1):
        return incomplete("SOURCE_INDEX_INCOMPLETE")
    races=c.get("races",{})
    if set(races)!=set(map(str,range(1,13))):
        return incomplete("RACE_DENOMINATOR_UNVERIFIED")
    t=c.get("totals",{})
    roster=paired=horses=profiles=history=0
    for r in races.values():
        if r.get("state")!="ROSTER_VERIFIED" or r.get("racecard",{}).get("state")!="SOURCE_VERIFIED":continue
        roster+=1
        paired+=int(r.get("paired_same_slot") is True)
        for h in r.get("horses",{}).values():
            horses+=1
            profiles+=int(h.get("profile",{}).get("state")=="SOURCE_VERIFIED")
            history+=int(h.get("prior_form",{}).get("state")=="SOURCE_VERIFIED")
    observed={"racecards":roster,"paired_same_slot_races":paired,
              "registered_horses_known":horses,"profile":profiles,"prior_form":history}
    if any(type(t.get(k)) is not int or t[k]!=v for k,v in observed.items()):
        return incomplete("COVERAGE_COUNTS_DISAGREE")
    if roster<12 or paired<12:
        mode="MARKET_OR_ROSTER_RECOVERY";reason="SATURDAY_MARKET_OR_ROSTER_GAP"
    elif horses and (profiles<horses or history<horses):
        mode="PROFILE_RECOVERY";reason="SATURDAY_PROFILE_OR_HISTORY_GAP"
    else:
        mode="BASELINE";reason="NO_SUPPORTED_ADAPTATION_NEEDED"
    return {"mode":mode,"reason":reason,"counts":observed}

def make(report,*,repo,run_id,collector_sha,key):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repo) or not str(run_id).isdigit() or not re.fullmatch(r"[a-f0-9]{40}",collector_sha):
        raise ValueError("invalid_policy_identity")
    decision=derive(report)
    body={"schema":SCHEMA,"repo":repo,"source_day":SOURCE_DAY,"target_day":TARGET_DAY,
          "source_run_id":str(run_id),"collector_sha":collector_sha,
          "source_report_sha256":digest(report),"decision":decision}
    return {"body":body,"hmac_sha256":hmac.new(_key(key),canonical(body),hashlib.sha256).hexdigest()}

def accept(doc,report,*,repo,run_id,collector_sha,key):
    body=doc["body"]
    if not hmac.compare_digest(doc["hmac_sha256"],hmac.new(_key(key),canonical(body),hashlib.sha256).hexdigest()):
        raise ValueError("policy_authentication_failed")
    expected=make(report,repo=repo,run_id=run_id,collector_sha=collector_sha,key=key)
    if doc!=expected:raise ValueError("policy_context_or_recomputation_mismatch")
    return body["decision"]["mode"]

def recover(day,*,repo,collector_sha,key,monotonic=time.monotonic):
    """Both read-only paths share the original 18 second deadline.

    The authenticated primary path has priority. The independent metadata
    path starts concurrently, so a primary timeout cannot consume its window.
    """
    from concurrent.futures import ThreadPoolExecutor
    if day!=TARGET_DAY:return "BASELINE","NOT_TARGET_SUNDAY"
    end=monotonic()+18
    def timeout(cap):
        left=end-monotonic()
        if left<=0:raise TimeoutError("adaptation_lookup_deadline")
        return min(left,cap)
    try:
        _key(key)
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repo) or not re.fullmatch(r"[a-f0-9]{40}",collector_sha):
            raise ValueError("invalid_runtime_identity")
        timeout(18)
    except Exception as exc:return "BASELINE","FALLBACK_"+type(exc).__name__
    def api(endpoint):
        return json.loads(subprocess.check_output(["gh","api",endpoint],text=True,stderr=subprocess.DEVNULL,timeout=timeout(5)))
    def primary():
        index=api(f"repos/{repo}/actions/workflows/{WORKFLOW}/runs?created=2026-11-28&per_page=100")
        runs=index["workflow_runs"]
        if index["total_count"]!=len(runs) or len(runs)>100 or len({r["id"] for r in runs})!=len(runs):raise ValueError("incomplete_run_index")
        def same_workflow(r):
            return (type(r.get("id")) is int and r["id"]>0
                    and run_name_matches(r,NAME,WORKFLOW,SOURCE_DAY) and r.get("created_at","")[:10]=="2026-11-28"
                    and r.get("head_repository",{}).get("full_name")==repo
                    and r.get("path","").split("@",1)[0]==".github/workflows/"+WORKFLOW)
        scheduled=[r for r in runs if same_workflow(r) and r.get("event")=="schedule"]
        def complete(r):
            return r.get("status")=="completed" and r.get("conclusion")=="success"
        eligible=[r for r in scheduled if complete(r)]
        manual=sorted((r for r in runs if same_workflow(r) and r.get("event")=="workflow_dispatch"
                       and r.get("head_branch")=="main" and complete(r)),
                      key=lambda r:(r["created_at"],r["id"]),reverse=True)
        def read_run(r):
            rid=r["id"]
            index=api(f"repos/{repo}/actions/runs/{rid}/artifacts?per_page=100")
            arts=index["artifacts"]
            if index["total_count"]!=len(arts):raise ValueError("incomplete_artifact_index")
            name=f"kyoto-handoff-{rid}-{SOURCE_DAY}"
            if len([a for a in arts if a.get("name")==name and a.get("expired") is False])!=1:raise ValueError("missing_or_ambiguous_artifact")
            with tempfile.TemporaryDirectory(prefix="kyoto_adaptive_plan_") as tmp:
                subprocess.run(["gh","run","download",str(rid),"--repo",repo,"--name",name,"--dir",tmp],
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=timeout(10))
                def read(name):
                    p=Path(tmp)/name
                    if p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=5_000_000:
                        raise ValueError("invalid_policy_artifact_file")
                    return json.loads(p.read_text(encoding="utf8"))
                try:report=read("report.json")
                except (OSError,ValueError):raise ValueError("HANDOFF_REPORT_MISSING_OR_INVALID") from None
                try:doc=read("nextday_policy.json")
                except (OSError,ValueError):raise ValueError("HANDOFF_POLICY_MISSING_OR_INVALID") from None
                # The Saturday handoff intentionally runs a fixed older
                # collector. Authenticate and recompute against that exact
                # source, then apply only the bounded policy table.
                signer=doc.get("body",{}).get("collector_sha")
                if signer==SATURDAY_HANDOFF_COLLECTOR and repo==NOV28_INCIDENT_REPO:
                    mode=accept(doc,report,repo=repo,run_id=rid,collector_sha=SATURDAY_HANDOFF_COLLECTOR,key=key)
                else:
                    mode=accept(doc,report,repo=repo,run_id=rid,collector_sha=collector_sha,key=key)
                prefix="AUTHENTICATED_SATURDAY_HANDOFF_" if r["event"]=="schedule" else "AUTHENTICATED_SATURDAY_DISPATCH_HANDOFF_"
                return mode,prefix+str(rid),doc["body"]["decision"]["reason"]
        # Preserve native schedule preference and the existing failure labels.
        # A signed, same-workflow main dispatch is a separate recovery path,
        # not evidence that GitHub's native scheduler or Cloudflare worked.
        if len(eligible)==1:
            try:return read_run(eligible[0])
            except Exception as exc: primary_error=exc
        elif not scheduled:primary_error=ValueError("HANDOFF_NOT_STARTED")
        elif len(scheduled)!=1:primary_error=ValueError("HANDOFF_AMBIGUOUS")
        elif scheduled[0].get("status")!="completed":primary_error=ValueError("HANDOFF_INCOMPLETE")
        elif scheduled[0].get("conclusion")=="timed_out":primary_error=ValueError("HANDOFF_TIMED_OUT")
        else:primary_error=ValueError("HANDOFF_FAILED")
        for candidate in manual:
            try:
                timeout(18)
                return read_run(candidate)
            except TimeoutError:break
            except Exception:continue
        raise primary_error
    pool=ThreadPoolExecutor(max_workers=2)
    try:
        main=pool.submit(primary)
        backup=pool.submit(recover_from_metadata,api,repo)
        try:
            mode,reason,decision_reason=main.result(timeout=max(0,end-monotonic()))
            # A signed incomplete baseline is not affirmative evidence of full
            # capture. A later confirmed failure may still justify recovery.
            # Never override a complete authenticated decision or wait longer.
            if mode=="BASELINE" and decision_reason in {"SOURCE_INDEX_INCOMPLETE","RACE_DENOMINATOR_UNVERIFIED","COVERAGE_COUNTS_DISAGREE"}:
                try:
                    m,r=backup.result(timeout=max(0,end-monotonic()))
                    if m=="MARKET_OR_ROSTER_RECOVERY":return m,reason+"__"+r
                except Exception:pass
            return mode,reason
        except Exception as exc:
            # Only fixed diagnostic labels may leave this function; never log
            # API output, credentials, exception arguments or artifact bytes.
            labels={"HANDOFF_NOT_STARTED","HANDOFF_AMBIGUOUS","HANDOFF_INCOMPLETE",
                    "HANDOFF_TIMED_OUT","HANDOFF_FAILED","HANDOFF_REPORT_MISSING_OR_INVALID",
                    "HANDOFF_POLICY_MISSING_OR_INVALID","missing_or_ambiguous_artifact",
                    "policy_authentication_failed","policy_context_or_recomputation_mismatch",
                    "incomplete_run_index","incomplete_artifact_index"}
            primary_error=str(exc) if isinstance(exc,ValueError) and str(exc) in labels else type(exc).__name__
        try:
            mode,reason=backup.result(timeout=max(0,end-monotonic()))
            return mode,"PRIMARY_"+primary_error+"__"+reason
        except Exception as exc:
            return "BASELINE","PRIMARY_"+primary_error+"__SECONDARY_"+type(exc).__name__
    finally:
        # No write, no JRA requests, no acquisition veto. Each running API
        # command already has a deadline; do not wait for a losing path.
        pool.shutdown(wait=False,cancel_futures=True)

def budgets(mode):
    return POLICY.get(mode,POLICY["BASELINE"])

def main():
    p=argparse.ArgumentParser();p.add_argument("--report",required=True,type=Path);p.add_argument("--out",required=True,type=Path);a=p.parse_args()
    report=json.loads(a.report.read_text(encoding="utf8"))
    sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
    plan=make(report,repo=os.environ["GITHUB_REPOSITORY"],run_id=os.environ["GITHUB_RUN_ID"],collector_sha=sha,key=os.environ["ARCHIVE_KEY"])
    with a.out.open("x",encoding="utf8") as f:json.dump(plan,f,sort_keys=True,ensure_ascii=False)
    print("NEXTDAY_POLICY="+plan["body"]["decision"]["mode"])
if __name__=="__main__":main()
