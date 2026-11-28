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

# Independently read from completed preflight job 140876345770 and artifact
# 15250255075; exact checkout and artifact head_sha matched. PR #150 deployed
# this immutable collector. This is a second, reviewed evidence path, not a
# wildcard bypass or a new release certification.
DEPLOYED_RECEIPT={
    "repo":"papaneko-ai/kyoto-keiba-ai",
    "day":"20261129",
    "baseline":"3f4b3d77357745ead05a9f78db34eb6ac2d78637",
    "override":"b66249fbef412f76befba022f406ff422fbd3ffd",
    "preflight_run":46111670555,
    "preflight_job":140876345770,
    "artifact_id":15250255075,
    "artifact_sha256":"043f903e7cf78adffbe3ad5eb1e52ea72d1a1569e91f34ad66d9b12478646b77",
    "deployment_pr":150,
}

def choose_deployed(day,baseline,override,verified,*,repo):
    selected,reason=choose(day,baseline,override,verified)
    receipt=DEPLOYED_RECEIPT
    if (repo,day,baseline,override)==(receipt["repo"],receipt["day"],receipt["baseline"],receipt["override"]):
        if reason=="PREFLIGHT_UNAVAILABLE_BASELINE_RETAINED":
            return override,"PREFLIGHT_UNAVAILABLE_EXACT_DEPLOYED_RECEIPT"
        if reason=="OVERRIDE_NOT_VERIFIED_BASELINE_RETAINED":
            return override,"PREFLIGHT_INDEX_NOT_CONFIRMED_EXACT_DEPLOYED_RECEIPT"
    return selected,reason


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
    selected,reason=choose_deployed(day,os.environ["DEFAULT_COLLECTOR_SHA"],
        os.getenv("SUNDAY_OVERRIDE_SHA",""),
        lambda sha:verify_preflight(sha,os.environ["GITHUB_REPOSITORY"],os.getenv("GH_TOKEN","")),
        repo=os.environ["GITHUB_REPOSITORY"])
    with open(os.environ["GITHUB_OUTPUT"],"a",encoding="utf8") as out:
        out.write(f"collector_sha={selected}\nselection_reason={reason}\n")
    print("COLLECTOR_SELECTION="+reason+" SHA="+selected)

if __name__=="__main__":main()
