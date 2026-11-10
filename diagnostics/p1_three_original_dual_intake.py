"""Three-original offline dual market admission with fail-closed provenance.

Checks independently saved racecard, quinella, bracket odds source *bytes* and
their asserted UTC times. Does NOT authenticate the asserted official origin,
sales or withdrawal updates; NEVER authorizes predictions or wagers.
"""
import hashlib
import io
import json
import zipfile
from datetime import timedelta
from diagnostics.jra_p1_future_evidence import instant
from diagnostics.jra_p1_offline_handoff import import_bundle
from diagnostics.jra_p1_snapshot_gate import evaluate
from diagnostics.p1_dual_market_offline_audit import inspect_dual_market, DualMarketRejected


class ThreeOriginalRejected(ValueError):
    pass


def inspect_three_original_dual_intake(bundle: bytes, snapshot: dict, *, observed_utc: str,\n                                       racecard_channel=None):
    try:
        imported = import_bundle(bundle, observed_utc=observed_utc)
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            receipt = json.loads(archive.read("receipt.json"))
    except (ValueError, TypeError, KeyError, zipfile.BadZipFile) as exc:
        raise ThreeOriginalRejected("source_bundle_invalid") from exc

    if not isinstance(snapshot, dict) or snapshot.get("schema") != "kyoto_p1_prerace_snapshot.v1":
        raise ThreeOriginalRejected("snapshot_schema_invalid")
    source_map = snapshot.get("sources")
    if not isinstance(source_map, dict) or set(source_map) != {"racecard", "odds", "bracket_odds"}:
        raise ThreeOriginalRejected("three_source_bindings_required")

    # The historical snapshot validator accepts two binding keys. Validate
    # those without confusing the third, then independently validate all three.
    legacy = dict(snapshot)
    legacy["sources"] = {"racecard": source_map["racecard"], "odds": source_map["odds"]}
    checked = evaluate(legacy, observed_utc=observed_utc)
    if checked.get("status") != "STRUCTURAL_CHECK_ONLY":
        raise ThreeOriginalRejected("snapshot_blocked:" + ",".join(checked.get("reasons", [])))

    try:
        observed = instant(observed_utc)
        captured = instant(snapshot["captured_utc"])
        cutoff = instant(snapshot["prediction_cutoff_utc"])
        if not captured <= observed < cutoff:
            raise ThreeOriginalRejected("cutoff_elapsed_or_capture_in_future")
        if instant(manifest.get("cutoff_utc")) != cutoff:
            raise ThreeOriginalRejected("cutoff_mismatch")
    except (ValueError, TypeError, KeyError) as exc:
        if isinstance(exc, ThreeOriginalRejected):
            raise
        raise ThreeOriginalRejected("timestamp_invalid") from exc

    if manifest.get("meeting_date") != snapshot.get("meeting_date"):
        raise ThreeOriginalRejected("meeting_date_mismatch")
    wanted = {"racecard": "racecard", "pre_race_odds": "odds", "bracket_odds": "bracket_odds"}
    sources = manifest.get("sources")
    if not isinstance(sources, list) or len(sources) != 3 or receipt.get("source_count") != 3:
        raise ThreeOriginalRejected("three_originals_required")
    seen = {}
    try:
        for source in sources:
            name = wanted.get(source.get("kind"))
            if name is None or name in seen:
                raise ThreeOriginalRejected("source_kind_duplicate_or_unknown")
            if source.get("race") != snapshot.get("race"):
                raise ThreeOriginalRejected("race_mismatch")
            binding = source_map[name]
            if not isinstance(binding, dict) or source.get("sha256") != binding.get("sha256"):
                raise ThreeOriginalRejected(name + "_sha_mismatch")
            source_time = instant(source.get("captured_utc"))
            if source_time != instant(binding.get("captured_utc")):
                raise ThreeOriginalRejected(name + "_time_mismatch")
            if not source_time <= captured or source_time >= cutoff:
                raise ThreeOriginalRejected(name + "_temporal_conflict")
            if name != "racecard" and captured - source_time > timedelta(minutes=30):
                raise ThreeOriginalRejected(name + "_market_stale")
            seen[name] = source["sha256"]
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        if isinstance(exc, ThreeOriginalRejected):
            raise
        raise ThreeOriginalRejected("source_binding_invalid") from exc
    if set(seen) != set(source_map):
        raise ThreeOriginalRejected("three_source_kinds_missing")
    if len(set(seen.values())) != 3:
        raise ThreeOriginalRejected("source_originals_not_independent")

    try:
        market = inspect_dual_market(snapshot, observed_utc=observed_utc)
    except DualMarketRejected as exc:
        raise ThreeOriginalRejected("dual_market_invalid:" + str(exc)) from exc
    if market["status"] != "STRUCTURAL_COMPLETE_ONLY":
        raise ThreeOriginalRejected("dual_market_incomplete_or_not_open")

    # Explicit strict mode reuses the existing real PC/SP racecard parsers.
    # The original three-source check only compared claimed hashes; it did
    # NOT prove that the structured runners came from those source bytes.
    # Legacy callers remain structural-only, with no readiness authorization.
    roster_receipt = None
    if racecard_channel is not None:
        if racecard_channel not in ("PC", "SP"):
            raise ThreeOriginalRejected("racecard_channel_invalid")
        from diagnostics.jra_pc_sp_benchmark import pc_rows, sp_rows
        racecard_source = next(x for x in sources if x["kind"] == "racecard")
        try:
            with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
                original = archive.read(racecard_source["path"])
            parsed = (pc_rows(original, snapshot["race"], meeting_date=snapshot["meeting_date"])
                      if racecard_channel == "PC" else sp_rows(original))
        except (ValueError, TypeError, KeyError, zipfile.BadZipFile) as exc:
            raise ThreeOriginalRejected("racecard_original_parse_failed") from exc
        expected = tuple((row["number"], row["bracket"], row["name"])
                         for row in snapshot["runners"])
        if len(parsed) != len(expected) or parsed != expected:
            raise ThreeOriginalRejected("racecard_original_roster_disagrees_with_snapshot")
        roster_receipt = {
            "channel": racecard_channel,
            "verified_against_original_bytes": True,
            "runner_count": len(parsed),
            "original_sha256": hashlib.sha256(original).hexdigest(),
        }

    raw = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "schema": "kyoto_p1_three_original_offline_intake.v1",
        "status": "THREE_SOURCE_STRUCTURAL_ONLY_NOT_AUTHENTICATED",
        "meeting_date": snapshot["meeting_date"],
        "race": snapshot["race"],
        "bundle_sha256": imported["raw_sha256"],
        "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        "source_sha256": seen,
        "source_count": 3,
        "expected_quinella_pairs": market["expected_quinella_pairs"],
        "expected_bracket_pairs": market["expected_bracket_pairs"],
        "market_coverage": "STRUCTURAL_COMPLETE_ONLY",
        "source_bytes_independently_bound": True,
        "official_origin_authenticated": False,
        "withdrawal_status_authenticated": False,
        "sales_state_authenticated": False,
        "prerace_market_authorized": False,
        "prediction_ready": False,
        "actual_orders_authorized": False,
        "racecard_roster_original_verified": roster_receipt is not None,\n        "racecard_roster_receipt": roster_receipt,\n        "network_requests": 0\n    }
