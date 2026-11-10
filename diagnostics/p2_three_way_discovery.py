"""P2 research-only chronological discovery and independent feature-value audit.

This is a frozen hypothesis family, not a fitted live prediction model.
Outcomes are accessed only after the chronological split. Never treat a
self-attested pre-result flag as independent official JRA evidence.
"""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from itertools import combinations
import json,math

class DiscoveryRejected(ValueError):pass

def _utc(s):
 try:
  t=datetime.fromisoformat(s.replace("Z","+00:00"))
  if t.utcoffset()!=timezone.utc.utcoffset(None):raise ValueError("UTC required")
  return t
 except (TypeError,ValueError,AttributeError) as exc:
  raise DiscoveryRejected("cutoff_utc_invalid") from exc

def _digest(obj):
 return sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def _validate(races):
 if type(races) is not list or len(races)<9:
  raise DiscoveryRejected("at_least_nine_races_required")
 seen=set();last=None;features=None
 for r in races:
  if type(r) is not dict or set(r)!={"race_id","cutoff_utc","pre_result_frozen","horses","winner"}:
   raise DiscoveryRejected("race_schema_invalid")
  rid=r["race_id"];t=_utc(r["cutoff_utc"])
  if type(rid) is not str or not rid or rid in seen:raise DiscoveryRejected("duplicate_race_id")
  seen.add(rid)
  if last is not None and t<=last:raise DiscoveryRejected("time_not_strictly_increasing")
  last=t
  if r["pre_result_frozen"] is not True:raise DiscoveryRejected("unfrozen_pre_result_features")
  hs=r["horses"]
  if type(hs) is not list or len(hs)<2:raise DiscoveryRejected("horses_missing")
  nums=set()
  for h in hs:
   if type(h) is not dict or set(h)!={"number","features"}:raise DiscoveryRejected("horse_schema_invalid")
   n=h["number"];f=h["features"]
   if type(n) is not int or n<1 or n>18 or n in nums:raise DiscoveryRejected("horse_number_invalid")
   nums.add(n)
   if type(f) is not dict or not 2<=len(f)<=8 or any(type(k) is not str or not k or k in ("winner","label","result","payout","final_odds") for k in f):
    raise DiscoveryRejected("forbidden_or_missing_feature")
   if features is None:features=tuple(sorted(f))
   if tuple(sorted(f))!=features:raise DiscoveryRejected("feature_schema_drift")
   if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in f.values()):
    raise DiscoveryRejected("nonfinite_or_future_feature")
  if type(r["winner"]) is not int or r["winner"] not in nums:raise DiscoveryRejected("winner_missing")
 return features

def _winner_by(r,keys):
 def rank(h):
  f=h["features"]
  return (-math.prod(f[k] for k in keys),h["number"])
 return min(r["horses"],key=rank)["number"]

def _stats(races,keys):
 hits=sum(_winner_by(r,keys)==r["winner"] for r in races)
 baseline=math.fsum(1/len(r["horses"]) for r in races)/len(races)
 return {"races":len(races),"hits":hits,"win_rate":hits/len(races),
         "random_baseline":baseline,"lift":hits/len(races)-baseline}

def discover_interactions(races,*,train_count,selection_count=2):
 """Precommit first/middle/last chronological windows.

 Only the first training window selects hypotheses. Validation and final
 untouched holdout cannot influence selection. Family size and Bonferroni
 caution are always reported; no statistical significance is claimed.
 """
 names=_validate(races)
 if (type(train_count) is not int or train_count<3 or train_count>len(races)-6
     or type(selection_count) is not int or selection_count<1 or selection_count>8):
  raise DiscoveryRejected("independent_three_way_split_required")
 train=races[:train_count]
 remaining=len(races)-train_count
 validate_count=remaining//2
 validation=races[train_count:train_count+validate_count]
 holdout=races[train_count+validate_count:]
 if len(validation)<3 or len(holdout)<3:raise DiscoveryRejected("validation_holdout_too_short")
 family=[(name,) for name in names]+list(combinations(names,2))
 # Discovery is strictly train-only, deterministic tie-breaking.
 ranked=sorted(family,key=lambda keys:(-_stats(train,keys)["lift"],keys))
 chosen=ranked[:selection_count]
 rows=[]
 for keys in chosen:
  a=_stats(train,keys);b=_stats(validation,keys);c=_stats(holdout,keys)
  rows.append({"features":list(keys),"training":a,"validation":b,
               "untouched_holdout":c,
               "refuted":c["lift"]<=0 or b["lift"]<=0,
               "deployable":False})
 return {"schema":"kyoto_p2_three_way_discovery.v1",
         "status":"SYNTHETIC_OR_RESEARCH_ONLY_NOT_DEPLOYED",
         "race_ids":{"training":[r["race_id"] for r in train],
                     "validation":[r["race_id"] for r in validation],
                     "untouched_holdout":[r["race_id"] for r in holdout]},
         "candidate_family_size":len(family),
         "multiple_testing_correction":"BONFERRONI_REQUIRED_BEFORE_SIGNIFICANCE_CLAIM",
         "bonferroni_alpha":0.05/len(family),
         "selected":rows,"input_sha256":_digest(races),
         "future_labels_used_for_selection":False,
         "official_pre_result_receipts_verified":False,
         "auto_promote":False,"real_bet_authorized":False}
