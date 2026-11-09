"""Stage5 OFFLINE replay through durable global one-shot request registry.

Important: replay object marker is a convention, NOT a network sandbox.
This module itself makes no HTTP calls; do not expose it as live transport.
"""
from datetime import timedelta

from diagnostics.jra_p1_fb_stage5_guarded_replay import (
    _utc, preflight, run_guarded_replay)
from diagnostics.jra_p1_fb_stage5_global_attempt_registry import Blocked, GlobalAttemptRegistry

def run_ledger_replay(*, folder, roster, now, cutoff, replay_transport,
                      parsers, ledger_path, prior_attempts=(),
                      channels=("PC","SP"), global_attempt_limit=24):
    if not getattr(replay_transport,"offline_replay_only",False):
        raise Blocked("offline_replay_transport_only")
    gate=preflight(roster=roster,prior_attempts=prior_attempts,
                   now=now,cutoff=cutoff,channels=channels)
    ledger=GlobalAttemptRegistry(ledger_path,max_attempts=global_attempt_limit)
    known={x["url"] for x in ledger.inventory()}
    if any(c["url"] in known for c in gate["channels"]):
        raise Blocked("url_already_reserved_in_global_ledger")
    reserved={}
    class ReplayWithLedger:
        offline_replay_only=True
        def __call__(self,channel,url):
            ix=len(reserved)
            expected=gate["channels"][ix] if ix<len(gate["channels"]) else None
            if not expected or expected["channel"]!=channel or expected["url"]!=url:
                raise Blocked("unexpected_channel_or_url")
            rid=ledger.reserve(channel=channel,url=url,
                               race_key=f"{roster.meeting_date}_KYOTO_{roster.race:02d}R",
                               horse_number=roster.number,
                               roster_sha=roster.racecard_sha256,
                               now=_utc(now)+timedelta(seconds=2*ix),
                               cutoff=cutoff,official_roster_observed=True)
            reserved[channel]=rid
            return replay_transport(channel,url)
    # A failed database reservation MUST stop; never treat it as HTTP failure
    # eligible for automatic backup. Stage4 preserves the error receipt first.
    result=run_guarded_replay(folder=folder,roster=roster,now=now,cutoff=cutoff,
                              replay_transport=ReplayWithLedger(),parsers=parsers,
                              prior_attempts=prior_attempts,channels=channels,
                              fatal_transport_exceptions=(Blocked,))
    for item in result["attempts"]:
        channel=item["channel"]
        if channel in reserved:
            ledger.attach_receipt(attempt_id=reserved[channel],detail=item["status"])
    result["global_reservations"]=len(reserved)
    result["global_ledger_offline_only"]=True
    return result
