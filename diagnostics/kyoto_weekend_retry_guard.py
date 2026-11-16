"""Strict second-schedule policy: retry only absent or pre-HTTP stopped primary.

Never retry an attempted capture, in-progress run, or untrusted history.
"""
import argparse
import json
import os
from urllib.request import Request,urlopen

PRIMARY={"20261121":"5 2 21 11 *","20261122":"10 2 22 11 *"}
BACKUP={"20261121":"50 2 21 11 *","20261122":"55 2 22 11 *"}
CAPTURE_STEPS=("Capture official PC observed originals",
               "Independently verified SP link, otherwise record zero-request stop")
class RetryGuardRejected(ValueError):
    pass

def evaluate(day,run_id,event,cron,runs,jobs_by_run):
    if day not in PRIMARY or not str(run_id).isdigit() or not isinstance(runs,list):
        raise RetryGuardRejected("RUN_HISTORY_UNVERIFIED_NO_HTTP")
    if event not in ("schedule","workflow_dispatch"):
        raise RetryGuardRejected("INVALID_EVENT_NO_HTTP")
    if event=="schedule" and cron not in (PRIMARY[day],BACKUP[day]):
        raise RetryGuardRejected("UNEXPECTED_CRON_NO_HTTP")
    if len(runs)>100:
        raise RetryGuardRejected("SAME_DAY_HISTORY_NEEDS_PAGINATION_NO_HTTP")
    previous=[r for r in runs if str(r.get("id"))!=str(run_id)]
    if not previous:
        return "BACKUP_ALLOWED_NO_PRIMARY_RUN" if cron==BACKUP[day] else "PRIMARY_ALLOWED"
    if event!="schedule" or cron!=BACKUP[day]:
        raise RetryGuardRejected("PREVIOUS_WORKFLOW_RUN_ON_TARGET_DAY_NO_HTTP")
    for r in previous:
        if (r.get("event")!="schedule" or r.get("status")!="completed" or
            r.get("conclusion") not in ("failure","cancelled","skipped","timed_out")):
            raise RetryGuardRejected("PREVIOUS_WORKFLOW_RUN_ON_TARGET_DAY_NO_HTTP")
        rid=r.get("id")
        if rid not in jobs_by_run or not isinstance(jobs_by_run[rid],list):
            raise RetryGuardRejected("RUN_HISTORY_UNVERIFIED_NO_HTTP")
        for j in jobs_by_run[rid]:
            if j.get("status")!="completed" or not isinstance(j.get("steps"),list):
                raise RetryGuardRejected("RUN_HISTORY_UNVERIFIED_NO_HTTP")
            for step in j["steps"]:
                if any(step.get("name","").startswith(name) for name in CAPTURE_STEPS):
                    if step.get("conclusion")!="skipped":
                        raise RetryGuardRejected("PREVIOUS_CAPTURE_ATTEMPTED_NO_HTTP")
    return "BACKUP_ALLOWED_VERIFIED_PRE_HTTP_STOP"

def _get(url,token):
    request=Request(url,headers={"Authorization":"Bearer "+token,
         "Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"})
    with urlopen(request,timeout=12) as response:
        return json.load(response)

def verify_github(day,run_id,event,cron,repo,token):
    if day not in PRIMARY:
        raise RetryGuardRejected("RUN_HISTORY_UNVERIFIED_NO_HTTP")
    date=f"{day[:4]}-{day[4:6]}-{day[6:]}"
    base=f"https://api.github.com/repos/{repo}"
    url=(base+"/actions/workflows/kyoto-20261121-22-two-source-production-observer.yml/runs"
        +"?created="+date+"&per_page=100")
    data=_get(url,token)
    if (not isinstance(data.get("workflow_runs"),list) or
        data.get("total_count",101)>100):
        raise RetryGuardRejected("SAME_DAY_HISTORY_NEEDS_PAGINATION_NO_HTTP")
    prior=[r for r in data["workflow_runs"] if str(r.get("id"))!=str(run_id)]
    jobs={}
    for r in prior:
        rid=r.get("id")
        if type(rid) is not int:
            raise RetryGuardRejected("RUN_HISTORY_UNVERIFIED_NO_HTTP")
        response=_get(base+f"/actions/runs/{rid}/jobs?per_page=100",token)
        if response.get("total_count",101)>100 or not isinstance(response.get("jobs"),list):
            raise RetryGuardRejected("RUN_HISTORY_UNVERIFIED_NO_HTTP")
        jobs[rid]=response["jobs"]
    return evaluate(day,run_id,event,cron,data["workflow_runs"],jobs)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--day",required=True)
    args=parser.parse_args()
    try:
        result=verify_github(args.day,os.environ["GITHUB_RUN_ID"],
            os.environ["GITHUB_EVENT_NAME"],os.environ.get("GITHUB_EVENT_SCHEDULE",""),
            os.environ["GITHUB_REPOSITORY"],os.environ["GH_TOKEN"])
    except (RetryGuardRejected,KeyError,ValueError,OSError,TimeoutError) as exc:
        raise SystemExit("RETRY_GUARD_BLOCKED_NO_HTTP:"+str(exc)) from exc
    print("RETRY_GUARD_DECISION="+result)
    print("JRA_HTTP_ATTEMPTS_BY_GUARD=0")
if __name__=="__main__":
    main()
