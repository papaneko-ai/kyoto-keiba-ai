"""R10: bounded comparison of existing P5 LAB allocations, never live advice.

The same immutable P5 ranking drives three predefined strategies. Estimate
error and odds shocks are scenario haircuts, not inferred real-market effects.
Worst-case loss is the full stake, not an asserted probability bound.
"""
from __future__ import annotations
import math
from diagnostics.p5_bounded_risk_capital_lab import (
    research_capital_control, CapitalRiskRejected, _digest)

PROFILES={
    "DEFENSIVE":{"exposure_fraction":.15,"max_race_fraction":.08,
                 "max_pair_fraction":.04,"max_pair_stake_yen":500,"downside_guard":.25},
    "BALANCED":{"exposure_fraction":.35,"max_race_fraction":.20,
                "max_pair_fraction":.12,"max_pair_stake_yen":2000,"downside_guard":.10},
    "CONCENTRATED":{"exposure_fraction":.65,"max_race_fraction":.40,
                    "max_pair_fraction":.25,"max_pair_stake_yen":5000,"downside_guard":.05},
}
class StrategyComparisonRejected(ValueError):pass

def compare_risk_strategies(ranking, *, probability_error=.08,
                            odds_downshift=.12, maximum_loss_yen=None):
    """Evaluate identical sealed ranking, deterministic risk stress and loss caps."""
    for name,v in (("probability_error",probability_error),
                   ("odds_downshift",odds_downshift)):
        if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<1:
            raise StrategyComparisonRejected("invalid_stress:"+name)
    if maximum_loss_yen is not None and (
            type(maximum_loss_yen) is not int or maximum_loss_yen<0
            or maximum_loss_yen%100):
        raise StrategyComparisonRejected("invalid_loss_ceiling")
    if type(ranking) is not dict:
        raise StrategyComparisonRejected("ranking_required")
    # Existing allocator independently verifies immutable digest and all caps.
    try:
        results={name:research_capital_control(ranking,**kwargs)
                 for name,kwargs in PROFILES.items()}
    except (CapitalRiskRejected,KeyError,TypeError,ValueError) as exc:
        raise StrategyComparisonRejected("sealed_ranking_rejected") from exc
    budget=ranking["daily_budget_ceiling_yen"]
    scenario_factor=(1-probability_error)*(1-odds_downshift)
    if not 0<scenario_factor<=1:raise StrategyComparisonRejected("invalid_scenario_factor")
    rows=[]
    for name,receipt in results.items():
        total=receipt["research_spent_yen"]
        stress_expected=0.; base_expected=0.; largest=0; ticket_count=0
        exposures=[]
        for race in receipt["selected"]:
            race_amount=race["race_exposure_yen"]
            exposures.append(race_amount)
            for ticket in race["tickets"]:
                stake=ticket["heuristic_stake_yen"]
                if stake==0:continue
                ticket_count+=1
                largest=max(largest,stake)
                net=ticket["stressed_ev_lower_per_1"]
                if type(net) not in (int,float) or not math.isfinite(net) or net<=-1:
                    raise StrategyComparisonRejected("invalid_source_stressed_ev")
                base_expected+=stake*net
                stress_expected+=stake*((1+net)*scenario_factor-1)
        if sum(exposures)!=total or total+receipt["unused_yen"]!=budget:
            raise StrategyComparisonRejected("allocation_reconciliation_failed")
        cap_ok=maximum_loss_yen is None or total<=maximum_loss_yen
        rows.append({"strategy":name,"receipt_sha256":receipt["capital_sha256"],
          "stake_yen":total,"unspent_yen":receipt["unused_yen"],
          "worst_case_loss_yen":total,"loss_ceiling_satisfied":cap_ok,
          "ticket_count":ticket_count,"race_count":len(exposures),
          "max_race_exposure_yen":max(exposures,default=0),
          "max_pair_exposure_yen":largest,
          "max_race_concentration_fraction":max(exposures,default=0)/total if total else 0.,
          "max_pair_concentration_fraction":largest/total if total else 0.,
          "baseline_stressed_expected_net_yen":round(base_expected,8),
          "scenario_expected_net_yen":round(stress_expected,8),
          "scenario_expected_net_after_haircuts_per_stake":
             round(stress_expected/total,8) if total else None,
          "risk_budget_100_yen_aligned":total%100==0,
          "actual_purchase_authorized":False})
    # Risk ordering explicitly reports feasibility; it does not pick the
    # highest backtested ROI or claim profitable real-race predictions.
    eligible=[r for r in rows if r["loss_ceiling_satisfied"]]
    safest=min(eligible,key=lambda r:(r["worst_case_loss_yen"],
                     r["max_race_concentration_fraction"],r["strategy"])) if eligible else None
    body={"schema":"kyoto_p5_r10_risk_strategy_comparison.v1",
      "source_ranking_sha256":ranking["ranking_sha256"],"source_scope":"LAB_ONLY",
      "daily_budget_ceiling_yen":budget,
      "probability_error_fraction":probability_error,
      "odds_downshift_fraction":odds_downshift,
      "scenario_factor":scenario_factor,
      "maximum_loss_ceiling_yen":maximum_loss_yen,
      "profiles":rows,"minimum_loss_strategy":safest["strategy"] if safest else None,
      "all_scenarios_profitable_claimed":False,"real_probability_calibrated":False,
      "real_market_verified":False,"real_paper_trade_recorded":False,
      "actual_purchase_authorized":False,"network_requests":0}
    return {**body,"comparison_sha256":_digest(body)}
