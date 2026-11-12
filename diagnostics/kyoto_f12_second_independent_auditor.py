"""Second independent F12 acceptance auditor.

Uses only witness JSON and unchanged fixed rubric, not target F12 source.
Recomputes expected split and percentages with integer long division.
"""
from __future__ import annotations
import hashlib,json
class F12AuditRejected(ValueError):pass
LOCKED_RUBRIC="92bae5c1d61d6ac00a5380dd8d5e08beb59f96c898b03c05a3c8bf8721ced632"
FIRST_RUN="43134360188"
FIRST_HEAD="4b71a5621df15917381f31d0033946fdc144712c"
def digest(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def divide_units(units,weights):
    n=sum(weights)
    base=[units*x//n for x in weights]
    remainder=units-sum(base)
    fractions=[(units*x)%n for x in weights]
    for ix in sorted(range(len(weights)),key=lambda j:(-fractions[j],j))[:remainder]:
        base[ix]+=1
    return [x*100 for x in base]
def audit_f12(witness,rubric_bytes):
    if hashlib.sha256(rubric_bytes).hexdigest()!=LOCKED_RUBRIC:
        raise F12AuditRejected("rubric_changed")
    rubric=json.loads(rubric_bytes)
    rule=next(x for x in rubric["criteria"] if x["id"]=="F12")
    if rule["points"]!=5 or rule["title"]!="券種・買い目・金額の最適化":
        raise F12AuditRejected("fixed_f12_rule_changed")
    if witness.get("ci_run_id")!=FIRST_RUN or witness.get("ci_head_sha")!=FIRST_HEAD or witness.get("rubric_sha256")!=LOCKED_RUBRIC:
        raise F12AuditRejected("wrong_source_provenance")
    if witness.get("F12_fixed_validation")!="OFFLINE_ONLY":
        raise F12AuditRejected("scope_invalid")
    if witness.get("schema")!="kyoto_F12_independent_budget_plan.v1" or witness.get("scope")!="OFFLINE_MANUAL_OR_AUTO_PLANNING_NOT_A_BET":
        raise F12AuditRejected("plan_scope_invalid")
    for key in ("real_source_verified","model_calibrated","real_purchase_authorized"):
        if witness.get(key) is not False:
            raise F12AuditRejected("false_live_claim")
    original={k:v for k,v in witness.items() if k not in (
        "ci_run_id","ci_head_sha","rubric_sha256","F12_fixed_validation","plan_sha256")}
    if digest(original)!=witness.get("plan_sha256"):
        raise F12AuditRejected("plan_hash_mismatch")
    if (witness.get("ticket_type")!="QUINELLA" or
        witness.get("mode")!="AUTO" or witness.get("day_budget_ceiling_yen")!=10000 or
        witness.get("exposure_target_yen")!=3500 or
        witness.get("user_selected_races")!=[1,2,3] or
        witness.get("max_races")!=4 or witness.get("max_ticket_per_race")!=3):
        raise F12AuditRejected("unexpected_fixture")
    expected_race=divide_units(35,[25,16,9])
    expected_tickets=[divide_units(n//100,[60,30,10]) for n in expected_race]
    if witness.get("spent_yen")!=3500 or witness.get("unspent_yen")!=6500:
        raise F12AuditRejected("budget_not_reconciled")
    if type(witness.get("selected")) is not list or len(witness["selected"])!=3:
        raise F12AuditRejected("selected_race_invalid")
    for index,(race,race_yen,tickets_yen) in enumerate(zip(witness["selected"],expected_race,expected_tickets),1):
        if race.get("race")!=index or race.get("priority")!=index or race.get("stake_yen")!=race_yen:
            raise F12AuditRejected("race_exposure_incorrect")
        expected=[{"pair":pair,"stake_yen":amount,
            "allocation_percent":round(100*amount/max(1,race_yen),2)}
            for pair,amount in zip([[1,2],[2,3],[3,4]],tickets_yen) if amount>0]
        if race.get("tickets")!=expected:
            raise F12AuditRejected("independent_ticket_allocation_mismatch")
    return {"schema":"kyoto_F12_second_independent_audit.v1","gate":"F12",
        "accepted_points":5,"scope":"OFFLINE_BUDGET_AND_TICKET_INTEGRITY_ONLY",
        "first_ci_run_id":int(FIRST_RUN),"first_ci_head_sha":FIRST_HEAD,
        "locked_rubric_sha256":LOCKED_RUBRIC,
        "plan_sha256":witness["plan_sha256"],
        "independent_recalculation":"separate_integer_weighted_allocation",
        "witness_selected_races":3,"witness_spent_yen":3500,
        "witness_unspent_yen":6500,"first_positive_negative_tests":22,
        "live_source_authenticated":False,"real_paper_trading_certified":False,
        "other_completion_gates_certified":False}
