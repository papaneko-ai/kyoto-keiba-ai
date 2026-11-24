"""Source-opportunity-first two-schedule policy.

Prior workflow success/attempt is NOT proof of complete official raw markets;
therefore prior runs do not veto the predeclared backup. GitHub date-scoped
concurrency serializes execution; both schedule slots are bounded and finite.
"""
import argparse
import os

EARLY={"20261121":("15 0 21 11 *","15 1 21 11 *"),
       "20261122":("15 0 22 11 *","15 1 22 11 *"),
       "20261128":("15 0 28 11 *","15 1 28 11 *"),
       "20261129":("15 0 29 11 *","15 1 29 11 *")}
PRIMARY={"20261121":"5 2 21 11 *","20261122":"10 2 22 11 *","20261128":"5 2 28 11 *","20261129":"10 2 29 11 *"}
BACKUP={"20261121":"50 2 21 11 *","20261122":"55 2 22 11 *","20261128":"50 2 28 11 *","20261129":"55 2 29 11 *"}
CAPTURE_STEPS=("Capture official PC observed originals",
               "Independently verified SP link, otherwise record zero-request stop")
class RetryGuardRejected(ValueError):
    pass

def evaluate(day,run_id,event,cron,runs,jobs_by_run):
    if day not in PRIMARY or not str(run_id).isdigit() or not isinstance(runs,list):
        raise RetryGuardRejected("RUN_HISTORY_UNVERIFIED_NO_HTTP")
    if event not in ("schedule","workflow_dispatch"):
        raise RetryGuardRejected("INVALID_EVENT_NO_HTTP")
    if event=="schedule" and cron not in (*EARLY[day],PRIMARY[day],BACKUP[day]):
        raise RetryGuardRejected("UNEXPECTED_CRON_NO_HTTP")
    if len(runs)>100:
        raise RetryGuardRejected("SAME_DAY_HISTORY_NEEDS_PAGINATION_NO_HTTP")
    # Two earlier observation slots plus primary and backup each day. Previous run count, job
    # conclusion, or attempted GET is not a reason to waste the backup slot:
    # success can mean safe-stop with no official originals or incomplete odds.
    # Same-day GitHub concurrency is the actual overlapping-network guard.
    previous=[r for r in runs if str(r.get("id"))!=str(run_id)]
    if event=="schedule" and cron in EARLY[day]:
        return "EARLY_OBSERVATION_ALLOWED_INDEPENDENT_OF_PRIOR_RUN"
    if event=="schedule" and cron==BACKUP[day]:
        return ("BACKUP_ALLOWED_AFTER_PRIOR_RUN" if previous
                else "BACKUP_ALLOWED_MISSING_PRIMARY")
    if event=="schedule" and cron==PRIMARY[day]:
        return "PRIMARY_ALLOWED_INDEPENDENT_OF_PRIOR_RUN"
    # An explicitly authorized manual dispatch may restore a missed chance.
    return "MANUAL_AUTHORIZED_RETRY_ALLOWED"

def verify_github(day,run_id,event,cron,repo,token):
    """Never make Github API history availability an extra pre-HTTP veto.

    The workflow itself has four predeclared scheduled entries per day,
    and its day-based concurrency serializes their network activity.
    The exact actual event/cron is checked locally without HTTP.
    """
    return evaluate(day,run_id,event,cron,[],{})

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
    print("NO_GITHUB_API_HISTORY_DEPENDENCY=TRUE")
if __name__=="__main__":
    main()
