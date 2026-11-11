"""Kyoto AI storage-budget and retention decision guard, pure offline library.

This module never connects to a database, scrapes any website, moves files,
or deletes bytes. It makes deterministic advice with fail-closed evidence.
"""
from __future__ import annotations

from datetime import date
from typing import Any

SCHEMA = "kyoto_storage_retention_v1"
DEFAULT_QUOTA_BYTES = 5_000_000_000
HOT_DAYS = 3 * 365
RAW_ARCHIVE_DAYS = 5 * 365
WARNING_RATIO = 0.60
ARCHIVE_RATIO = 0.75
HARD_STOP_RATIO = 0.85
PROTECTED = frozenset({
    "FROZEN_PREDICTION", "PAPER_TRADE_LEDGER", "OFFICIAL_RESULT",
    "OFFICIAL_PAYOUT", "SOURCE_PROVENANCE", "MODEL_VERSION",
    "EVOLUTION_DECISION", "ROLLBACK_EVIDENCE", "MODEL_EVALUATION",
    "ARCHIVE_MANIFEST",
})
RAW = frozenset({"RAW_HTML", "RAW_SNAPSHOT"})
DERIVED = frozenset({"DERIVED_FEATURE", "CACHE", "TEMPORARY"})

class RetentionRejected(ValueError):
    pass


def _nonnegative_int(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        raise RetentionRejected(name + "_invalid")
    return value


def storage_status(*, used_bytes: int, quota_bytes: int = DEFAULT_QUOTA_BYTES,
                   remaining_read_rows: int | None = None,
                   remaining_write_rows: int | None = None) -> dict:
    """Decide storage state. Totals must be verified externally for all DBs."""
    _nonnegative_int(used_bytes, "used_bytes")
    _nonnegative_int(quota_bytes, "quota_bytes")
    if quota_bytes == 0:
        raise RetentionRejected("quota_zero")
    if remaining_read_rows is not None:
        _nonnegative_int(remaining_read_rows, "remaining_read_rows")
    if remaining_write_rows is not None:
        _nonnegative_int(remaining_write_rows, "remaining_write_rows")
    ratio = used_bytes / quota_bytes
    if ratio >= HARD_STOP_RATIO:
        stage = "HARD_STOP_UNNECESSARY_RAW_WRITES"
    elif ratio >= ARCHIVE_RATIO:
        stage = "ARCHIVE_REVIEW"
    elif ratio >= WARNING_RATIO:
        stage = "WARNING"
    else:
        stage = "NORMAL"
    return {
        "schema": SCHEMA,
        "used_bytes": used_bytes, "quota_bytes": quota_bytes,
        "used_percent": round(ratio * 100, 3),
        "stage": stage,
        "never_delete_protected": True,
        "automatic_deletion_permitted": False,
        "continue_mandatory_trades_if_space_and_quota_available": True,
        "remaining_read_rows": remaining_read_rows,
        "remaining_write_rows": remaining_write_rows,
    }


def retention_action(*, kind: str, captured_on: str, today: str,
                     archive_verified: bool, still_needed_for_recheck: bool,
                     model_depends_on_it: bool, provenance_available: bool) -> dict:
    """Classify a record; not a deletion instruction.

    archive_verified requires an independent restore proof, not merely a file.
    """
    if not isinstance(kind, str) or not kind:
        raise RetentionRejected("kind_invalid")
    try:
        captured = date.fromisoformat(captured_on)
        current = date.fromisoformat(today)
    except (TypeError, ValueError) as exc:
        raise RetentionRejected("date_invalid") from exc
    if captured > current:
        raise RetentionRejected("captured_in_future")
    for name, v in (
        ("archive_verified", archive_verified),
        ("still_needed_for_recheck", still_needed_for_recheck),
        ("model_depends_on_it", model_depends_on_it),
        ("provenance_available", provenance_available),
    ):
        if type(v) is not bool:
            raise RetentionRejected(name + "_not_boolean")
    age = (current - captured).days
    if kind in PROTECTED:
        action, reason = "KEEP_LONG_TERM", "critical_reproducibility_evidence"
    elif kind in RAW:
        if age < HOT_DAYS:
            action, reason = "KEEP_HOT", "younger_than_hot_window"
        elif not archive_verified or not provenance_available or still_needed_for_recheck or model_depends_on_it:
            action, reason = "PROTECT_PENDING_ARCHIVE_REVIEW", "independent_restore_or_dependency_gate"
        elif age >= RAW_ARCHIVE_DAYS:
            action, reason = "MANUAL_DELETION_CANDIDATE", "archive_restorable_and_old"
        else:
            action, reason = "MOVE_TO_COLD_REVIEW", "archive_restorable"
    elif kind in DERIVED:
        if still_needed_for_recheck or model_depends_on_it or not archive_verified:
            action, reason = "PROTECT_PENDING_ARCHIVE_REVIEW", "dependency_or_restore_gate"
        elif age >= HOT_DAYS:
            action, reason = "MANUAL_DELETION_CANDIDATE", "reconstructible_old_derived"
        else:
            action, reason = "KEEP_HOT", "younger_than_hot_window"
    else:
        action, reason = "PROTECT_UNKNOWN_KIND", "unknown_kind_must_be_reviewed"
    return {
        "schema": SCHEMA, "kind": kind, "age_days": age,
        "action": action, "reason": reason,
        "delete_now": False,
        "manual_approval_required_for_deletion": True,
    }
