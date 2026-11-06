"""Offline, fail-closed event scheduler. No network, DB or model writes."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum

JST = timezone(timedelta(hours=9))
CUTOFF_MINUTES = 10

class Stage(str, Enum):
    EVENT_DISCOVERED = "EVENT_DISCOVERED"
    ENTRIES_READY = "ENTRIES_READY"
    DRAW_READY = "DRAW_READY"
    PRE_RACE_INPUT_READY = "PRE_RACE_INPUT_READY"
    PREDICTION_FROZEN = "PREDICTION_FROZEN"
    OFFICIAL_RESULT_READY = "OFFICIAL_RESULT_READY"
    SCORED = "SCORED"
    ARCHIVED = "ARCHIVED"

ORDER = tuple(Stage)
EVIDENCE = {
    Stage.ENTRIES_READY: "entries_verified",
    Stage.DRAW_READY: "draw_verified",
    Stage.PRE_RACE_INPUT_READY: "prerace_inputs_verified",
    Stage.PREDICTION_FROZEN: "prediction_receipt",
    Stage.OFFICIAL_RESULT_READY: "official_result_verified",
    Stage.SCORED: "score_receipt",
    Stage.ARCHIVED: "archive_receipt",
}

class GateError(ValueError):
    pass

def aware_utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise GateError("timezone_aware_datetime_required")
    return value.astimezone(timezone.utc)

def job_key(race_id, stage, snapshot_type, version):
    if not all(isinstance(x, str) and x.strip() for x in (race_id, snapshot_type, version)):
        raise GateError("invalid_job_identity")
    return "|".join((race_id, Stage(stage).value, snapshot_type, version))

@dataclass(frozen=True)
class RaceJob:
    race_id: str
    scheduled_start_utc: datetime
    stage: Stage = Stage.EVENT_DISCOVERED
    retries: int = 0
    last_evidence_sha256: str = ""
    cutoff_utc: datetime | None = None
    frozen_at_utc: datetime | None = None

def advance(job, next_stage, evidence, now, *, confirmed_start_utc=None):
    """Return a new immutable state, or refuse. Repeating same verified event is idempotent."""
    now = aware_utc(now)
    scheduled_start = aware_utc(job.scheduled_start_utc)
    candidate_start = aware_utc(confirmed_start_utc) if confirmed_start_utc else scheduled_start
    next_stage = Stage(next_stage)
    current = Stage(job.stage)
    if not isinstance(evidence, dict):
        raise GateError("evidence_required")
    if next_stage == current:
        return job
    if ORDER.index(next_stage) != ORDER.index(current) + 1:
        raise GateError("stage_order_violation")
    if not evidence.get(EVIDENCE[next_stage]):
        raise GateError("required_evidence_missing")
    if next_stage == Stage.PREDICTION_FROZEN:
        # A late/post-start discovery may never be retroactively frozen.
        cutoff = min(scheduled_start, candidate_start) - timedelta(minutes=CUTOFF_MINUTES)
        if now >= cutoff:
            raise GateError("prediction_deadline_passed")
        if not evidence.get("source_fetched_at_utc") or not evidence.get("model_sha256"):
            raise GateError("prediction_provenance_missing")
        fetched_at = aware_utc(evidence["source_fetched_at_utc"])
        if fetched_at > now or fetched_at >= cutoff:
            raise GateError("future_or_late_source")
        if len(str(evidence.get("prediction_receipt", ""))) < 8:
            raise GateError("invalid_prediction_receipt")
        return replace(job, stage=next_stage, cutoff_utc=cutoff,
                       frozen_at_utc=now, last_evidence_sha256=str(evidence.get("source_sha256", "")))
    if next_stage == Stage.OFFICIAL_RESULT_READY:
        if not job.frozen_at_utc:
            raise GateError("no_prior_prediction")
        if now <= candidate_start:
            raise GateError("race_not_started")
        if not evidence.get("payout_finalized"):
            raise GateError("payout_not_finalized")
    if next_stage == Stage.SCORED and not job.frozen_at_utc:
        raise GateError("missing_frozen_prediction")
    return replace(job, stage=next_stage, last_evidence_sha256=str(evidence.get("source_sha256", "")))

def dry_run(events, initial):
    """Deterministic offline replay; events contain no external actions."""
    job = initial
    audit = []
    for event in events:
        try:
            updated = advance(job, event["stage"], event["evidence"], event["at"],
                              confirmed_start_utc=event.get("confirmed_start_utc"))
            audit.append({"stage": str(event["stage"]), "status": "duplicate" if updated == job else "accepted"})
            job = updated
        except (GateError, KeyError, ValueError) as exc:
            audit.append({"stage": str(event.get("stage")), "status": "blocked", "reason": str(exc)})
    return job, audit
