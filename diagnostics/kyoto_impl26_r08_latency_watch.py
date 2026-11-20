"""R08: detect PC->SP release delay from GitHub job step timestamps only.

No source requests or interference with PC/SP serialization.
"""
from datetime import datetime, timezone
import hashlib

PC="pc-originals-independent"
SP="sp-originals-independent"
PC_CAPTURE="Capture official PC observed originals (bounded no guessed URLs)"
SP_CAPTURE="Independently verified SP link, otherwise record zero-request stop"

def _utc(timestamp):
    if not isinstance(timestamp,str) or not timestamp:
        return None
    try:
        parsed=datetime.fromisoformat(timestamp.replace("Z","+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None

def _step(jobs,job_name,step_name):
    selected=[j for j in jobs if j.get("name")==job_name]
    if len(selected)!=1:
        return None
    steps=[s for s in selected[0].get("steps",[]) if s.get("name")==step_name]
    return steps[0] if len(steps)==1 else None

def assess_delay(jobs,run_id,day,*,threshold_seconds=120):
    if day not in ("20261121","20261122") or not isinstance(jobs,list):
        raise ValueError("invalid_r08_input")
    if not isinstance(threshold_seconds,int) or threshold_seconds<1:
        raise ValueError("invalid_threshold")
    pc=_step(jobs,PC,PC_CAPTURE)
    sp=_step(jobs,SP,SP_CAPTURE)
    completed=_utc(pc.get("completed_at")) if pc else None
    started=_utc(sp.get("started_at")) if sp else None
    result={"schema":"kyoto_impl26_r08_latency.v1","day":day,"run_id":run_id,
            "pc_capture_end_utc":completed.isoformat() if completed else None,
            "sp_capture_start_utc":started.isoformat() if started else None,
            "delay_seconds":None,"threshold_seconds":threshold_seconds,
            "state":"UNMEASURABLE","overlap_detected":False,
            "source_content_authenticated":False}
    if completed and started:
        delta=(started-completed).total_seconds()
        result["delay_seconds"]=delta
        result["overlap_detected"]=delta<0
        result["state"]=("OVERLAP_REQUIRES_REVIEW" if delta<0 else
                          "R08_LATENCY_THRESHOLD_EXCEEDED" if delta>threshold_seconds
                          else "OBSERVED_WITHIN_THRESHOLD")
    return result

def incident_from_assessment(assessment):
    if assessment["state"] not in ("OVERLAP_REQUIRES_REVIEW","R08_LATENCY_THRESHOLD_EXCEEDED"):
        return None
    run_id=assessment["run_id"]
    day=assessment["day"]
    key=f"{day}|{run_id}|R08|{assessment['state']}"
    inc_id="INC-"+day+"-"+str(run_id)+"-"+hashlib.sha256(key.encode()).hexdigest()[:12]
    return {
        "incident_id":inc_id,"day":day,"run_id":run_id,"job_id":None,
        "channel":"PC_SP","failure_stage":"UNKNOWN","risk_ids":["R08"],
        "symptom":f"R08 observed {assessment['state']}, PC_capture_to_SP_start_seconds={assessment['delay_seconds']}",
        "root_cause_status":"UNKNOWN","status":"DETECTED",
        "data_preserved":"UNKNOWN","data_missing":"UNKNOWN",
        "source_timestamps_utc":{k:assessment.get(k) for k in ("pc_capture_end_utc","sp_capture_start_utc")},
        "no_automatic_http_retry":True,
        "requires_further_evidence":True
    }
