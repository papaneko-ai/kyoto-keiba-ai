"""G06 offline missing-market recovery plan; never guesses URLs or issues HTTP."""
from datetime import datetime, timedelta
MARKETS=("quinella","bracket_quinella")
CHANNELS=("PC","SP")
UNSAFE={"HTTP_403","HTTP_429","ACCESS_DENIED","FINAL_ODDS","CUTOFF",
 "IDENTITY_CONFLICT","SHA_MISMATCH","UNSAFE_REDIRECT","UNLICENSED_SUPPLEMENTAL","UNVERIFIED_ORIGINAL"}
GLOBAL_STOP={"HTTP_403","HTTP_429","ACCESS_DENIED","UNSAFE_REDIRECT","UNLICENSED_SUPPLEMENTAL"}
TRANSIENT={"TIMEOUT","HTTP_500","HTTP_502","HTTP_503","LINK_NOT_OBSERVED",
 "NAVIGATION_UNRESOLVED","CONNECTION_RESET"}

def _utc(s):
    if not isinstance(s,str):raise ValueError("utc_required")
    try:d=datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError as exc:raise ValueError("invalid_utc") from exc
    if d.tzinfo is None or d.utcoffset()!=timedelta(0):
        raise ValueError("utc_timezone_required")
    return d

def plan_gap_recovery(*,race_id,verified_market_receipts,official_links,
    attempt_history,now_utc,cutoff_utc,approved_supplemental=()):
    now,cutoff=_utc(now_utc),_utc(cutoff_utc)
    if not isinstance(race_id,str) or not race_id.strip():
        raise ValueError("race_id_required")
    if not isinstance(verified_market_receipts,dict) or set(verified_market_receipts)!=set(MARKETS):
        raise ValueError("exact_markets_required")
    if not isinstance(official_links,dict) or set(official_links)!=set(CHANNELS):
        raise ValueError("exact_official_channels_required")
    if not isinstance(attempt_history,(tuple,list)) or len(attempt_history)>100:
        raise ValueError("bounded_history_required")
    if not isinstance(approved_supplemental,(tuple,list)):
        raise ValueError("supplemental_registration_required")
    for channel in CHANNELS:
        if not isinstance(official_links[channel],bool):
            raise ValueError("official_link_observation_boolean_required")
    for src in approved_supplemental:
        if not isinstance(src,dict) or set(src)!={"id","observed_url","license_verified","automation_permitted"}:
            raise ValueError("supplemental_provenance_required")
        if not src["id"] or not src["observed_url"] or src["license_verified"] is not True or src["automation_permitted"] is not True:
            raise ValueError("supplemental_not_approved")
    known_ids={s["id"] for s in approved_supplemental}
    by_key={}
    for row in attempt_history:
        if not isinstance(row,dict) or set(row)!={"market","source","result","at_utc"}:
            raise ValueError("attempt_receipt_invalid")
        market,source,state=row["market"],row["source"],row["result"]
        if market not in MARKETS or source not in CHANNELS and source not in known_ids:
            raise ValueError("unregistered_attempt")
        stamp=_utc(row["at_utc"])
        if stamp>now:raise ValueError("future_attempt")
        if state not in UNSAFE|TRANSIENT|{"VERIFIED"}:
            raise ValueError("unrecognized_attempt_result")
        by_key.setdefault((market,source),[]).append((stamp,state))
    summary={"race_id":race_id,"items":{},"network_requests":0,
             "prediction_ready":False,"production_authorized":False}
    global_refusal=any(sorted(records)[-1][1] in GLOBAL_STOP for records in by_key.values())
    for market in MARKETS:
        proof=verified_market_receipts[market]
        if proof is not None:
            if not isinstance(proof,dict) or not all(proof.get(k) for k in ("sha256","captured_at_utc","channel")):
                raise ValueError("market_proof_incomplete")
            if proof["channel"] not in CHANNELS:raise ValueError("market_source_unverified")
            if _utc(proof["captured_at_utc"])>=cutoff:raise ValueError("market_proof_after_cutoff")
            summary["items"][market]={"state":"VERIFIED_KEEP","next_actions":[],
                                       "retained_sha256":proof["sha256"]}
            continue
        if global_refusal:
            summary["items"][market]={"state":"BLOCKED_WITH_EVIDENCE","next_actions":[],
                                       "blocked_sources":[{"source":"ALL","reason":"GLOBAL_ACCESS_REFUSAL"}]}
            continue
        candidates=[];blocked=[]
        for channel in CHANNELS:
            records=sorted(by_key.get((market,channel),[]))
            if records and records[-1][1] in UNSAFE:
                blocked.append({"source":channel,"reason":records[-1][1]})
                continue
            if now>=cutoff:
                blocked.append({"source":channel,"reason":"CUTOFF"})
                continue
            if not official_links[channel]:
                candidates.append({"source":channel,"action":"OBSERVE_INDEPENDENT_OFFICIAL_NAVIGATION",
                                    "requires_observed_url":True})
                continue
            if records and records[-1][1]=="VERIFIED":
                blocked.append({"source":channel,"reason":"MISSING_VALID_PROOF_RECHECK"})
                continue
            candidates.append({"source":channel,
                "action":"RETRY_OBSERVED_MARKET_ONLY" if records else "FETCH_OBSERVED_MARKET_ONLY",
                "requires_live_phase_recheck":True,"requires_observed_url":True})
        for src in approved_supplemental:
            records=sorted(by_key.get((market,src["id"]),[]))
            if records and records[-1][1] in UNSAFE:
                blocked.append({"source":src["id"],"reason":records[-1][1]})
            elif now<cutoff:
                candidates.append({"source":src["id"],"action":"CHECK_VERIFIED_SUPPLEMENTAL_PROVENANCE",
                                   "requires_live_phase_recheck":True,"requires_observed_url":True,
                                   "not_equivalent_to_official":True})
        summary["items"][market]={"state":"PENDING_RECOVERY" if candidates else "BLOCKED_WITH_EVIDENCE",
                                  "next_actions":candidates,"blocked_sources":blocked}
    summary["all_markets_verified"]=all(x["state"]=="VERIFIED_KEEP" for x in summary["items"].values())
    return summary
