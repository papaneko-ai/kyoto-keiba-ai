"""Evidence-based adjudication of fixed FMEA risks; not a bug-free claim.
The original reverse-FMEA register is an immutable discovery record.
Each supported verifier evaluates evidence rather than accepting a PASS flag.
Unimplemented verifiers remain open. No live acquisition, settings or release.
"""
from __future__ import annotations
import argparse,hashlib,json,re,subprocess
from pathlib import Path
import yaml

IDS={f"GAP-{i:02d}" for i in range(1,26)}
LEDGER="docs/diagnostics/KYOTO_REVERSE_FMEA_GAP_REGISTER_20261116.json"
PREF=".github/workflows/kyoto-impl30-nov28-29-offline-preflight.yml"
REPO="papaneko-ai/kyoto-keiba-ai"
PACKAGES={"beautifulsoup4":"4.15.0","soupsieve":"4.1.3","typing-extensions":"4.16.0","cryptography":"46.0.7","cffi":"2.1.1","pycparser":"3.12"}
PYTHON="3.11.18"
WORKFLOWS={
 ".github/workflows/kyoto-20261128-29-two-source-production-observer.yml":{"select-collector":False,"pc-originals-independent":True,"sp-originals-independent":True},
 ".github/workflows/kyoto-20261128-29-auxiliary-refresh.yml":{"afternoon-auxiliary-source":True},
 ".github/workflows/kyoto-20261128-29-postrace-evidence.yml":{"postrace-source-evidence":True},
 ".github/workflows/kyoto-20261128-29-result-handoff.yml":{"authenticated-handoff":True}}
def digest(raw):return hashlib.sha256(raw).hexdigest()
def git_head(root):return subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
def require(ok,reason):
    if not ok:raise ValueError(reason)
def parse(raw):
    return yaml.load(raw,Loader=yaml.BaseLoader)
def verify_job(job,install_required):
    steps=job["steps"]
    versions=[s.get("with",{}).get("python-version") for s in steps if s.get("uses","").startswith("actions/setup-python@")]
    require(versions==[PYTHON],"python_pin_mismatch")
    installs=[s["run"].strip() for s in steps if re.search(r"\bpip\s+install\b",s.get("run",""))]
    if not install_required:
        require(not installs,"unexpected_install")
        return
    require(len(installs)==1,"missing_or_multiple_install")
    tokens=installs[0].split()
    require(tokens[:5]==["python","-m","pip","install","--no-deps"],"install_command_mismatch")
    require(sorted(tokens[5:])==sorted(f"{k}=={v}" for k,v in PACKAGES.items()),"dependency_pin_mismatch")
def gap17(production,collector_root,run,jobs,log):
    sha=git_head(collector_root)
    require(re.fullmatch("[a-f0-9]{40}",sha),"invalid_collector")
    evidence={}
    for path,expected in WORKFLOWS.items():
        raw=(production/path).read_bytes();doc=parse(raw)
        require(set(doc["jobs"])==set(expected),"source_job_inventory_mismatch")
        for name,install in expected.items():verify_job(doc["jobs"][name],install)
        if path.endswith("two-source-production-observer.yml"):
            require(doc["jobs"]["select-collector"]["env"]["DEFAULT_COLLECTOR_SHA"]==sha,"collector_pin_mismatch")
            for name in ("pc-originals-independent","sp-originals-independent"):
                require(doc["jobs"][name]["env"]["COLLECTOR_SHA"]=="${{ needs.select-collector.outputs.collector_sha }}","lane_pin_mismatch")
        else:
            job=next(iter(doc["jobs"].values()))
            refs=[s.get("with",{}).get("ref") for s in job["steps"] if s.get("uses","").startswith("actions/checkout@")]
            require(refs==[sha],"collector_pin_mismatch")
        evidence[path]=digest(raw)
    raw=(collector_root/PREF).read_bytes()
    verify_job(parse(raw)["jobs"]["offline-next-week"],True)
    evidence["collector:"+PREF]=digest(raw)
    rid=run.get("id")
    require(type(rid) is int and rid>0 and run.get("head_sha")==sha and run.get("repository",{}).get("full_name")==REPO and run.get("head_repository",{}).get("full_name")==REPO and run.get("path","").split("@",1)[0]==PREF and run.get("event") in ("push","pull_request","workflow_dispatch") and run.get("status")=="completed" and run.get("conclusion")=="success","ci_identity_or_result")
    require(jobs.get("total_count")==len(jobs["jobs"])==1,"job_inventory")
    job=jobs["jobs"][0]
    require(type(job.get("id")) is int and job["id"]>0 and job.get("run_id")==rid and job.get("name")=="offline-next-week" and job.get("status")=="completed" and job.get("conclusion")=="success","ci_job_identity")
    steps={s["name"]:s["conclusion"] for s in job["steps"]}
    for name in ("Run actions/setup-python@v5","Install existing parsing and crypto libraries","Exact candidate and offline root cause regression"):require(steps.get(name)=="success","ci_step_missing")
    expected=sorted(f"{k}-{v}" for k,v in PACKAGES.items())
    matches=[line.split("Successfully installed ",1)[1].strip().split() for line in log.splitlines() if "Successfully installed " in line]
    require(len(matches)==1 and sorted(matches[0])==expected,"observed_install_mismatch")
    require(sha in log,"observed_checkout_mismatch")
    return {"scope":"Original GAP-17: unpinned parser/crypto dependency versions in scheduled source jobs","collector_sha":sha,"ci_run_id":rid,"ci_job_id":job["id"],"source_sha256":evidence,"ci_log_sha256":digest(log.encode()),"observed_packages":PACKAGES,"python":PYTHON,"not_covered":["runner or action image changes","provider outage","future live data acquisition"]}
