"""P1-FB: offline two-channel decision gate, never executes HTTP."""
from dataclasses import dataclass
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json,re

@dataclass(frozen=True)
class ChannelResult:
    channel:str
    verified:bool
    source_sha256:str
    horse:str
    asof_utc:str
    error:str=""
    race:int=0
    number:int=0
    roster_sha:str=""
    normalized_sha256:str=""
    url_verified:bool=False
    raw_saved:bool=False

def validate(item,cutoff):
    if item.channel not in ("PC","SP"):raise ValueError("invalid_channel")
    if not item.horse or not 1<=item.race<=12 or not 1<=item.number<=18:
        raise ValueError("horse_identity_missing")
    if not re.fullmatch("[0-9a-f]{64}",item.roster_sha):raise ValueError("roster_proof_missing")
    if not re.fullmatch("[0-9a-f]{64}",item.source_sha256):raise ValueError("source_proof_missing")
    stamp=datetime.fromisoformat(item.asof_utc.replace("Z","+00:00"))
    if stamp.tzinfo is None or cutoff.tzinfo is None or stamp.astimezone(timezone.utc)>=cutoff.astimezone(timezone.utc):
        raise ValueError("source_after_cutoff")
    if item.verified and (not item.url_verified or not item.raw_saved or
        not re.fullmatch("[0-9a-f]{64}",item.normalized_sha256)):
        raise ValueError("unproven_validation")

def choose(primary,secondary=None,*,cutoff,compare=False):
    validate(primary,cutoff)
    if secondary is not None:
        validate(secondary,cutoff)
        if secondary.channel==primary.channel:raise ValueError("not_cross_channel")
        if (secondary.horse,secondary.race,secondary.number,secondary.roster_sha)!=(
            primary.horse,primary.race,primary.number,primary.roster_sha):
            raise ValueError("horse_identity_conflict")
    if primary.verified and compare and secondary is not None and secondary.verified and (
        primary.normalized_sha256!=secondary.normalized_sha256):
        return None,"SOURCE_CONFLICT"
    if primary.verified:return primary.channel,"PRIMARY_VALID"
    if secondary is None:return None,"PRIMARY_FAILED"
    if secondary.verified:return secondary.channel,"FALLBACK_VALID_PRIMARY_STILL_BROKEN"
    return None,"BOTH_FAILED"
