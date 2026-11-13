"""R04: five distinct LAB model families using existing P3 chronology.

BC/Benter are market-free functional-form proxies, NOT exact published
algorithms. No real odds or JRA authenticity are claimed.
"""
from __future__ import annotations
from math import exp,fsum,log
from diagnostics.p3_offline_model_tournament import (
    TournamentRejected,_validate,_hash,audit_chronological_holdout,predict)

FAMILIES=("UNIFORM","PL_HARVILLE","BC_STYLE_PROXY","BENTER_STYLE_PROXY","ML_SOFTMAX")
PARAM_GRID={
 "UNIFORM":(None,),
 "PL_HARVILLE":(None,),
 "BC_STYLE_PROXY":(.5,1.,1.5,2.),
 "BENTER_STYLE_PROXY":(0.,.25,.5,.75,1.),
 "ML_SOFTMAX":tuple((s,d,f) for s in (.5,1.,1.5) for d in (-.5,0.,.5) for f in (-.5,0.,.5)),
}
def _softmax(scores):
    top=max(scores.values())
    w={key:exp(val-top) for key,val in scores.items()}
    total=fsum(w.values())
    return {key:w[key]/total for key in sorted(w)}

def pair_probabilities(snapshot,family,parameter=None):
    strengths,frames=_validate(snapshot)
    if family not in FAMILIES:raise TournamentRejected("unknown_r04_family")
    nums=sorted(strengths)
    pairs=[(a,b) for k,a in enumerate(nums) for b in nums[k+1:]]
    if family=="UNIFORM":return {p:1/len(pairs) for p in pairs}
    pl=predict(snapshot,"PL_BASE")["quinella"]
    base={tuple(x["pair"]):x["probability"] for x in pl}
    if family=="PL_HARVILLE":return base
    if family=="BC_STYLE_PROXY":
        if type(parameter) not in (int,float) or parameter not in (.5,1.,1.5,2.):
            raise TournamentRejected("r04_parameter_invalid")
        return _softmax({(a,b):parameter*(log(strengths[a])+log(strengths[b])) for a,b in pairs})
    if family=="BENTER_STYLE_PROXY":
        if type(parameter) not in (int,float) or parameter not in (0.,.25,.5,.75,1.):
            raise TournamentRejected("r04_parameter_invalid")
        products=_softmax({(a,b):log(strengths[a])+log(strengths[b]) for a,b in pairs})
        return _softmax({p:parameter*log(base[p])+(1-parameter)*log(products[p]) for p in pairs})
    if not(type(parameter) is tuple and len(parameter)==3
           and all(type(v) in (int,float) for v in parameter)
           and parameter[0] in (.5,1.,1.5) and parameter[1] in (-.5,0.,.5)
           and parameter[2] in (-.5,0.,.5)):
        raise TournamentRejected("r04_parameter_invalid")
    scale,spread,frame=parameter
    return _softmax({(a,b):scale*(log(strengths[a])+log(strengths[b]))
        +spread*abs(log(strengths[a])-log(strengths[b]))
        +frame*int(frames[a]==frames[b]) for a,b in pairs})

def train_and_compare(train,holdout,*,plan_locked_utc):
    baseline=audit_chronological_holdout(train,holdout,plan_locked_utc=plan_locked_utc)
    fits={};scores={}
    for family in FAMILIES:
        best=None
        grid=PARAM_GRID[family]
        for param in grid:
            losses=[]
            for item in train:
                q=pair_probabilities(item["snapshot"],family,param)
                losses.append(-log(q[tuple(item["winning_pair"])]))
            objective=fsum(losses)/len(losses)
            if best is None or objective<best[0]-1e-12:
                best=(objective,param)
        objective,param=best
        losses=[];briers=[]
        for item in holdout:
            q=pair_probabilities(item["snapshot"],family,param)
            win=tuple(item["winning_pair"])
            losses.append(-log(q[win]))
            briers.append(fsum((v-int(p==win))**2 for p,v in q.items()))
        fits[family]={"training_log_loss":objective,
            "selected_parameter":list(param) if type(param) is tuple else param,
            "training_candidates":len(grid)}
        scores[family]={"mean_multiclass_log_loss":fsum(losses)/len(losses),
            "mean_multiclass_brier":fsum(briers)/len(briers),"holdout_races":len(holdout)}
    body={"schema":"kyoto_r04_five_distinct_lab_models.v1",
        "families":list(FAMILIES),"training_races":len(train),
        "holdout_races":len(holdout),"plan_locked_utc":plan_locked_utc,
        "canonical_tournament_sha256":baseline["receipt_sha256"],
        "fitted_on_training_only":fits,"holdout_proper_scores":scores,
        "benter_bc_exact_published_formulas_claimed":False,
        "market_odds_were_used":False,"holdout_used_for_parameter_fitting":False,
        "holdout_winner_promoted_to_production":False,
        "official_jra_authenticated":False,"real_calibration_certified":False,
        "real_bet_authorized":False}
    return {**body,"receipt_sha256":_hash(body)}
