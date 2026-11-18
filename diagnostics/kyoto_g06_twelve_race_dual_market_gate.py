"""G06 twelve-race paired market validation; strictly offline and evidence-only."""
from hashlib import sha256
from collections.abc import Mapping
from diagnostics.jra_market_source_chain import audit_source_originals

MARKETS=("quinella","bracket_quinella")
class G06Incomplete(ValueError):pass

def audit_twelve_races(races,*,provenance,expected_day):
    if provenance not in ("REAL_ARCHIVED_ORIGINAL","SYNTHETIC_OFFLINE_TEST"):
        raise G06Incomplete("provenance_required")
    if not isinstance(races,Mapping) or set(races)!=set(range(1,13)):
        raise G06Incomplete("exact_twelve_race_keys_required")
    if not isinstance(expected_day,str) or len(expected_day)!=8 or not expected_day.isdecimal():
        raise G06Incomplete("invalid_race_day")
    results=[]
    for race in range(1,13):
        item=races[race]
        if not isinstance(item,Mapping) or item.get("race_number")!=race or item.get("race_day")!=expected_day:
            raise G06Incomplete(f"race_{race:02d}_identity_mismatch")
        market=item.get("market_raw")
        if not isinstance(market,Mapping) or set(market)!=set(MARKETS):
            raise G06Incomplete(f"race_{race:02d}_both_market_originals_required")
        if any(not isinstance(market[k],bytes) for k in MARKETS) or sha256(market["quinella"]).digest()==sha256(market["bracket_quinella"]).digest():
            raise G06Incomplete(f"race_{race:02d}_duplicate_or_nonbyte_original")
        try:
            o=audit_source_originals(**dict(item))
            results.append({"race_number":race,"classification":o["classification"],
                "markets":o["markets"],"menu_sha256":o["menu_sha256"],
                "historical_final_quarantined":o["historical_final_quarantined"]})
        except Exception as exc:
            results.append({"race_number":race,"classification":"REJECTED_OR_UNVERIFIED",
                "error_class":type(exc).__name__,"error":str(exc)[:150]})
    live=sum(x["classification"]=="VALIDATED_LIVE_MARKETS_NOT_PREDICTION_RELEASED" for x in results)
    hist=sum(x["classification"]=="QUARANTINED_HISTORICAL_FINAL" for x in results)
    return {"schema":"kyoto_g06_twelve_race_dual_market_gate.v1","day":expected_day,
        "provenance_claim":provenance,"races_total":12,"live_source_validated_count":live,
        "historical_final_quarantined_count":hist,"rejected_count":12-live-hist,
        "all_twelve_structurally_valid":live+hist==12,
        "all_twelve_live_source_validated":live==12,
        "evidence_independently_verified":False,"g06_certified":False,
        "actual_wagers_enabled":False,"network_requests":0,"races":results}
