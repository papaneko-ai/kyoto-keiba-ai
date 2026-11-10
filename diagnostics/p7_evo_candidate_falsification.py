"""P7 research-only EVO-01..08 candidate generation and falsification.

All observations are synthetic or separately attested historical; this module
never reads JRA or promotes a model. Candidate scoring is fixed before labels.
"""
from __future__ import annotations
from math import isfinite
from hashlib import sha256
import json

class EvolutionRejected(ValueError): pass

EVO_RULES={
 "EVO-01":("recent_form",0.5),
 "EVO-02":("speed_index",0.5),
 "EVO-03":("jockey_index",0.5),
 "EVO-04":("draw_advantage",0.5),
 "EVO-05":("track_fit",0.5),
 "EVO-06":("pace_fit",0.5),
 "EVO-07":("training_index",0.5),
 "EVO-08":("value_signal",0.5),
}
def _canonical(v):
 return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def validate(races):
 if type(races) is not list or len(races)<6:
  raise EvolutionRejected("at_least_six_chronological_races_required")
 ids=set();last=None
 for race in races:
  if type(race) is not dict or set(race)!={"race_id","cutoff_utc","pre_result_frozen","runners","winner"}:
   raise EvolutionRejected("race_schema_invalid")
  key=race["race_id"]
  if type(key) is not str or not key or key in ids:
   raise EvolutionRejected("duplicate_race_id")
  ids.add(key)
  from diagnostics.p3_research_calibration import timestamp
  t=timestamp(race["cutoff_utc"])
  if last is not None and t<=last:
   raise EvolutionRejected("chronological_order_invalid")
  last=t
  if race["pre_result_frozen"] is not True:
   raise EvolutionRejected("unfrozen_prediction_features")
  rows=race["runners"]
  if type(rows) is not list or len(rows)<2:
   raise EvolutionRejected("runners_invalid")
  numbers=set()
  for row in rows:
   if type(row) is not dict or set(row)!={"horse_number","features"}:
    raise EvolutionRejected("runner_schema_invalid")
   n=row["horse_number"];f=row["features"]
   if type(n) is not int or n<1 or n>18 or n in numbers:
    raise EvolutionRejected("horse_number_invalid")
   numbers.add(n)
   if type(f) is not dict or set(f)!=set(x[0] for x in EVO_RULES.values()):
    raise EvolutionRejected("feature_set_incomplete")
   if any(type(v) not in (int,float) or not isfinite(v) or not 0<=v<=1 for v in f.values()):
    raise EvolutionRejected("feature_out_of_range")
  if type(race["winner"]) is not int or race["winner"] not in numbers:
   raise EvolutionRejected("winner_missing")
 return races

def _candidate(race,feature,threshold):
 ranked=sorted(race["runners"],key=lambda r:(-r["features"][feature],r["horse_number"]))
 best=ranked[0]
 if best["features"][feature]<threshold:
  return None
 return best["horse_number"]

def discover_and_refute(races,*,train_count):
 """Predeclared candidate family; independent holdout never selects rules.

 A rule is REFUTED if its held-out win rate fails to beat the fixed,
 predeclared 1/field-size random-choice baseline. No model is deployed.
 """
 validate(races)
 if type(train_count) is not int or train_count<3 or train_count>len(races)-3:
  raise EvolutionRejected("train_holdout_minimum_three_each")
 training=races[:train_count];holdout=races[train_count:]
 result=[]
 for rule,(feature,threshold) in EVO_RULES.items():
  def assess(group):
   eligible=[(r,_candidate(r,feature,threshold)) for r in group]
   chosen=[(r,n) for r,n in eligible if n is not None]
   hits=sum(r["winner"]==n for r,n in chosen)
   # Baseline uses the same eligible races, not an artificially diluted denominator.
   baseline=sum(1/len(r["runners"]) for r,n in chosen)/len(chosen) if chosen else None
   return {"races":len(group),"selected":len(chosen),"hits":hits,
           "win_rate":hits/len(chosen) if chosen else None,
           "random_baseline":baseline}
  a=assess(training);b=assess(holdout)
  refuted=(b["selected"]<3 or b["win_rate"]<=b["random_baseline"])
  result.append({"id":rule,"feature":feature,"threshold":threshold,
                 "training":a,"unseen_holdout":b,
                 "verdict":"REFUTED_OR_INSUFFICIENT" if refuted else "SURVIVED_SYNTHETIC_HOLDOUT_ONLY",
                 "deployable":False})
 return {"schema":"kyoto_p7_evo_eight_falsification.v1",
         "status":"RESEARCH_CANDIDATES_NOT_APPROVED",
         "candidate_ids":list(EVO_RULES),"candidate_count":len(result),
         "train_race_ids":[r["race_id"] for r in training],
         "holdout_race_ids":[r["race_id"] for r in holdout],
         "input_sha256":sha256(_canonical(races)).hexdigest(),
         "candidates":result,"auto_promote":False,
         "prediction_ready":False,"real_bet_authorized":False}