VERIFIERS={"GAP-17":gap17}

def summarize(ledger,results):
    rows=ledger["risks"]
    require(len(rows)==25 and {r["id"] for r in rows}==IDS,"fixed_risk_inventory_changed")
    require(set(results)==IDS,"adjudication_inventory_changed")
    closed=sorted(k for k,v in results.items() if v["state"]=="CLOSED_IN_ORIGINAL_SCOPE")
    open_ids=sorted(IDS-set(closed))
    return {"fixed_risk_count":25,"closed_count":len(closed),"closed_ids":closed,"open_ids":open_ids,
        "open_high_count":sum(r["severity"]=="BLOCKER" and r["id"] in open_ids for r in rows),
        "all_fixed_risks_closed":not open_ids,"no_unknown_bugs_claimed":False,
        "production_activation_authorized":False,"live_acquisition_certified":False,"results":results}

def assess(production,collector_root,run,jobs,log):
    raw=(collector_root/LEDGER).read_bytes();ledger=json.loads(raw)
    require(ledger.get("schema")=="kyoto_fmea_reverse_coverage_v1","ledger_schema")
    # The discovery record stays unchanged, never rewritten to green.
    require(all(r.get("test_proven") is False and r.get("remediated") is False for r in ledger["risks"]),"discovery_record_modified")
    # No arbitrary evidence status, registry path or verifier name from input.
    results={}
    for rid in sorted(IDS):
        verifier=VERIFIERS.get(rid)
        if verifier is None:results[rid]={"state":"OPEN","reason":"RISK_SPECIFIC_EVIDENCE_NOT_YET_ADJUDICATED"};continue
        try:results[rid]={"state":"CLOSED_IN_ORIGINAL_SCOPE","evidence":verifier(production,collector_root,run,jobs,log)}
        except (ValueError,KeyError,TypeError,OSError,AttributeError,IndexError,yaml.YAMLError,subprocess.SubprocessError) as exc:
            results[rid]={"state":"OPEN","reason":type(exc).__name__+":"+str(exc)[:100]}
    result=summarize(ledger,results)
    result.update(schema="kyoto_fmea_evidence_adjudication.v1",discovery_ledger_sha256=digest(raw),production_sha=git_head(production),collector_sha=git_head(collector_root))
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--production",type=Path,default=Path("."))
    p.add_argument("--collector",type=Path,required=True)
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--jobs",type=Path,required=True)
    p.add_argument("--log",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--require-closed",action="store_true")
    a=p.parse_args()
    result=assess(a.production,a.collector,json.loads(a.run.read_text()),json.loads(a.jobs.read_text()),a.log.read_text())
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("FMEA_ADJUDICATION="+json.dumps({k:result[k] for k in ("fixed_risk_count","closed_count","closed_ids","open_high_count","all_fixed_risks_closed")},sort_keys=True))
    if a.require_closed and not result["all_fixed_risks_closed"]:raise SystemExit("FIXED_RISKS_REMAIN_OPEN")
if __name__=="__main__":main()
