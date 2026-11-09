"""Offline P1 dual-market audit; synthetic/claimed records never authorize wagers.

A bracket pair remains possible if it can be formed by two distinct active
horses. This is a structural check, not a claim about official live sales.
"""
from itertools import combinations
from math import isfinite
from diagnostics.jra_p1_future_evidence import instant


class DualMarketRejected(ValueError):
    pass


def inspect_dual_market(snapshot, *, observed_utc):
    if not isinstance(snapshot, dict) or snapshot.get("schema") != "kyoto_p1_prerace_snapshot.v1":
        raise DualMarketRejected("snapshot_schema_invalid")
    runners = snapshot.get("runners")
    if not isinstance(runners, list) or not 2 <= len(runners) <= 18:
        raise DualMarketRejected("runner_roster_invalid")
    horses = {}
    for item in runners:
        if not isinstance(item, dict):
            raise DualMarketRejected("runner_invalid")
        number, bracket, state = item.get("number"), item.get("bracket"), item.get("status")
        if (type(number) is not int or not 1 <= number <= 18 or number in horses
                or type(bracket) is not int or not 1 <= bracket <= 8
                or state not in ("ACTIVE", "WITHDRAWN", "EXCLUDED")):
            raise DualMarketRejected("horse_identity_bracket_or_status_invalid")
        horses[number] = (bracket, state)
    active = {n: b for n, (b, state) in horses.items() if state == "ACTIVE"}
    if len(active) < 2:
        raise DualMarketRejected("too_few_active_horses")
    try:
        observed = instant(observed_utc)
        captured = instant(snapshot.get("captured_utc"))
        cutoff = instant(snapshot.get("prediction_cutoff_utc"))
        if not captured <= observed < cutoff:
            raise DualMarketRejected("observation_outside_prerace_window")
        statuses = snapshot.get("market_states")
        if not isinstance(statuses, dict) or set(statuses) != {"quinella", "bracket"}:
            raise DualMarketRejected("market_states_missing")
        for state in statuses.values():
            if not isinstance(state, dict) or state.get("sales") not in ("OPEN", "SUSPENDED", "NOT_OPEN", "CLOSED"):
                raise DualMarketRejected("market_sales_state_invalid")
            when = instant(state.get("observed_utc"))
            if not when <= captured or when >= cutoff:
                raise DualMarketRejected("market_state_time_invalid")
    except (ValueError, TypeError, AttributeError) as exc:
        if isinstance(exc, DualMarketRejected):
            raise
        raise DualMarketRejected("market_timestamp_invalid") from exc

    expected_horses = set(combinations(sorted(active), 2))
    # Derive same-bracket pairs only when at least two ACTIVE horses occupy it.
    expected_brackets = set()
    for x, y in expected_horses:
        expected_brackets.add(tuple(sorted((active[x], active[y]))))

    def audit(rows, expected, max_number, label):
        if not isinstance(rows, list):
            raise DualMarketRejected(label + "_array_invalid")
        seen = set()
        for item in rows:
            if not isinstance(item, dict):
                raise DualMarketRejected(label + "_row_invalid")
            a, b, price = item.get("first"), item.get("second"), item.get("decimal")
            if (type(a) is not int or type(b) is not int
                    or not 1 <= a <= max_number or not 1 <= b <= max_number):
                raise DualMarketRejected(label + "_pair_invalid")
            pair = tuple(sorted((a, b)))
            if pair not in expected:
                raise DualMarketRejected(label + "_unavailable_pair")
            if pair in seen:
                raise DualMarketRejected(label + "_duplicate_pair")
            if type(price) not in (int, float) or not isfinite(price) or not 1 < price < 100000:
                raise DualMarketRejected(label + "_price_invalid")
            seen.add(pair)
        return len(expected), len(seen), [list(x) for x in sorted(expected - seen)]

    q = audit(snapshot.get("odds"), expected_horses, 18, "quinella")
    b = audit(snapshot.get("bracket_odds"), expected_brackets, 8, "bracket")
    open_both = all(s["sales"] == "OPEN" for s in statuses.values())
    complete = not q[2] and not b[2]
    return {
        "schema": "kyoto_p1_dual_market_offline_audit.v1",
        "active_horses": len(active),
        "inactive_horses": len(horses) - len(active),
        "expected_quinella_pairs": q[0], "observed_quinella_pairs": q[1],
        "missing_quinella_pairs": q[2],
        "expected_bracket_pairs": b[0], "observed_bracket_pairs": b[1],
        "missing_bracket_pairs": b[2],
        "market_states_claimed_open": open_both,
        "structural_complete": complete,
        "status": "STRUCTURAL_COMPLETE_ONLY" if complete and open_both else "BLOCKED",
        "withdrawal_authenticity_verified": False,
        "official_source_verified": False,
        "sales_state_officially_verified": False,
        "legal_fetch_permission_verified": False,
        "calibrated_model_verified": False,
        "prediction_ready": False, "actual_orders_authorized": False,
        "network_requests": 0
    }
