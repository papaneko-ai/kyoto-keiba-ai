"""P1-FB stage5 real-time request gate: offline verification, live network hard-disabled.

Design-purpose component: real monotonic/UTC clock injection is measured here,
but no socket, HTTP, redirects, or remote fetching is performed. A request
decision is NOT permission to fetch. Legal/JRA approval & multi-host ledger
remain independent gates. Can be invoked with a fake clock to inject failures.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urlsplit,parse_qs
import re

from diagnostics.jra_p1_fb_request_budget_policy import official
from diagnostics.jra_p1_fb_stage5_global_attempt_registry import GlobalAttemptRegistry,Blocked

@dataclass(frozen=True)
class RequestEvidence:
    channel: str
    official_url: str
    race_key: str
    horse_number: int
    horse_name: str
    source_roster_sha256: str
    roster_link_observed: bool
    cutoff_utc: datetime
    evidence_captured_utc: datetime

class LiveNetworkDisabled(Blocked):
    pass

def strict_official_url(channel,url):
    if not isinstance(url,str) or not official(channel,url):
        return False
    u=urlsplit(url)
    if u.username or u.password or u.port is not None or not u.hostname:
        return False
    if u.netloc.lower()!=u.hostname.lower():
        return False
    if u.query.count("CNAME=")!=1 or "&" in u.query or ";" in u.query:
        return False
    q=parse_qs(u.query,keep_blank_values=True)
    if set(q)!={"CNAME"} or len(q["CNAME"])!=1:
        return False
    token=q["CNAME"][0]
    return re.fullmatch(r"(?:pw|sj)[0-9A-Za-z]+/[0-9A-Za-z]+",token) is not None

def utc(t):
    if not isinstance(t,datetime) or t.tzinfo is None or t.utcoffset() is None:
        raise Blocked("untrusted_wall_clock")
    return t.astimezone(timezone.utc)

def verify_request(evidence,wall_clock_now):
    """Pure preflight; no ledger mutation and no network activity."""
    if not isinstance(evidence,RequestEvidence):
        raise Blocked("invalid_request_evidence")
    t=utc(wall_clock_now)
    expiry=utc(evidence.cutoff_utc)
    captured=utc(evidence.evidence_captured_utc)
    if not evidence.roster_link_observed or not re.fullmatch(r"[0-9a-f]{64}",evidence.source_roster_sha256):
        raise Blocked("missing_source_provenance")
    if not strict_official_url(evidence.channel,evidence.official_url):
        raise Blocked("untrusted_request_endpoint")
    match=re.fullmatch(r"(20\d{2}-\d{2}-\d{2})_KYOTO_(0[1-9]|1[0-2])R",evidence.race_key)
    if not match or type(evidence.horse_number) is not int or not 1<=evidence.horse_number<=18 or not evidence.horse_name.strip():
        raise Blocked("invalid_race_or_horse_identity")
    # Date parsing is explicit rather than lexicographical when building new schedules.
    date=datetime.fromisoformat(match.group(1)).date()
    if captured>=expiry or t>=expiry or t<captured:
        raise Blocked("source_future_or_prediction_cutoff")
    if t.date()>date:
        raise Blocked("race_day_expired")
    return {"status":"ELIGIBLE_FOR_OFFLINE_LEDGER_RESERVATION_ONLY",
            "race_key":evidence.race_key, "channel":evidence.channel,
            "url_sha256":sha256(evidence.official_url.encode("utf8")).hexdigest(),
            "current_utc":t.isoformat(),"roster_sha256":evidence.source_roster_sha256,
            "network_allowed":False,"actual_requests":0}

def reserve_offline_simulation(*,registry,evidence,clock,monotonic,
                               last_call_monotonic=None,wait_seconds=2.0):
    """Measure elapsed wall time without calling sleep or network.

    A caller can only proceed if at least two actual monotonic seconds elapsed
    between supplied request times; fake clock allows deterministic CI.
    The SQLite reservation remains consumed if the next phase crashes.
    """
    if not isinstance(registry,GlobalAttemptRegistry):
        raise Blocked("registry_not_verified")
    now=clock()
    permit=verify_request(evidence,now)
    measured=monotonic()
    if isinstance(measured,bool) or not isinstance(measured,(int,float)) or not 0<=measured<float("inf"):
        raise Blocked("invalid_monotonic_clock")
    if last_call_monotonic is not None and measured-last_call_monotonic<max(2.0,wait_seconds):
        raise Blocked("real_time_interval_not_elapsed")
    rid=registry.reserve(channel=evidence.channel,url=evidence.official_url,
        race_key=evidence.race_key,horse_number=evidence.horse_number,
        roster_sha=evidence.source_roster_sha256,now=now,
        cutoff=evidence.cutoff_utc,official_roster_observed=True)
    return {"reservation_id":rid,"monotonic_at_reserve":measured,
            "network_allowed":False,"actual_requests":0,
            "request_preflight":permit}

def deny_network_execution(*args,**kwargs):
    """The network boundary is intentionally NOT implemented/authorized."""
    raise LiveNetworkDisabled("live_jra_http_not_authorized_or_implemented")
