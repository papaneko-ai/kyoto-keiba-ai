"""P1-FB stage5 scheduled OFFLINE replay: real clock recheck before every fake request.

The only accepted backend is ScriptedOfflineTransport (in-memory fixtures).
Injected clock/sleep functions permit deterministic tests of elapsed time.
No HTTP client, socket, DNS resolver or enabled live transport exists here.
"""
from datetime import datetime, timezone
from math import isfinite
import time

from diagnostics.jra_p1_fb_stage5_guarded_replay import preflight
from diagnostics.jra_p1_fb_stage5_ledger_replay import run_ledger_replay
from diagnostics.jra_p1_fb_stage5_offline_http_envelope import ScriptedOfflineTransport
from diagnostics.jra_p1_fb_stage5_global_attempt_registry import Blocked
from diagnostics.jra_p1_fb_stage5_live_preflight_disabled import utc

class OfflineScheduledTransport:
    offline_replay_only=True
    def __init__(self,source,*,wall_clock,monotonic_clock,sleep,
                 cutoff,minimum_gap_seconds=2.0):
        if type(source) is not ScriptedOfflineTransport:
            raise Blocked("strict_in_memory_scripted_transport_required")
        if minimum_gap_seconds<2 or not isfinite(minimum_gap_seconds):
            raise Blocked("unsafe_requested_gap")
        self.source=source
        self.wall_clock=wall_clock
        self.monotonic_clock=monotonic_clock
        self.sleep=sleep
        self.cutoff=utc(cutoff)
        self.minimum_gap=minimum_gap_seconds
        self.last_monotonic=None
        self.last_wall=None
        self.observations=[]

    def observe(self,channel,url,idx):
        # All checks are before reserving URL and before handing over bytes.
        tick=self.monotonic_clock()
        if (type(tick) not in (int,float) or not isfinite(tick) or tick<0):
            raise Blocked("untrustworthy_monotonic_clock")
        if self.last_monotonic is not None:
            remaining=self.minimum_gap-(tick-self.last_monotonic)
            if remaining>0:
                # Never sleep past expiry based on the caller's old snapshot.
                if utc(self.wall_clock())>=self.cutoff:
                    raise Blocked("cutoff_before_second_request")
                self.sleep(remaining)
                tick=self.monotonic_clock()
                if type(tick) not in (int,float) or not isfinite(tick):
                    raise Blocked("untrustworthy_monotonic_clock")
            if tick-self.last_monotonic<self.minimum_gap:
                raise Blocked("monotonic_gap_not_satisfied")
        now=utc(self.wall_clock())
        if now>=self.cutoff:
            raise Blocked("cutoff_during_request_scheduling")
        if self.last_wall is not None and now<self.last_wall:
            raise Blocked("wall_clock_rolled_backward")
        self.last_monotonic=tick
        self.last_wall=now
        self.observations.append((channel,url,idx,now,tick))
        return now

    def __call__(self,channel,url):
        # This path is deliberately not callable before an observed reservation.
        if not self.observations or self.observations[-1][:2]!=(channel,url):
            raise Blocked("unobserved_scripted_request")
        if (channel,url) in getattr(self,"_consumed",set()):
            raise Blocked("duplicate_scripted_request")
        self._consumed=getattr(self,"_consumed",set())
        self._consumed.add((channel,url))
        return self.source(channel,url)

def run_scheduled_offline_replay(*, folder, roster, now, cutoff,
                                 scripted_transport, parsers, ledger_path,
                                 channels=("PC","SP"), prior_attempts=(),
                                 wall_clock=None, monotonic_clock=None,
                                 sleep=None, global_attempt_limit=24):
    """As-of proven by preflight; current-time safety checked at each fake request."""
    preflight(roster=roster, prior_attempts=prior_attempts,
              now=now,cutoff=cutoff,channels=channels)
    transport=OfflineScheduledTransport(
        scripted_transport,wall_clock=wall_clock or (lambda:datetime.now(timezone.utc)),
        monotonic_clock=monotonic_clock or time.monotonic,
        sleep=sleep or time.sleep,cutoff=cutoff)
    result=run_ledger_replay(
        folder=folder,roster=roster,now=now,cutoff=cutoff,
        replay_transport=transport,parsers=parsers,ledger_path=ledger_path,
        channels=channels,prior_attempts=prior_attempts,
        global_attempt_limit=global_attempt_limit,
        reservation_clock=transport.observe)
    result["monotonic_request_gap_test_only"]=True
    result["scheduled_offline_only"]=True
    result["measured_monotonic_seconds"]=[item[4] for item in transport.observations]
    result["network_requests"]=0
    return result
