"""Offline only: model dual-source decisions without network requests."""

from dataclasses import dataclass

@dataclass(frozen=True)
class ChannelResult:
    channel: str
    verified: bool
    source_sha256: str
    horse: str
    asof_utc: str
    error: str = ""

def choose(primary, secondary=None):
    if primary.channel not in ("PC", "SP"):
        raise ValueError("invalid_primary")
    if primary.verified:
        return primary.channel
    if secondary is None:
        return None
    if secondary.channel not in ("PC", "SP") or secondary.channel == primary.channel:
        raise ValueError("invalid_fallback_channel")
    if primary.horse != secondary.horse:
        raise ValueError("horse_identity_conflict")
    return secondary.channel if secondary.verified else None
