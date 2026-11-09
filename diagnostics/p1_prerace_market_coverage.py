"""P1 offline completeness audit: never authorizes an actual race prediction.

Structural quinella coverage is necessary but not sufficient for a real
market: independently validated official provenance, withdrawals, prices,
timing, official sales status and calibration are still required.
"""
from itertools import combinations
from math import isfinite


class MarketCoverageRejected(ValueError):
    pass


def inspect_quinella_coverage(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get("schema") != "kyoto_p1_prerace_snapshot.v1":
        raise MarketCoverageRejected("snapshot_schema_invalid")
    runners = snapshot.get("runners")
    if not isinstance(runners, list) or not 2 <= len(runners) <= 18:
        raise MarketCoverageRejected("runner_count_invalid")
    numbers = [r.get("number") for r in runners if isinstance(r, dict)]
    if len(numbers) != len(runners) or any(type(n) is not int or not 1 <= n <= 18 for n in numbers) or len(set(numbers)) != len(numbers):
        raise MarketCoverageRejected("runner_identity_invalid")
    expected = set(combinations(sorted(numbers), 2))
    odds = snapshot.get("odds")
    if not isinstance(odds, list):
        raise MarketCoverageRejected("market_array_invalid")
    seen = set()
    for row in odds:
        if not isinstance(row, dict):
            raise MarketCoverageRejected("market_row_invalid")
        a,b,price = row.get("first"),row.get("second"),row.get("decimal")
        if type(a) is not int or type(b) is not int or a == b:
            raise MarketCoverageRejected("pair_invalid")
        pair = tuple(sorted((a,b)))
        if pair not in expected:
            raise MarketCoverageRejected("unknown_pair")
        if pair in seen:
            raise MarketCoverageRejected("duplicate_pair")
        seen.add(pair)
        if type(price) not in (float,int) or not isfinite(price) or not 1 < price < 100000:
            raise MarketCoverageRejected("price_invalid")
    missing = sorted(expected - seen)
    return {"schema":"kyoto_p1_quinella_coverage_only.v1",
            "race": snapshot.get("race"),"runner_count":len(numbers),
            "expected_quinella_pairs":len(expected),
            "observed_quinella_pairs":len(seen),
            "missing_quinella_pairs":[list(x) for x in missing],
            "market_completeness": "STRUCTURAL_COMPLETE" if not missing else "INCOMPLETE",
            "bracket_market_verified":False,
            "official_source_verified":False,
            "withdrawals_verified":False,
            "market_sales_status_verified":False,
            "calibrated_model_verified":False,
            "prediction_ready":False,
            "actual_orders_authorized":False,
            "network_requests":0}
