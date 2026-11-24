"""C12: classify ALL 21 Nov scheduled PC/SP runs and authenticated artifacts.

No JRA HTTP, no model predictions, no automatic next-day code promotion.
This is a reproducible GitHub-API metadata + existing AES evidence audit.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, tempfile
from pathlib import Path
from diagnostics.kyoto_weekend_day21_triage import classify
from diagnostics.kyoto_weekend_day21_artifact_triage import assess_lane

DAY="20261121"
WORKFLOW="Kyoto Nov21-22 independent encrypted original collection"
WORKFLOW_FILE="kyoto-20261121-22-two-source-production-observer.yml"
WEEKENDS={
    DAY:(WORKFLOW,WORKFLOW_FILE,"20261122"),
    "20261128":("Kyoto Nov28-29 independent encrypted original collection",
        "kyoto-20261128-29-two-source-production-observer.yml","20261129"),
    "20261129":("Kyoto Nov28-29 independent encrypted original collection",
        "kyoto-20261128-29-two-source-production-observer.yml",None),
}
EXPECTED_SCHEDULED_RUNS=4
LANES=("PC","SP")

class HandoffRejected(ValueError):
    pass

def _day(timestamp):
    return timestamp[:10] if isinstance(timestamp,str) else None

def _date(day):
    return f"{day[:4]}-{day[4:6]}-{day[6:]}"

def _safe_run(run):
    return {"id":run.get("id"),"event":run.get("event"),
            "created_at":run.get("created_at"),
            "conclusion":run.get("conclusion"),
            "status":run.get("status"),
            "head_sha":run.get("head_sha")}

def summarize(day, entries, *, total_count=None, pagination_complete=True):
    """Fail closed on malformed/partial listings; never infer market success."""
    if day not in WEEKENDS:
        raise HandoffRejected("c12_only_20261121_or_nov28_29")
    workflow,_,next_day=WEEKENDS[day]
    if not isinstance(entries,list) or type(pagination_complete) is not bool:
        raise HandoffRejected("invalid_run_index")
    seen=set()
    normalized=[]
    excluded=[]
    for e in entries:
        if not isinstance(e,dict):
            raise HandoffRejected("invalid_run_entry")
        run=e.get("run")
        if not isinstance(run,dict) or not isinstance(run.get("id"),int) or run["id"]<=0:
            raise HandoffRejected("invalid_run_identity")
        if run["id"] in seen:
            raise HandoffRejected("duplicate_run_identity")
        seen.add(run["id"])
        if run.get("name")!=workflow or _day(run.get("created_at"))!=_date(day):
            raise HandoffRejected("workflow_or_day_identity_mismatch")
        if run.get("event")!="schedule":
            excluded.append({"run_id":run["id"],"event":run.get("event"),"reason":"NON_SCHEDULED_RUN"})
            continue
        if run.get("status")!="completed":
            excluded.append({"run_id":run["id"],"event":"schedule","reason":"RUN_NOT_COMPLETED"})
            normalized.append({"run":_safe_run(run),"state":"RUN_NOT_COMPLETED",
                               "lanes":{c:{"state":"RUN_NOT_COMPLETED"} for c in LANES}})
            continue
        if e.get("metadata_error"):
            normalized.append({"run":_safe_run(run),"state":"RUN_METADATA_UNAVAILABLE",
                               "lanes":{c:{"state":"RUN_METADATA_UNAVAILABLE"} for c in LANES},
                               "error_class":e["metadata_error"]})
            continue
        jobs=e.get("jobs")
        artifacts=e.get("artifacts")
        if not isinstance(jobs,list) or not isinstance(artifacts,list):
            raise HandoffRejected("jobs_or_artifacts_unavailable")
        classification=classify(day,run,jobs,artifacts)
        source=e.get("source_assessment",{})
        if not isinstance(source,dict):
            raise HandoffRejected("source_assessment_invalid")
        lanes={}
        for lane in LANES:
            meta=classification["lanes"][lane]
            state=source.get(lane,{})
            if not isinstance(state,dict):
                raise HandoffRejected("source_lane_invalid")
            lanes[lane]={
                "job_state":meta.get("state"),
                "failure_stage":meta.get("stage"),
                "job_conclusion":meta.get("job_conclusion"),
                "artifact_count":meta.get("artifact_count"),
                "artifact_evidence_state":state.get("state","NOT_INDEPENDENTLY_INSPECTED"),
                "ciphertext_authenticated":state.get("ciphertext_authenticated") is True,
                "source_original_sha_utc_checked":state.get("source_original_sha_utc_checked") is True,
                "both_raw_market_originals_sha_utc_verified":state.get("both_raw_market_originals_sha_utc_verified") is True,
                "c11_family_evidence_state":state.get("c11_family_evidence_state",
                    "NOT_APPLICABLE_OR_NOT_RECOMPUTED"),
                "c11_verified_counts":state.get("c11_verified_counts",{})
                    if state.get("c11_family_evidence_state")=="RECOMPUTED_SOURCE_SHA_UTC_MATCH" else {},
                "official_live_market_accepted":False,
                "prediction_ready":False,
                "error_class":state.get("error_class"),
            }
        normalized.append({"run":_safe_run(run),"state":"ALL_LANES_CLASSIFIED",
                           "lanes":lanes,
                           "needs_manual_review":classification["day22_strategy"]["requires_manual_intervention"]})
    normalized.sort(key=lambda e:(e["run"]["created_at"],e["run"]["id"]))
    scheduled=len(normalized)
    incomplete=max(0,EXPECTED_SCHEDULED_RUNS-scheduled)
    if total_count is not None and (type(total_count) is not int or total_count!=len(entries)):
        pagination_complete=False
    all_screened=(pagination_complete and scheduled==EXPECTED_SCHEDULED_RUNS and
                  all(e["state"]=="ALL_LANES_CLASSIFIED" for e in normalized))
    problems=[]
    if not pagination_complete:problems.append("GITHUB_RUN_LIST_PAGINATION_INCOMPLETE")
    if scheduled!=EXPECTED_SCHEDULED_RUNS:problems.append("SCHEDULED_RUN_COUNT_NOT_EXACTLY_FOUR")
    for e in normalized:
        if e["state"]!="ALL_LANES_CLASSIFIED":
            problems.append("RUN_METADATA_UNAVAILABLE" if e["state"]=="RUN_METADATA_UNAVAILABLE" else "RUN_UNFINISHED")
            continue
        for lane in LANES:
            x=e["lanes"][lane]
            if lane=="PC" and x.get("c11_family_evidence_state")!="RECOMPUTED_SOURCE_SHA_UTC_MATCH":
                problems.append("C11_G03_G06_FAMILY_COUNTS_NOT_RECOMPUTED")
            if x["job_state"]!="ARTIFACT_RETAINED_CONTENT_UNVERIFIED" or not x["ciphertext_authenticated"] or not x["source_original_sha_utc_checked"]:
                problems.append("SOURCE_OR_CIPHERTEXT_GAP_REQUIRES_REVIEW")
                break
    return {
        "schema":"kyoto_impl25_c12_all_runs_day22_handoff.v1",
        "day":day,"expected_schedule_count":EXPECTED_SCHEDULED_RUNS,
        "observed_schedule_count":scheduled,"missing_run_count_lower_bound":incomplete,
        "all_four_expected_scheduled_run_records_observed":scheduled==EXPECTED_SCHEDULED_RUNS,
        "individual_cron_slot_identity_independently_proved":False,
        "all_run_metadata_screened":all_screened,
        "github_run_listing_complete":pagination_complete,
        "github_reported_total_runs":total_count,
        "excluded_runs":excluded,"scheduled_runs":normalized,
        "detected_review_reasons":sorted(set(problems)),
        "next_day":next_day,
        "next_day_action":"KEEP_EXISTING_PIN_OR_REQUIRE_OFFLINE_CI_AND_EXPLICIT_APPROVED_SHA_FOR_FIX",
        "automatic_patch_or_secret_edit_authorized":False,
        "collector_sha_auto_promotion_authorized":False,
        "full_live_jra_coverage_proved":False,
        "independent_sp_full12_fallback_proved":False,
        "source_originals_uploaded":False,
        "new_live_jra_http_requests_started":0,
        "decision_state":"ALL_FOUR_SCHEDULED_RECORDS_CLASSIFIED_SOURCE_GAPS_STILL_REVIEW_REQUIRED"
                         if all_screened else "INCOMPLETE_SCHEDULED_RUN_RECORDS_REVIEW_REQUIRED",
    }

def _gh(endpoint):
    return json.loads(subprocess.check_output(
        ["gh","api",endpoint],stderr=subprocess.DEVNULL,text=True,timeout=30))

def _download(run_id, name, location, repo):
    subprocess.run(["gh","run","download",str(run_id),"--repo",repo,
                    "--name",name,"--dir",str(location)],
                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                   timeout=150,check=True)

def gather(day,repo):
    if day not in WEEKENDS or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repo):
        raise HandoffRejected("unexpected_day_or_repo")
    workflow,workflow_file,_=WEEKENDS[day]
    result=[]
    pagination_complete=True
    seen_ids=set()
    total=None
    # An explicit page loop prevents silently overlooking later workflow runs.
    for page in range(1,11):
        response=_gh(f"repos/{repo}/actions/workflows/{workflow_file}/runs?created={_date(day)}&per_page=100&page={page}")
        if not isinstance(response,dict) or not isinstance(response.get("workflow_runs"),list):
            raise HandoffRejected("github_run_index_invalid")
        rows=response["workflow_runs"]
        reported=response.get("total_count")
        if type(reported) is not int:
            raise HandoffRejected("github_run_total_missing")
        if total is None:total=reported
        if total!=reported:
            pagination_complete=False
        for run in rows:
            if run.get("id") in seen_ids:
                raise HandoffRejected("github_run_duplicated_across_pages")
            seen_ids.add(run.get("id"))
            if run.get("name")!=workflow or _day(run.get("created_at"))!=_date(day):
                raise HandoffRejected("github_wrong_workflow_or_day")
            result.append(run)
        if len(result)>=total:
            if len(result)!=total:
                pagination_complete=False
            break
        if not rows:
            pagination_complete=False
            break
    else:
        pagination_complete=False
    entries=[]
    for run in result:
        if run.get("event")!="schedule" or run.get("status")!="completed":
            entries.append({"run":run})
            continue
        run_id=run["id"]
        try:
            jobs_doc=_gh(f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100")
            art_doc=_gh(f"repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100")
            jobs=jobs_doc["jobs"];artifacts=art_doc["artifacts"]
            if (not isinstance(jobs,list) or not isinstance(artifacts,list)
                or jobs_doc.get("total_count")!=len(jobs) or art_doc.get("total_count")!=len(artifacts)):
                raise HandoffRejected("github_job_artifact_listing_incomplete")
        except (OSError,ValueError,TypeError,KeyError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
            # Isolate one failed run metadata lookup; do not lose other runs
            # or misrepresent an API failure as a JRA retrieval failure.
            entries.append({"run":run,"metadata_error":type(exc).__name__})
            continue
        source={}
        for lane in LANES:
            name=f"kyoto-{lane.lower()}-{run_id}-{day}"
            found=[a for a in artifacts if a.get("name")==name and a.get("expired") is False]
            if len(found)!=1:
                source[lane]={"state":"EXACT_ARTIFACT_NOT_FOUND_OR_AMBIGUOUS"}
                continue
            with tempfile.TemporaryDirectory(prefix="kyoto_c12_ciphertext_only_") as tmp:
                target=Path(tmp)/"ciphertext"
                target.mkdir()
                try:
                    _download(run_id,name,target,repo)
                    source[lane]=assess_lane(target,day=day,channel=lane,
                        key=os.environ.get("ARCHIVE_KEY",""),repo=repo,run_id=str(run_id))
                except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
                    source[lane]={"state":"ARTIFACT_DOWNLOAD_FAILED",
                                  "error_class":type(exc).__name__}
                # Existing assess_lane decrypts only into its own ephemeral dir.
        entries.append({"run":run,"jobs":jobs,"artifacts":artifacts,
                        "source_assessment":source})
    report=summarize(day,entries,total_count=total,pagination_complete=pagination_complete)
    if day in ("20261128","20261129"):
        from diagnostics.kyoto_impl30_day_coverage import combine
        slots=[]
        for entry in entries:
            source=entry.get("source_assessment",{}).get("PC",{})
            slot=source.get("day_coverage_slot")
            if (source.get("ciphertext_authenticated") is True and
                source.get("source_original_sha_utc_checked") is True and
                isinstance(slot,dict) and slot.get("run_id")==str(entry["run"]["id"])):
                slots.append(slot)
        coverage=combine(day,slots)
        coverage["all_scheduled_run_metadata_screened"]=report["all_run_metadata_screened"]
        coverage["expected_scheduled_slots"]=EXPECTED_SCHEDULED_RUNS
        coverage["unassessed_pc_slots"]=max(0,report["observed_schedule_count"]-len(slots))
        report["day_source_coverage"]=coverage
    return report

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--day",choices=tuple(WEEKENDS),required=True)
    p.add_argument("--repo",required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    report=gather(args.day,args.repo)
    if args.out.exists() or args.out.is_symlink():
        raise HandoffRejected("cannot_overwrite_existing_handoff")
    args.out.parent.mkdir(parents=True,exist_ok=True)
    content=(json.dumps(report,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode()
    args.out.write_bytes(content)
    digest=hashlib.sha256(content).hexdigest()
    args.out.with_suffix(".sha256").write_text(digest+"  "+args.out.name+"\n")
    print("C12_ALL_RUNS_TRIAGED="+str(report["observed_schedule_count"]))
    print("C12_SCHEDULE_COMPLETENESS="+str(report["all_run_metadata_screened"]))
    print("C12_LIVE_JRA_CERTIFIED=False")

if __name__=="__main__":
    main()
