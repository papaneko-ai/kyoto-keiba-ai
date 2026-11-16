"""Source-opportunity-first two-schedule policy.

Prior workflow success/attempt is NOT proof of complete official raw markets;
therefore prior runs do not veto the predeclared backup. GitHub date-scoped
concurrency serializes execution; both schedule slots are bounded and finite.
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
    # One primary and one backup slot each day. Previous run count, job
    # conclusion, or attempted GET is not a reason to waste the backup slot:
    # success can mean safe-stop with no official originals or incomplete odds.
    # Same-day GitHub concurrency is the actual overlapping-network guard.
    previous=[r for r in runs if str(r.get("id"))!=str(run_id)]
    if event=="schedule" and cron==BACKUP[day]:
        return ("BACKUP_ALLOWED_AFTER_PRIOR_RUN" if previous
                else "BACKUP_ALLOWED_MISSING_PRIMARY")
    if event=="schedule" and cron==PRIMARY[day]:
        return "PRIMARY_ALLOWED_INDEPENDENT_OF_PRIOR_RUN"
    # An explicitly authorized manual dispatch may restore a missed chance.
    return "MANUAL_AUTHORIZED_RETRY_ALLOWED"

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
    return evaluate(day,run_id,event,cron,data["workflow_runs"],{})

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
