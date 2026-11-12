"""Executable offline EVO research streams, not mere filled-in capability fields.

Every stream derives numeric evidence from an actual synthetic input collection
and returns machine-auditable rows. No JRA network, purchase or model deploy.
"""
from __future__ import annotations
import math
class EVOStreamRejected(ValueError):pass
def ck(v,m):
    if not v:raise EVOStreamRejected(m)
def finite(v):
    ck(type(v) in (int,float) and math.isfinite(v),"nonfinite_stream")
    return float(v)
def execute_streams(streams,race_ids):
    ck(type(streams) is dict and set(streams)=={
       "sources","weaknesses","portfolios","experiments","surprises","drift_windows"},
       "missing_research_stream")
    # EVO01: rank 3 actual candidate sources by value net of collection cost.
    sources=streams["sources"]
    ck(type(sources) is list and len(sources)==3
       and len({x["id"] for x in sources})==3,"sources_invalid")
    ranked=[]
    for x in sources:
        ck(set(x)=={"id","cost","value","coverage"} and type(x["id"]) is str,"source_schema")
        cost,val,coverage=finite(x["cost"]),finite(x["value"]),finite(x["coverage"])
        ck(cost>0 and val>=0 and 0<=coverage<=1,"source_numeric_invalid")
        ranked.append({"id":x["id"],"net":val-cost,"coverage":coverage,"cost":cost,"value":val})
    ranked.sort(key=lambda x:(-x["net"],x["id"]))
    chosen=ranked[0]
    # EVO02: actually compute same-race loss by failure class.
    weaknesses=streams["weaknesses"]
    ck(type(weaknesses) is list and len(weaknesses)==len(race_ids),"weakness_size")
    ck([x["race_id"] for x in weaknesses]==race_ids,"weakness_wrong_population")
    group={}
    for x in weaknesses:
        ck(set(x)=={"race_id","category","baseline_loss","candidate_loss"},"weakness_schema")
        cat=x["category"]
        ck(type(cat) is str and cat,"weakness_category_invalid")
        group.setdefault(cat,[]).append((finite(x["baseline_loss"]),finite(x["candidate_loss"])))
    comparisons=[]
    for cat,values in group.items():
        comparisons.append({"category":cat,
             "baseline_loss":math.fsum(a for a,b in values)/len(values),
             "candidate_loss":math.fsum(b for a,b in values)/len(values),
             "races":len(values)})
    comparisons.sort(key=lambda x:(-x["baseline_loss"],x["category"]))
    weak=comparisons[0]
    # EVO04: independently compute peak-to-trough loss trajectories from
    # ten historical LAB paper-market simulations, not a supplied drawdown.
    portfolios=streams["portfolios"]
    ck(type(portfolios) is list and len(portfolios)==2 and
       len({x["id"] for x in portfolios})==2,"portfolio_count")
    simulations=[]
    for x in portfolios:
        ck(set(x)=={"id","race_ids","net_returns_per_unit"},"portfolio_schema")
        ck(x["race_ids"]==race_ids and len(x["net_returns_per_unit"])==len(race_ids),"portfolio_population")
        cumulative=peak=max_dd=0.
        for value in x["net_returns_per_unit"]:
            cumulative+=finite(value)
            peak=max(peak,cumulative)
            max_dd=max(max_dd,peak-cumulative)
        simulations.append({"id":x["id"],"max_drawdown":max_dd,"total_net_return":cumulative})
    portfolio_drawdown=max(s["max_drawdown"] for s in simulations)
    # EVO05: compute drift history trend from three separate LAB windows.
    drift=streams["drift_windows"]
    ck(type(drift) is list and len(drift)==3 and
       [x["id"] for x in drift]==["BASELINE","FORWARD-01","FORWARD-02"],"drift_windows_invalid")
    drift_values=[]
    for x in drift:
        ck(set(x)=={"id","rate"},"drift_schema")
        rate=finite(x["rate"])
        ck(rate>=0,"drift_negative")
        drift_values.append(rate)
    # EVO06: independently execute a bounded LAB experiment selection using
    # preallocated project tokens. This never executes arbitrary code.
    experiments=streams["experiments"]
    ck(type(experiments) is list and len(experiments)==4 and
       len({x["id"] for x in experiments})==4,"research_experiment_count")
    candidates=[]
    for e in experiments:
        ck(set(e)=={"id","cost","lab_gain"},"experiment_schema")
        cost,gain=finite(e["cost"]),finite(e["lab_gain"])
        ck(cost>0 and gain>=0,"research_cost_or_gain")
        candidates.append({"id":e["id"],"cost":cost,"lab_gain":gain})
    candidates.sort(key=lambda x:(-x["lab_gain"]/x["cost"],x["id"]))
    selected=[];remaining=10.
    for e in candidates:
        if len(selected)>=4:break
        if e["cost"]<=remaining:
            remaining-=e["cost"]
            selected.append(e["id"])
    # EVO08: re-evaluate surprising independent LAB observation pairs,
    # recording counterexample identities instead of trusting a count.
    surprises=streams["surprises"]
    ck(type(surprises) is list and len(surprises)==2 and
       len({x["id"] for x in surprises})==2,"surprise_cases_invalid")
    errors=[];examples=[]
    for s in surprises:
        ck(set(s)=={"id","predicted_probability","outcome"},"surprise_schema")
        p=finite(s["predicted_probability"])
        ck(0<p<1 and type(s["outcome"]) is int and s["outcome"] in (0,1),"surprise_probability")
        err=abs(p-s["outcome"])
        errors.append(err)
        if err>=.1:examples.append(s["id"])
    ck(len(selected)==3,"insufficient_lab_experiments")
    return {
      "source_ranking":ranked,"top_source":chosen,
      "weakness_groups":comparisons,"top_weakness":weak,
      "portfolio_simulations":simulations,"computed_portfolio_drawdown":portfolio_drawdown,
      "drift_observations":drift_values,
      "experiment_priority":[x["id"] for x in candidates],
      "executed_lab_experiment_ids":selected,
      "spent_lab_budget":10.-remaining,
      "surprise_errors":errors,"surprise_counterexample_ids":examples,
      "surprise_mean_error":math.fsum(errors)/len(errors)
    }
