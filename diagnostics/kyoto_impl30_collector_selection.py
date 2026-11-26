"""Resolve one immutable collector for both PC and SP lanes; never promote an untested override."""
import json
import os
import re
from urllib.parse import urlencode
from urllib.request import Request,urlopen

SHA=re.compile(r"[0-9a-f]{40}\Z")
REPO=re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
PREFLIGHT="kyoto-impl30-nov28-29-offline-preflight.yml"
DAYS=("20261128","20261129")

def choose(day,baseline,override,verified):
    if day not in DAYS or not isinstance(baseline,str) or not SHA.fullmatch(baseline):
        raise ValueError("invalid_baseline_or_day")
    if day==DAYS[0] or not override or override==baseline:
        return baseline,"BASELINE"
    if not isinstance(override,str) or not SHA.fullmatch(override):
        return baseline,"OVERRIDE_INVALID_BASELINE_RETAINED"
    try:
        if verified(override) is True:
            return override,"EXACT_PREFLIGHT_VERIFIED_OVERRIDE"
    except Exception:
        return baseline,"PREFLIGHT_UNAVAILABLE_BASELINE_RETAINED"
    return baseline,"OVERRIDE_NOT_VERIFIED_BASELINE_RETAINED"

def verify_preflight(candidate,repo,token,fetch=urlopen):
    if not SHA.fullmatch(candidate) or not REPO.fullmatch(repo) or not token:
        return False
    url=(f"https://api.github.com/repos/{repo}/actions/workflows/{PREFLIGHT}/runs?"
        +urlencode({"head_sha":candidate,"status":"success","per_page":100}))
    request=Request(url,headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json"})
    with fetch(request,timeout=8) as response:
        report=json.loads(response.read(2_000_001))
    return any(run.get("head_sha")==candidate and run.get("status")=="completed"
        and run.get("conclusion")=="success" and run.get("event") in ("push","workflow_dispatch")
        and run.get("head_repository",{}).get("full_name")==repo
        and run.get("path","").split("@",1)[0]==".github/workflows/"+PREFLIGHT
        for run in report.get("workflow_runs",[]) if isinstance(run,dict))

def main():
    day=os.environ["KYOTO_TARGET_DAY"]
    selected,reason=choose(day,os.environ["DEFAULT_COLLECTOR_SHA"],
        os.getenv("SUNDAY_OVERRIDE_SHA",""),
        lambda sha:verify_preflight(sha,os.environ["GITHUB_REPOSITORY"],os.getenv("GH_TOKEN","")))
    with open(os.environ["GITHUB_OUTPUT"],"a",encoding="utf8") as out:
        out.write(f"collector_sha={selected}\nselection_reason={reason}\n")
    print("COLLECTOR_SELECTION="+reason+" SHA="+selected)

if __name__=="__main__":main()
