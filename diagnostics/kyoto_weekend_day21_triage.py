"""Classify first-day result for the next-day remediation decision.

Consumes GitHub API-derived job and artifact metadata only; never claims
market authentication from job success. No JRA HTTP, changes to main, or
automatic approval of a novel code repair.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import argparse
import json

EXPECTED={"pc-originals-independent","sp-originals-independent"}
STAGES={"Race date, immutable commit, secret, first attempt and non-replay guard":"PRE_HTTP_GUARD",
        "Capture official PC observed originals (bounded no guessed URLs)":"PC_CAPTURE",
        "Independently verified SP link, otherwise record zero-request stop":"SP_CAPTURE",
        "Always encrypt any source originals or save factual pre-HTTP stop":"ENCRYPTION_OR_STOP",
        "Always encrypt SP originals or save factual pre-HTTP stop":"ENCRYPTION_OR_STOP",
        "Upload only AES-GCM ciphertext or safe-stop receipt":"ARTIFACT",
        "Independent SP offline regression":"OFFLINE_REGRESSION",
        "Offline regression mandatory before any live HTTP":"OFFLINE_REGRESSION"}

def classify(day, run, jobs, artifacts):
    if day not in ("20261121","20261122"):
        raise ValueError("triage_day_invalid")
    if not isinstance(run,dict) or not isinstance(jobs,list) or not isinstance(artifacts,list):
        raise ValueError("triage_evidence_invalid")
    if run.get("event") not in ("schedule","workflow_dispatch"):
        raise ValueError("unexpected_observation_event")
    if not run.get("created_at","").startswith(day[:4]+"-"+day[4:6]+"-"+day[6:]):
        raise ValueError("wrong_day_run_cannot_be_reinterpreted")
    findings={}
    for lane,needle in (("PC","pc-originals-independent"),("SP","sp-originals-independent")):
        matches=[job for job in jobs if job.get("name")==needle]
        if len(matches)!=1:
            findings[lane]={"state":"JOB_MISSING_OR_DUPLICATE","stage":"UNKNOWN"}
            continue
        job=matches[0]
        failed=[step.get("name","") for step in job.get("steps",[]) if step.get("conclusion")=="failure"]
        artifact=[a for a in artifacts if a.get("name","").startswith("kyoto-"+lane.lower()+"-") and not a.get("expired",False)]
        if job.get("conclusion")=="success" and artifact:
            status="ARTIFACT_RETAINED_CONTENT_UNVERIFIED"
            stage="POSTFLIGHT_INSPECTION_REQUIRED"
        elif not artifact:
            status="NO_ARTIFACT"
            stage=next((STAGES.get(x,"OTHER_FAILURE") for x in failed),"UNKNOWN")
        else:
            status="FAILED_WITH_ARTIFACT"
            stage=next((STAGES.get(x,"OTHER_FAILURE") for x in failed),"UNKNOWN")
        findings[lane]={"state":status,"stage":stage,"failed_steps":failed,
                        "artifact_count":len(artifact),
                        "job_conclusion":job.get("conclusion")}
    # Prevalidated next-day behavior does not depend on editing protected main
    # after Saturday. Unknown causes must not be mistaken for auto-repair.
    blocked_stages={"PRE_HTTP_GUARD","ENCRYPTION_OR_STOP","ARTIFACT",
                    "OFFLINE_REGRESSION","OTHER_FAILURE","UNKNOWN"}
    needs_intervention=any(
        item.get("stage") in blocked_stages for item in findings.values()
    )
    day22_strategy={
        "PC":"FRESH_NEXT_DAY_INDEPENDENT_OFFICIAL_SOURCE_CAPTURE",
        "SP":"SUNDAY_EXPANDED_BOUNDED_6_PAGE_OBSERVED_OFFICIAL_NAVIGATION",
        "data_claim":"SOURCE_ONLY_NO_PREDICTION_OR_MARKET_AUTHENTICATION",
        "requires_manual_intervention":needs_intervention,
        "human_review_reason":"PRE_HTTP_OR_EVIDENCE_FAILURE" if needs_intervention else
                              "OFFICIAL_BYTES_STILL_REQUIRE_INSPECTION",
        "automatic_unknown_source_code_repair":False,
        "configured_before_day21":True,
    }
    return {"schema":"kyoto_weekend_day21_day22_handoff.v1",
            "day":day,"run_id":run.get("id"),
            "run_conclusion":run.get("conclusion"),
            "lanes":findings,
            "observed_workflow_run_exists":run.get("actual_run_observed",True) is not False,
            "day22_strategy":day22_strategy,
            "next_day":"20261122" if day=="20261121" else None,
            "candidate_promotion_permitted_without_independent_tests":False,
            "requires_actual_original_decrypt_and_hash_check":True,
            "automatic_code_patch_approved":False,
            "ready_for_prerace_predictions":False,
            "result":"NEEDS_HUMAN_TRIAGE_OR_PREVALIDATED_NEXT_DAY_FALLBACK"}


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--day",required=True)
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--jobs",type=Path,required=True)
    p.add_argument("--artifacts",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    run=json.loads(args.run.read_text(encoding="utf8"))
    jobs=json.loads(args.jobs.read_text(encoding="utf8"))["jobs"]
    artifacts=json.loads(args.artifacts.read_text(encoding="utf8"))["artifacts"]
    result=classify(args.day,run,jobs,artifacts)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf8")
    print("FIRST_DAY_SECOND_DAY_HANDOFF="+result["result"])

if __name__=="__main__":
    main()
