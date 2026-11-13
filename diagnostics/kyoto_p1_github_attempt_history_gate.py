"""GitHub Actions source-attempt guard that distinguishes PRE-HTTP setup failures.

A known skipped JRA GET step in an entirely completed failed run is safe
to retry. Anything ambiguous or potentially HTTP-started is consumed.
Repository API is independently queried per page and per previous run.
"""
from __future__ import annotations
import json,re
from urllib.request import Request,urlopen

class AttemptLedgerRejected(ValueError): pass

def was_proven_zero_http(previous_run, previous_jobs, *, http_step):
    if (type(previous_run) is not dict or previous_run.get("status")!="completed"
        or previous_run.get("conclusion") not in ("failure","cancelled","skipped")
        or type(previous_jobs) is not list or not previous_jobs):
        return False
    observed=False
    for job in previous_jobs:
        if type(job) is not dict or job.get("status")!="completed":
            return False
        steps=job.get("steps")
        if type(steps) is not list or not steps:
            return False
        matches=[s for s in steps if s.get("name")==http_step]
        if len(matches)!=1:
            return False
        step=matches[0]
        if step.get("conclusion")!="skipped":
            return False
        observed=True
    return observed

def audit_previous_runs(*, repo, token, branch, current_run_id,
                        workflow_name, http_step, api_fetch=None):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repo):
        raise AttemptLedgerRejected("repository_invalid")
    if not re.fullmatch(r"[0-9]+",str(current_run_id)):
        raise AttemptLedgerRejected("current_run_id_invalid")
    if type(token) is not str or not token:
        raise AttemptLedgerRejected("GitHub_API_token_unavailable")
    def get(url):
        request=Request(url,headers={
            "Authorization":"Bearer "+token,
            "Accept":"application/vnd.github+json",
            "User-Agent":"KyotoAI-Official-Source-RunGate"
        })
        if api_fetch is not None:
            return api_fetch(url)
        with urlopen(request,timeout=12) as response:
            return json.load(response)
    previous=[];seen=False;complete=False
    for page in range(1,26):
        response=get(f"https://api.github.com/repos/{repo}/actions/runs?branch={branch}&per_page=100&page={page}")
        runs=response.get("workflow_runs")
        if type(runs) is not list:
            raise AttemptLedgerRejected("run_history_invalid")
        for run in runs:
            if type(run) is not dict or type(run.get("id")) is not int:
                raise AttemptLedgerRejected("run_record_invalid")
            if run.get("name")==workflow_name:
                if str(run["id"])==str(current_run_id):
                    seen=True
                else:
                    previous.append(run)
        if len(runs)<100:
            complete=True
            break
    if not complete or not seen:
        raise AttemptLedgerRejected("current_run_or_full_history_unverified")
    unconsumed=[]
    for run in previous:
        page=get(f"https://api.github.com/repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100")
        jobs=page.get("jobs")
        if page.get("total_count")!=len(jobs or []):
            raise AttemptLedgerRejected("prior_jobs_pagination_unverified")
        if not was_proven_zero_http(run,jobs,http_step=http_step):
            raise AttemptLedgerRejected("prior_HTTP_possible_do_not_repeat:"+str(run["id"]))
        unconsumed.append(run["id"])
    return {"schema":"kyoto_source_attempt_history.v1",
            "current_run_id":str(current_run_id),
            "prior_zero_http_runs":unconsumed,
            "prior_HTTP_possible":False,
            "source_HTTP_attempt_authorized_by_history_only":False}
