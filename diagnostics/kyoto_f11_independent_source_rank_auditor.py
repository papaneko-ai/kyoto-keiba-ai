"""Second independent F11 acceptance: no import of P4/P5/F11/F12 implementation.

Audits an *existing GitHub Actions original-byte-bound LAB* witness by
recomputing source receipt SHA256, conservative race and ticket ranks,
explanations, timing, and F12 budget invariants separately.
Only proves an isolated deterministic planning pipeline, not real JRA source
identity, calibrated probabilities, performance or a paper-trade.
"""
from __future__ import annotations
import hashlib,json,math
from datetime import datetime
class AuditRejected(ValueError):pass
def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,
        separators=(",",":"),allow_nan=False).encode()).hexdigest()
def audit(witness,rubric):
    if hashlib.sha256(rubric).hexdigest()!="92bae5c1d61d6ac00a5380dd8d5e08beb59f96c898b03c05a3c8bf8721ced632":
        raise AuditRejected("rubric_changed")
    r=json.loads(rubric)
    f11=next(x for x in r["criteria"] if x["id"]=="F11")
    if f11["points"]!=5 or f11["title"]!="推奨レースの選択と説明":
        raise AuditRejected("rubric_f11_changed")
    if witness.get("schema")!="kyoto_F11_F12_source_bound_offline_witness.v1":
        raise AuditRejected("witness_schema")
    if (witness.get("ci_run_id")!="43135357123" or
        witness.get("ci_head_sha")!="76b9fe33e4ce29959e6f3f39b0d1136127a46003"):
        raise AuditRejected("source_ci_provenance")
    if (witness.get("source_scope")!="SYNTHETIC_P4_MARKET_NOT_AUTHENTICATED_JRA" or
        witness.get("official_pre_race_data_verified") is not False or
        witness.get("actual_paper_trade_registered") is not False or
        witness.get("real_purchase_authorized") is not False):
        raise AuditRejected("false_live_claim")
    rows=witness.get("p4_comparisons")
    rec=witness.get("f11")
    hand=witness.get("f12_handoff")
    if type(rows) is not list or len(rows)!=4 or type(rec) is not dict or type(hand) is not dict:
        raise AuditRejected("source_shape")
    if rec.get("f11_sha256")!=digest({k:v for k,v in rec.items() if k!="f11_sha256"}):
        raise AuditRejected("f11_digest_tampered")
    if rec.get("scope")!="LAB_SOURCE_BOUND_P4_AND_SYNTHETIC_MODELS_NOT_JRA_AUTHENTICATED":
        raise AuditRejected("f11_scope")
    for key in ("source_jra_authenticated","confidence_calibrated","virtual_bets_frozen","real_purchase_authorized"):
        if rec.get(key) is not False:
            raise AuditRejected("f11_false_live_claim")
    start=datetime.fromisoformat(rec["source_observed_utc"].replace("Z","+00:00"))
    end=datetime.fromisoformat(rec["decision_cutoff_utc"].replace("Z","+00:00"))
    if (end-start).total_seconds()!=300 or rec.get("source_age_seconds")!=300:
        raise AuditRejected("freshness_invalid")
    if rec.get("ticket_type")!="QUINELLA" or rec.get("max_races")!=3 or rec.get("max_tickets_per_race")!=2:
        raise AuditRejected("ranking_contract_changed")
    expected=[]
    for c in rows:
        if type(c) is not dict or c.get("schema")!="kyoto_p4_source_bound_model_market_comparison.v1":
            raise AuditRejected("p4_schema")
        if c.get("comparison_sha256")!=digest({k:v for k,v in c.items() if k!="comparison_sha256"}):
            raise AuditRejected("p4_source_receipt_tampered")
        if (c.get("scope")!="STRICT_ORIGINAL_CONTENT_PLUS_SYNTHETIC_MODEL_ONLY" or
            c.get("source_official_origin_authenticated") is not False or
            c.get("model_externally_calibrated") is not False):
            raise AuditRejected("p4_false_live_origin")
        market=c.get("markets",{}).get("QUINELLA",{})
        pairs=market.get("research_model_expected_net")
        if type(pairs) is not list or len(pairs)!=market.get("full_pair_count"):
            raise AuditRejected("market_incomplete")
        eligible=[]
        seen=set()
        for p in pairs:
            if set(p)!={"pair","stressed_net_lower","expected_net_per_unit"}:
                raise AuditRejected("invalid_pair")
            pair=p["pair"]
            ev=p["stressed_net_lower"]
            if (type(pair) is not list or len(pair)!=2 or
                any(type(k) is not int for k in pair) or pair[0]>=pair[1] or
                tuple(pair) in seen or type(ev) not in (int,float) or not math.isfinite(ev)):
                raise AuditRejected("bad_pair_or_ev")
            seen.add(tuple(pair))
            if ev>0:eligible.append((ev,pair))
        eligible.sort(key=lambda t:(-t[0],t[1]))
        if eligible:
            expected.append((eligible[0][0],c["race_date"],c["race"],c["comparison_sha256"],eligible[:2]))
    expected.sort(key=lambda t:(-t[0],t[1],t[2]))
    expected=expected[:3]
    chosen=rec.get("selected")
    if len(chosen)!=len(expected):
        raise AuditRejected("selected_count_wrong")
    for i,(got,item) in enumerate(zip(chosen,expected),1):
        best,date,race,sha,pairs=item
        if (got["rank"]!=i or got["race_date"]!=date or got["race"]!=race or
            got["source_p4_sha256"]!=sha or got["best_conservative_ev"]!=best or
            got["confidence"]!=0.75 or got["source_age_seconds"]!=300 or
            got["ticket_type"]!="QUINELLA"):
            raise AuditRejected("ranking_wrong")
        if set(got["explanation"])!={"expectation","confidence","freshness"}:
            raise AuditRejected("explanation_missing")
        if [t["pair"] for t in got["tickets"]]!=[pair for _,pair in pairs]:
            raise AuditRejected("ranked_ticket_pair_wrong")
        weights=[t["weight"] for t in got["tickets"]]
        if any(type(w) is not int or not 1<=w<=100 for w in weights):
            raise AuditRejected("invalid_ticket_weights")
    if hand.get("f11_source_sha256")!=rec["f11_sha256"]:
        raise AuditRejected("handoff_not_bound")
    plan=hand.get("f12_plan",{})
    if (hand.get("scope")!="LAB_RANKING_TO_BUDGET_ONLY_NO_LIVE_FREEZE" or
        hand.get("actual_purchase_authorized") is not False or
        hand.get("virtual_trade_frozen") is not False or
        plan.get("day_budget_ceiling_yen")!=10000 or
        plan.get("exposure_target_yen")!=3500 or
        plan.get("spent_yen")!=3500 or
        plan.get("unspent_yen")!=6500):
        raise AuditRejected("budget_or_handoff_wrong")
    if plan.get("plan_sha256")!=digest({k:v for k,v in plan.items() if k!="plan_sha256"}):
        raise AuditRejected("plan_tampered")
    if len(plan["selected"])!=3 or any(r["race"]!=i for i,r in enumerate(plan["selected"],1)):
        raise AuditRejected("plan_selected_wrong")
    spent=0
    for race in plan["selected"]:
        cost=sum(t["stake_yen"] for t in race["tickets"])
        if cost!=race["stake_yen"] or any(t["stake_yen"]<=0 or t["stake_yen"]%100 for t in race["tickets"]):
            raise AuditRejected("ticket_stakes_wrong")
        spent+=cost
    if spent!=3500:
        raise AuditRejected("overspend_or_missing_stake")
    return {
     "schema":"kyoto_F11_second_independent_acceptance.v1",
     "gate":"F11","accepted_points":5,
     "scope":"OFFLINE_RECOMMENDATION_RANKING_EXPLANATIONS_ONLY",
     "first_ci_run_id":43135357123,"first_ci_head_sha":"76b9fe33e4ce29959e6f3f39b0d1136127a46003",
     "p4_source_receipts_checked":len(rows),
     "f11_ranking_sha256":rec["f11_sha256"],
     "f12_plan_sha256":plan["plan_sha256"],
     "ranked_races":len(expected),
     "manual_selection_supported_by_test_suite":True,
     "confidence_is_calibrated":False,
     "live_official_jra_origin_verified":False,
     "real_paper_trade_or_real_purchase_authorized":False,
     "independent_live_operation_verified":False
    }
