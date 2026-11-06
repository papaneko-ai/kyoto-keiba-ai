"""P1-FB stage4: injected-transport source-first dry-run adapter.

NO real network implementation. Requires caller-supplied fake transport.
All runs are sandbox-only, never model/ledger adoption.
"""
from dataclasses import dataclass
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit
import json,re
from diagnostics.jra_p1_fb_request_budget_policy import Attempt,decision,official

CUTOFF=datetime(2026,11,7,tzinfo=timezone.utc)
MAX_BYTES=1_800_000
@dataclass(frozen=True)
class Source:
    channel:str
    url:str
    observed_roster_url:bool

@dataclass(frozen=True)
class Response:
    body:bytes
    status:int
    content_type:str
    final_url:str

def record(path,obj):
    path.write_text(json.dumps(obj,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf8")

def run(*,folder,primary,secondary,horse_name,race,number,roster_sha,
        cutoff=CUTOFF,now,transport,parsers,prior_attempts=()):
    """Exactly one primary and, if allowed, one alternate. No built-in URL opener.

    A previously created folder forbids a restart. Failure evidence is saved
    synchronously before any fallback is assessed, including HTTP errors.
    """
    dest=Path(folder)
    if dest.exists():raise ValueError("immutable_incident_directory_already_exists")
    if (not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None
        or cutoff.tzinfo is None or cutoff.utcoffset() is None):
        raise ValueError("untrusted_clock")
    if (not horse_name or not 1<=race<=12 or not 1<=number<=18
        or not re.fullmatch("[0-9a-f]{64}",roster_sha)
        or not official(primary.channel,primary.url)):
        raise ValueError("unverified_primary_identity_or_url")
    if secondary is not None and (secondary.channel==primary.channel
       or not official(secondary.channel,secondary.url)):
        raise ValueError("invalid_backup_channel_or_url")
    urls=[a.url for a in prior_attempts]
    if primary.url in urls or (secondary and secondary.url in urls):
        raise ValueError("already_requested_url")
    if now.astimezone(timezone.utc)>=cutoff.astimezone(timezone.utc):
        raise ValueError("prediction_cutoff_passed")
    if not isinstance(transport,object) or not callable(transport):
        raise ValueError("mock_transport_required")
    if not primary.observed_roster_url:
        raise ValueError("primary_roster_url_not_observed")
    dest.mkdir(parents=True)
    info={"schema":"p1_fb_stage4_mock_transport.v1","status":"BLOCKED",
       "horse":horse_name,"race":race,"number":number,"roster_sha":roster_sha,
       "attempts":[],"incidents":[],"selected":None,"mock_transport_only":True,
       "actual_network_requests":0,"live_automatic_fallback_authorized":False,
       "training_ready":False,"prediction_ready":False}
    attempts=list(prior_attempts)
    def commit():record(dest/"receipt.json",info)
    commit()
    def attempt(source,t):
        index=len(info["attempts"])+1
        e={"channel":source.channel,"url":source.url,"status":"BLOCKED",
           "original_saved":False,"receipt_saved":True,"attempt_index":index}
        info["attempts"].append(e);commit()
        outcome="HTTP_FAILED"
        try:
            if t>=cutoff:raise ValueError("cutoff_before_mock_request")
            response=transport(source.channel,source.url)
            if not isinstance(response,Response):raise ValueError("invalid_mock_response")
            final=urlsplit(response.final_url)
            if (response.status!=200 or not isinstance(response.body,bytes)
                or not 0<len(response.body)<=MAX_BYTES or "html" not in response.content_type.lower()
                or not official(source.channel,response.final_url)
                or response.final_url!=source.url):
                raise ValueError("untrusted_mock_http_response")
            digest=sha256(response.body).hexdigest()
            (dest/("original_"+source.channel.lower()+".html")).write_bytes(response.body)
            e.update(original_saved=True,source_sha256=digest,bytes=len(response.body),
                captured_at_utc=t.astimezone(timezone.utc).isoformat())
            commit()  # raw source sealed BEFORE parser
            outcome="PARSER_FAILED"
            parser=parsers[source.channel]
            parsed=parser(response.body,horse_name)
            if (not isinstance(parsed,dict) or parsed.get("horse_name")!=horse_name
                or not isinstance(parsed.get("prior_rows"),list)
                or parsed.get("invalid_rows") or
                parsed.get("source_sha256",digest)!=digest):
                raise ValueError("parser_identity_or_history_invalid")
            if any(not isinstance(row,dict) or row.get("date","9999")>="2026-11-07"
                   for row in parsed["prior_rows"]):
                raise ValueError("postcutoff_race_in_prior_rows")
            e["status"]="VALIDATED";e["prior_rows"]=len(parsed["prior_rows"])
            e["normalized_sha256"]=sha256(json.dumps(parsed["prior_rows"],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            commit();outcome="VALIDATED"
        except Exception as exc:
            e["status"]="QUARANTINED";e["reason"]=type(exc).__name__+":"+str(exc)[:180]
            info["incidents"].append({"channel":source.channel,"reason":e["reason"],
                "source_sha256":e.get("source_sha256"),"open":True})
            commit()
        attempts.append(Attempt(source.channel,source.url,t,race,number,outcome,
            e["original_saved"],True))
        return outcome
    outcome=attempt(primary,now)
    if outcome=="VALIDATED":
        info["status"]="PRIMARY_VALID_MOCK_ONLY";info["selected"]=primary.channel
        commit();return info
    if secondary is None:
        info["status"]="PRIMARY_FAILED_NO_BACKUP";commit();return info
    policy=decision(failed_channel=primary.channel,failed_url=primary.url,
       backup_channel=secondary.channel,backup_url=secondary.url,race=race,
       horse_number=number,horse_name=horse_name,roster_sha256=roster_sha,
       observed_backup_link=secondary.observed_roster_url,attempts=attempts,
       asof_utc=now+timedelta(seconds=2),cutoff_utc=cutoff,simulate_authorized=True)
    info["fallback_policy"]=policy
    commit()
    if policy["status"]!="DRY_RUN_ELIGIBLE":
        info["status"]="FALLBACK_BLOCKED";commit();return info
    backup_outcome=attempt(secondary,now+timedelta(seconds=2))
    if backup_outcome=="VALIDATED":
        info["selected"]=secondary.channel
        info["status"]="FALLBACK_VALID_PRIMARY_INCIDENT_OPEN_MOCK_ONLY"
    else:info["status"]="BOTH_FAILED_QUARANTINED"
    commit();return info
