"""P1-03 controlled PC -> SP acquisition/fallback, using existing parsers.

No network capability is embedded: a caller must supply a fetch transport.
Production authorization and JRA origin are NOT attested by this code.
The CI transport is synthetic; do not score as live operational readiness.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from urllib.parse import urlsplit, parse_qs
import json, re
from diagnostics.jra_pc_sp_benchmark import reconcile_saved_racecards

class AcquisitionRejected(ValueError): pass

def _utc(value):
    try:
        if type(value) is not str: raise ValueError()
        t=datetime.fromisoformat(value.replace("Z","+00:00"))
        if t.utcoffset()!=timedelta(0): raise ValueError()
        return t
    except (ValueError,TypeError,AttributeError):
        raise AcquisitionRejected("UTC_timestamp_required")

def _url(raw,channel):
    if type(raw) is not str: raise AcquisitionRejected("observed_url_required")
    u=urlsplit(raw)
    q=parse_qs(u.query,strict_parsing=True,keep_blank_values=True)
    if (u.scheme!="https" or u.hostname!=("jra.jp" if channel=="PC" else "sp.jra.jp")
        or u.port is not None or u.username or u.password or u.fragment
        or u.path!="/JRADB/accessD.html" or set(q)!={"CNAME"} or len(q["CNAME"])!=1
        or not re.fullmatch(r"[A-Za-z0-9]+(?:/[A-Za-z0-9]+)?",q["CNAME"][0])):
        raise AcquisitionRejected("untrusted_or_unobserved_racecard_url")
    return raw

def controlled_racecard_fallback(*, meeting_date,race,cutoff_utc,observed_utc,
        independently_frozen_roster,observed_urls,fetcher,transport_scope):
    """Provider returns {'raw': bytes, 'captured_utc': str, 'final_url': str}.

    Executes at most one PC and then one SP fetch; verifies sha and exact
    externally frozen horse roster. Failed PC never silently becomes accepted
    unless SP passes the unchanged independent frozen reference.
    """
    if transport_scope not in ("LAB_SIMULATED_TRANSPORT","OPERATOR_SUPPLIED_TRANSPORT"):
        raise AcquisitionRejected("explicit_transport_scope_required")
    if not callable(fetcher): raise AcquisitionRejected("injected_fetcher_required")
    if type(race) is not int or not 1<=race<=12:
        raise AcquisitionRejected("race_number_invalid")
    start=_utc(observed_utc);cutoff=_utc(cutoff_utc)
    try:
        d=datetime.strptime(meeting_date,"%Y-%m-%d").date()
    except (TypeError,ValueError) as exc:raise AcquisitionRejected("race_day_invalid") from exc
    if d.isoformat()!=meeting_date or (cutoff+timedelta(hours=9)).date()!=d or start>=cutoff:
        raise AcquisitionRejected("meeting_day_or_cutoff_invalid")
    if type(observed_urls) is not dict or set(observed_urls)!={"PC","SP"}:
        raise AcquisitionRejected("both_independently_observed_links_required")
    urls={c:_url(observed_urls[c],c) for c in ("PC","SP")}
    if (type(independently_frozen_roster) is not dict or
        independently_frozen_roster.get("roster_verified") is not True or
        independently_frozen_roster.get("race_date")!=meeting_date or
        independently_frozen_roster.get("race_number")!=race):
        raise AcquisitionRejected("independent_reference_required")
    rows=independently_frozen_roster.get("runners")
    if (type(rows) is not list or not 2<=len(rows)<=18
        or any(type(x) is not dict or set(x)!={"horse_number","frame_number","horse_name"}
        for x in rows) or len({x["horse_number"] for x in rows})!=len(rows)):
        raise AcquisitionRejected("invalid_frozen_roster")
    evidence={}
    errors={}
    attempts=[]
    for channel in ("PC","SP"):
        attempts.append(channel)
        try:
            result=fetcher(channel,urls[channel])
            if type(result) is not dict or set(result)!={"raw","captured_utc","final_url"}:
                raise AcquisitionRejected("transport_receipt_schema_invalid")
            if _url(result["final_url"],channel)!=urls[channel]:
                raise AcquisitionRejected("redirect_or_navigation_mismatch")
            raw=result["raw"]
            if type(raw) is not bytes or not 0<len(raw)<=1_500_000:
                raise AcquisitionRejected("source_bytes_invalid")
            captured=_utc(result["captured_utc"])
            if captured>start or captured>=cutoff:
                raise AcquisitionRejected("post_cutoff_or_future_source")
            evidence[channel]={"raw":raw,"captured_utc":result["captured_utc"],
                               "sha256":sha256(raw).hexdigest()}
            check=reconcile_saved_racecards(
                {channel:evidence[channel]},independently_frozen_roster,
                meeting_date=meeting_date,race=race,
                cutoff_utc=cutoff_utc,observed_utc=observed_utc)
            if check["selected_channel"]==channel:
                # No further network is attempted after one verified match.
                chosen=channel
                break
            errors[channel]="parser_or_frozen_roster_mismatch"
        except (ValueError,TypeError,KeyError,OSError,UnicodeError) as exc:
            errors[channel]=str(exc)[:160] or type(exc).__name__
    else:
        chosen=None
    receipt={"schema":"kyoto_p1_pc_sp_acquisition_fallback.v1",
             "meeting_date":meeting_date,"race":race,
             "observed_utc":observed_utc,"cutoff_utc":cutoff_utc,
             "attempts":attempts,"selected_channel":chosen,
             "fallback_used":chosen=="SP",
             "source_sha256":{c:x["sha256"] for c,x in evidence.items()},
             "failed_channels":errors,
             "transport_scope":transport_scope,
             "result":"SAVED_ORIGINAL_ROSTER_MATCH" if chosen else "BLOCKED",
             "official_origin_independently_authenticated":False,
             "permission_independently_verified":False,
             "official_dual_market_verified":False,
             "real_prediction_authorized":False,
             "real_paper_trade_authorized":False,"actual_purchase_authorized":False}
    digest=sha256(json.dumps(receipt,sort_keys=True,ensure_ascii=False,
                   separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return {"receipt":{**receipt,"sha256":digest},
            "selected_original_bytes":evidence[chosen]["raw"] if chosen else None,
            "selected_original_sha256":evidence[chosen]["sha256"] if chosen else None}
