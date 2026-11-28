"""Classify source artifact absence from the exact producer job, without data credit."""
JOB={
    ("two-source-production-observer.yml","pc"):"pc-originals-independent",
    ("two-source-production-observer.yml","sp"):"sp-originals-independent",
    ("auxiliary-refresh.yml","auxiliary"):"afternoon-auxiliary-source",
    ("postrace-evidence.yml","postrace"):"postrace-source-evidence",
    ("result-handoff.yml","handoff"):"authenticated-handoff",
    ("result-handoff.yml","cushion-day"):"cushion-day-reconciliation",
    ("workout-source.yml","workout"):"source-only",
    ("cushion-source.yml","cushion"):"cushion-source-only",
}
SKIPPED="JOB_SKIPPED_NO_ARTIFACT"

def exact_job(filename,lane,rid,doc):
    """Require complete, unique, run-bound job metadata; never infer a skip."""
    try:
        name=JOB[(filename,lane)]
        rows=doc["jobs"]
        if (type(rid) is not int or rid<=0 or type(doc["total_count"]) is not int
            or not isinstance(rows,list) or doc["total_count"]!=len(rows) or len(rows)>400):
            return None
        if any(not isinstance(j,dict) or type(j.get("id")) is not int or j["id"]<=0
               or type(j.get("run_id")) is not int or j["run_id"]!=rid for j in rows):
            return None
        if len({j["id"] for j in rows})!=len(rows):return None
        matches=[j for j in rows if j.get("name")==name]
        if len(matches)!=1:return None
        j=matches[0]
        if j.get("status")!="completed" or j.get("conclusion") not in (
            "success","failure","skipped","cancelled","timed_out","neutral","action_required","stale","startup_failure"):
            return None
        return {"job_id":j["id"],"job_conclusion":j["conclusion"]}
    except (KeyError,TypeError,AttributeError):
        return None

def classify_artifact(filename,lane,rid,matches,doc=None):
    ids=[a["id"] for a in matches]
    if len(matches)==1 and matches[0].get("expired") is False:
        return {"state":"PRESENT","ids":ids}
    if matches:
        return {"state":"MISSING_EXPIRED_OR_AMBIGUOUS","ids":ids}
    job=exact_job(filename,lane,rid,doc)
    if job is None:return {"state":"MISSING_JOB_STATE_UNVERIFIED","ids":[]}
    conclusion=job["job_conclusion"]
    if conclusion=="skipped":
        return {"state":SKIPPED,"ids":[],**job,"skip_reason_verified":False}
    return {"state":"MISSING_AFTER_JOB_SUCCESS" if conclusion=="success" else "MISSING_AFTER_JOB_UNSUCCESSFUL",
            "ids":[],**job}
