"""P4-04 research-only downside, uncertainty and market-distortion audit.

A deliberately conservative diagnostic: no real market prices, no calibrated
probabilities and no model adoption are implied by a passing test.
"""
from __future__ import annotations
import hashlib,json,math
from decimal import Decimal
from diagnostics.p3_p6_research_no_bet import market_ev,ResearchRejected

class RiskRejected(ValueError):pass

def audit_market_risk(pair_probs,odds,*,probability_error_bound,odds_drift_fraction,
                      min_lower_net=0.0,maximum_exposure_fraction=0.25):
 """Robust return under adverse probability and odds shocks.

 p_lower=max(0,p-error), price_lower=price*(1-drift).
 This is a deterministic stress bound, NOT a statistical confidence interval.
 Entire market must be present, probabilities sum to one, odds >1.
 """
 for name,v,lo,hi in (("probability_error_bound",probability_error_bound,0,1),
                      ("odds_drift_fraction",odds_drift_fraction,0,1),
                      ("maximum_exposure_fraction",maximum_exposure_fraction,0,1)):
  if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<hi:
   raise RiskRejected(name+"_invalid")
 if type(min_lower_net) not in (int,float) or not math.isfinite(min_lower_net) or not -1<=min_lower_net<=10:
  raise RiskRejected("min_lower_net_invalid")
 try:
  rows=market_ev(pair_probs,odds)
 except ResearchRejected as exc:
  raise RiskRejected(str(exc)) from exc
 risk=[]
 for row in rows:
  p=row["theoretical_probability"]
  o=float(Decimal(row["decimal_odds"]))
  lower_p=max(0,p-probability_error_bound)
  lower_o=o*(1-odds_drift_fraction)
  lower_net=lower_p*lower_o-1
  implied=1/o
  edge=p-implied
  risk.append({"pair":list(row["pair"]),"model_probability":p,
               "market_implied_probability_unadjusted":implied,
               "probability_minus_implied":edge,
               "model_expected_net":row["expected_net_per_1"],
               "stressed_probability_lower":lower_p,
               "stressed_decimal_odds_lower":lower_o,
               "stressed_expected_net_lower":lower_net,
               "passes_stress_gate":lower_net>min_lower_net})
 # Market overround is only a descriptive unadjusted inverse-odds sum;
 # pari-mutuel quinella pricing is not a direct bookmaker probability.
 overround=math.fsum(1/float(Decimal(r["decimal_odds"])) for r in rows)
 # Exposure is advisory; never emit stake or actionable ticket.
 payload={"schema":"kyoto_p4_research_downside_market_distortion.v1",
          "classification":"RESEARCH_STRESS_NOT_CALIBRATED_NOT_LIVE",
          "pairs":risk,"market_inverse_odds_sum":overround,
          "market_inverse_odds_sum_interpretation":"DESCRIPTIVE_ONLY_NOT_TAKEOUT",
          "bounds":{"probability_error_bound":probability_error_bound,
                    "odds_drift_fraction":odds_drift_fraction,
                    "min_lower_net":min_lower_net,
                    "maximum_exposure_fraction":maximum_exposure_fraction},
          "stress_survivors":sum(r["passes_stress_gate"] for r in risk),
          "live_prediction_ready":False,"stake_recommendation_yen":0,
          "live_bet_authorized":False,"real_operational_score_eligible":False}
 digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
 return {**payload,"sha256":digest}
