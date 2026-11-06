"""Source-aware JRA PC/SP routing policy.

Offline decision only: no network requests, model training, database writes or
automatic source switching. A small HTML response is NOT proof of low latency.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median

ALLOWED = frozenset(("PC", "SP"))
REQUIRED_FIELDS = frozenset(("race_id", "horse_number", "horse_name", "frame_number", "profile_link"))
TIMING_SAMPLE_MIN = 5
SPEED_GAIN_REQUIRED = 0.15  # 15% median latency improvement
SOURCE_EXPERIMENT_MIN = 3  # successful independent race comparisons
MAX_CLOCK_SKEW_SECONDS = 900  # 15 min for direct live cross-checks


class SourceRoutingError(ValueError):
    pass


@dataclass(frozen=True)
class SourceEvidence:
    channel: str
    race_key: str
    captured_at_utc: str
    content_sha256: str
    rows: tuple  # (horse number, frame number, normalized name) in horse-number order
    fields_verified: frozenset
    parse_errors: tuple = ()
    scratches_verified: bool = False
    independent_checks: int = 0
    latency_ms_samples: tuple = ()
    observed_bytes: int = 0
    response_verified: bool = False

    def valid(self):
        if self.channel not in ALLOWED:
            return False
        if not isinstance(self.race_key, str) or not self.race_key:
            return False
        if not self.response_verified or self.parse_errors:
            return False
        if not REQUIRED_FIELDS.issubset(self.fields_verified):
            return False
        if not isinstance(self.content_sha256, str) or len(self.content_sha256) != 64:
            return False
        try:
            int(self.content_sha256, 16)
        except ValueError:
            return False
        if self.observed_bytes <= 0:
            return False
        if not self.rows or len(self.rows) != len(set(self.rows)):
            return False
        numbers = [x[0] for x in self.rows]
        if numbers != list(range(1, len(numbers) + 1)):
            return False
        for x in self.rows:
            if len(x) != 3 or type(x[0]) is not int or type(x[1]) is not int or not 1 <= x[1] <= 8 or not x[2]:
                return False
        return True


def _timestamp(value):
    if not isinstance(value, str):
        raise SourceRoutingError("timestamp_missing")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SourceRoutingError("timestamp_invalid") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise SourceRoutingError("timestamp_requires_timezone")
    return stamp.astimezone(timezone.utc)


def _latency(samples):
    if len(samples) < TIMING_SAMPLE_MIN:
        return None
    if any(type(x) not in (int, float) or x <= 0 for x in samples):
        return None
    return float(median(samples))


def decide(pc: SourceEvidence | None, sp: SourceEvidence | None, *,
           successful_sp_crosschecks=0, require_scratches=False):
    """Conservative policy: PC baseline, promote SP only with strong timing+parity.

    No automatic fallback without explicit full validation; conflicts are blocked.
    """
    if pc is not None and pc.channel != "PC":
        raise SourceRoutingError("pc_channel_mismatch")
    if sp is not None and sp.channel != "SP":
        raise SourceRoutingError("sp_channel_mismatch")
    good_pc = pc is not None and pc.valid()
    good_sp = sp is not None and sp.valid()
    answer = {
        "schema_version": "jra_dual_channel_policy.v1",
        "preferred_source": None,
        "state": "BLOCK",
        "reason": None,
        "pc_valid": good_pc,
        "sp_valid": good_sp,
        "same_race_parity": False,
        "sp_latency_advantage": None,
        "requires_final_starter_check": True,
        "prediction_ready": False,
        "training_ready": False,
    }
    if not good_pc and not good_sp:
        answer.update(reason="no_verified_source")
        return answer
    if good_pc and good_sp:
        if pc.race_key != sp.race_key:
            answer.update(reason="source_race_mismatch")
            return answer
        delta = abs((_timestamp(pc.captured_at_utc) - _timestamp(sp.captured_at_utc)).total_seconds())
        if delta > MAX_CLOCK_SKEW_SECONDS:
            answer.update(state="RECHECK", reason="capture_time_gap_exceeds_15_minutes")
            return answer
        if pc.rows != sp.rows:
            answer.update(state="RECHECK", reason="different_runner_or_frame_snapshot")
            return answer
        answer["same_race_parity"] = True
        if require_scratches and (not pc.scratches_verified or not sp.scratches_verified):
            answer.update(state="RECHECK", reason="scratch_validation_missing")
            return answer
        median_pc = _latency(pc.latency_ms_samples)
        median_sp = _latency(sp.latency_ms_samples)
        if median_pc and median_sp:
            improvement = (median_pc - median_sp) / median_pc
            answer["sp_latency_advantage"] = round(improvement, 4)
            if (improvement >= SPEED_GAIN_REQUIRED
                    and successful_sp_crosschecks >= SOURCE_EXPERIMENT_MIN
                    and sp.independent_checks >= SOURCE_EXPERIMENT_MIN):
                answer.update(preferred_source="SP", state="CANDIDATE",
                              reason="sp_validated_and_measurably_faster")
                return answer
        answer.update(preferred_source="PC", state="CANDIDATE",
                      reason="pc_baseline_sp_speed_not_proven")
        return answer
    if good_pc:
        answer.update(preferred_source="PC", state="CANDIDATE",
                      reason="sp_missing_or_invalid")
        return answer
    # A separate SP can preserve collection if PC is down, but is untrusted for
    # prediction until the missing independent checks and scratches are completed.
    if successful_sp_crosschecks >= SOURCE_EXPERIMENT_MIN and sp.independent_checks >= SOURCE_EXPERIMENT_MIN:
        answer.update(preferred_source="SP", state="PROVISIONAL",
                      reason="pc_unavailable_sp_verified_not_release_ready")
    else:
        answer.update(state="RECHECK", reason="sp_only_insufficient_independent_evidence")
    return answer


def source_bytes_comparison(pc_bytes: int, sp_bytes: int):
    if type(pc_bytes) is not int or type(sp_bytes) is not int or pc_bytes <= 0 or sp_bytes <= 0:
        raise SourceRoutingError("invalid_html_size")
    return {
        "pc_bytes": pc_bytes, "sp_bytes": sp_bytes,
        "sp_reduction_pct": round((pc_bytes - sp_bytes) * 100 / pc_bytes, 1),
        "latency_improvement_proven": False,
    }
