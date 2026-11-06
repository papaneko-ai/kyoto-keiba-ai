"""P1-FB deterministic OFFLINE request-budget policy; does not perform HTTP.

No automatic live failover is authorized. A DRY_RUN_ELIGIBLE result is not
permission to call the JRA. Previously queried URLs are never retried.
"""
from dataclasses import dataclass
from datetime import datetime,timezone,timedelta
from urllib.parse import urlsplit
import re
@dataclass(frozen=True)
class Attempt:
    channel:str
    url:str
    time_utc:datetime
    race:int
    horse_number:int
    outcome:str
    original_saved:bool
    receipt_saved:bool=True

HOSTS={"PC":("jra.jp","www.jra.go.jp"),"SP":("sp.jra.jp",)}
def official(channel,url):
    u=urlsplit(url)
    return (channel in HOSTS and u.scheme=="https" and
            u.hostname in HOSTS[channel] and u.path=="/JRADB/accessU.html"
            and u.query.startswith("CNAME=") and not u.fragment)
def decision(*,failed_channel,failed_url,backup_channel,backup_url,
             race,horse_number,horse_name,roster_sha256,observed_backup_link,
             attempts,asof_utc,cutoff_utc,simulate_authorized=False):
    """Return a status for a simulated fallback, never a network action."""
    def stop(why):return {"status":"BLOCKED","reason":why,"network_requests":0,
        "live_auto_fallback_authorized":False}
    if not simulate_authorized:return stop("experimental_only_not_authorized")
    if (failed_channel==backup_channel or failed_channel not in HOSTS
        or backup_channel not in HOSTS):return stop("channel_not_distinct")
    if not official(failed_channel,failed_url) or not official(backup_channel,backup_url):
        return stop("not_verified_official_endpoint")
    if not observed_backup_link:return stop("backup_link_not_proven_in_official_roster")
    if not horse_name or not 1<=race<=12 or not 1<=horse_number<=18 or not re.fullmatch("[0-9a-f]{64}",roster_sha256):
        return stop("identity_provenance_missing")
    if any(t.tzinfo is None or t.utcoffset() is None for t in (asof_utc,cutoff_utc)):
        return stop("naive_clock")
    now=asof_utc.astimezone(timezone.utc);cutoff=cutoff_utc.astimezone(timezone.utc)
    if now>=cutoff:return stop("prediction_cutoff_passed")
    relevant=[x for x in attempts if x.race==race and x.horse_number==horse_number]
    if len(relevant)!=1:return stop("expected_exactly_one_primary_attempt")
    first=relevant[0]
    if (first.channel!=failed_channel or first.url!=failed_url
        or first.outcome not in ("HTTP_FAILED","PARSER_FAILED","INVALID_SOURCE")
        or not first.receipt_saved
        or (first.outcome!="HTTP_FAILED" and not first.original_saved)):
        return stop("primary_failure_not_preserved")
    if any(x.url==backup_url for x in attempts):return stop("backup_url_already_attempted")
    if any(x.channel==backup_channel and x.race==race and x.horse_number==horse_number for x in attempts):
        return stop("backup_channel_already_attempted")
    if any(x.outcome=="VALIDATED" for x in relevant):return stop("already_verified")
    if any(x.time_utc.tzinfo is None or x.time_utc.utcoffset() is None for x in attempts):
        return stop("attempt_clock_unverifiable")
    if attempts and now-max(x.time_utc.astimezone(timezone.utc) for x in attempts)<timedelta(seconds=2):
        return stop("minimum_two_seconds_not_elapsed")
    return {"status":"DRY_RUN_ELIGIBLE","reason":"all_offline_guards_passed",
            "planned_channel":backup_channel,"race":race,"horse_number":horse_number,
            "failed_channel_incident_still_open":True,
            "network_requests":0,"live_auto_fallback_authorized":False}
