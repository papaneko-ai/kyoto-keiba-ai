"""P1-FB stage5: guarded offline source-first adapter integration.

This module deliberately has NO HTTP client or network imports. Injection does not
authorize real-world fetches: the transport must be explicitly marked as a replay.
Archived raw bytes are sealed atomically before invoking any parser.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import tempfile

from diagnostics.jra_p1_fb_stage4_mock_adapter import Source, run as stage4_run
from diagnostics.jra_p1_fb_request_budget_policy import Attempt, official

@dataclass(frozen=True)
class RosterHorse:
    meeting_date: str
    race: int
    number: int
    horse_name: str
    racecard_sha256: str
    pc_url: str | None
    sp_url: str | None
    pc_observed: bool = False
    sp_observed: bool = False

def _utc(t):
    if not isinstance(t, datetime) or t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("untrusted_utc_clock")
    return t.astimezone(timezone.utc)

def _canonical(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))+"\n").encode("utf8")

def atomic_seal(directory, filename, data):
    """Create immutable original by atomic no-overwrite hard link + fsync.

    Temporary source is on the same volume; os.link fails if destination exists.
    Existing data are not overwritten. On unsupported filesystems fail closed.
    """
    d = Path(directory)
    if not d.is_dir() or not re.fullmatch(r"[A-Za-z0-9_.-]+", filename):
        raise ValueError("bad_source_destination")
    if not isinstance(data, bytes) or not data:
        raise ValueError("bad_source_bytes")
    dest = d / filename
    if dest.exists():
        raise FileExistsError("original_already_exists")
    fd, name = tempfile.mkstemp(prefix=".sealed-", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.link(name, dest)
        if dest.read_bytes() != data:
            raise ValueError("sealed_source_mismatch")
        return {"source_sha256": sha256(data).hexdigest(), "bytes": len(data), "path": filename}
    finally:
        if os.path.exists(name):
            os.unlink(name)

def preflight(*, roster, prior_attempts, now, cutoff, channels=("PC", "SP")):
    """Reject unsupported, already attempted, or postcutoff profiles before work."""
    current = _utc(now)
    close = _utc(cutoff)
    if not isinstance(roster, RosterHorse):
        raise ValueError("unverified_roster_record")
    if not re.fullmatch(r"[0-9a-f]{64}", roster.racecard_sha256):
        raise ValueError("unverified_racecard_original")
    if not re.fullmatch(r"20\d\d-\d\d-\d\d", roster.meeting_date):
        raise ValueError("invalid_race_date")
    if current >= close or current.date().isoformat() > roster.meeting_date:
        raise ValueError("prerace_cutoff_expired")
    if not roster.horse_name or not (1 <= roster.race <= 12) or not (1 <= roster.number <= 18):
        raise ValueError("invalid_horse_identity")
    if not channels or len(channels) > 2 or len(set(channels)) != len(channels):
        raise ValueError("invalid_channel_order")
    sources = []
    for channel in channels:
        if channel not in ("PC", "SP"):
            raise ValueError("unknown_channel")
        url = roster.pc_url if channel == "PC" else roster.sp_url
        observed = roster.pc_observed if channel == "PC" else roster.sp_observed
        if not url or not observed or not official(channel, url):
            raise ValueError("unverified_official_roster_link")
        sources.append(Source(channel, url, True))
    attempts = tuple(prior_attempts)
    for a in attempts:
        if not isinstance(a, Attempt):
            raise ValueError("invalid_attempt_ledger")
        if a.race == roster.race and a.horse_number == roster.number and a.outcome == "VALIDATED":
            raise ValueError("horse_already_verified")
        if a.url in [s.url for s in sources]:
            raise ValueError("already_attempted_official_url")
    return {"schema": "kyoto_p1_fb_stage5_preflight.v1",
            "status": "DRY_RUN_ELIGIBLE_NOT_NETWORK_AUTHORIZATION",
            "horse": roster.horse_name, "race": roster.race, "number": roster.number,
            "roster_sha256": roster.racecard_sha256,
            "channels": [{"channel": s.channel, "url": s.url} for s in sources],
            "cutoff_utc": close.isoformat(), "asof_utc": current.isoformat(),
            "actual_network_requests": 0, "live_automatic_fallback_authorized": False,
            "prediction_ready": False, "training_ready": False}

def run_guarded_replay(*, folder, roster, now, cutoff, replay_transport,
                       parsers, prior_attempts=(), channels=("PC", "SP")):
    """Stage5 integrates canonical roster and stage4 with replay-only transport."""
    if not getattr(replay_transport, "offline_replay_only", False):
        raise ValueError("offline_replay_transport_only")
    gate = preflight(roster=roster, prior_attempts=prior_attempts,
                     now=now, cutoff=cutoff, channels=channels)
    sources = []
    for c in channels:
        sources.append(Source(c, roster.pc_url if c == "PC" else roster.sp_url, True))
    result = stage4_run(folder=folder, primary=sources[0],
                        secondary=sources[1] if len(sources) > 1 else None,
                        horse_name=roster.horse_name, race=roster.race,
                        number=roster.number, roster_sha=roster.racecard_sha256,
                        cutoff=cutoff, now=now, transport=replay_transport,
                        parsers=parsers, prior_attempts=tuple(prior_attempts),
                        source_writer=lambda path, body: atomic_seal(path.parent, path.name, body))
    out = Path(folder)
    gate_bytes = _canonical(gate)
    atomic_seal(out, "stage5_preflight.json", gate_bytes)
    result["stage5_gate_sha256"] = sha256(gate_bytes).hexdigest()
    result["stage5_offline_only"] = True
    # Raw source check after stage4; never accept a receipt without matching bytes.
    for attempt in result["attempts"]:
        if attempt["original_saved"]:
            p = out / ("original_" + attempt["channel"].lower() + ".html")
            if not p.is_file() or sha256(p.read_bytes()).hexdigest() != attempt["source_sha256"]:
                raise ValueError("original_receipt_mismatch")
    if result["actual_network_requests"] != 0:
        raise ValueError("unexpected_real_network")
    return result
