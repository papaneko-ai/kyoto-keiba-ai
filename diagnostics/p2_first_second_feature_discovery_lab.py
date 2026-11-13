"""ALG02 LAB separate winner, runner-up and unplaced feature effects.

Predeclared single/pair feature family. Selection strictly training only;
validation and untouched holdout report counterexamples. No live prediction
certification, profit claim, JRA HTTP, or future feature accepted.
"""
from __future__ import annotations
from itertools import combinations
from math import fsum,isfinite
from diagnostics.p3_offline_model_tournament import _hash,_utc
from diagnostics.p2_p3_p5_offline_feature_bridge import FEATURE_SCHEMA,FeatureBridgeRejected,_feature_row

class PlaceDiscoveryRejected(ValueError):pass

def _score(rows,keys):
    pos=[[],[],[]]
    for row in rows:
        s=row["snapshot"];winner=row["first_second"]
        for h in s["runners"]:
            value=1.0
            for k in keys:value*=h["features"][k]
            slot=0 if h["number"]==winner[0] else (1 if h["number"]==winner[1] else 2)
            pos[slot].append(value)
    avg=[fsum(p)/len(p) if p else 0 for p in pos]
    return {"first_mean":avg[0],"second_mean":avg[1],"unplaced_mean":avg[2],
            "first_minus_unplaced":avg[0]-avg[2],
            "second_minus_unplaced":avg[1]-avg[2],
            "first_second_mean_minus_unplaced":(avg[0]+avg[1])/2-avg[2],
            "first_samples":len(pos[0]),"second_samples":len(pos[1]),
            "unplaced_samples":len(pos[2])}

def discover_first_second(rows,*,train_count,selection_count=3):
    if type(rows) is not list or len(rows)<12:
        raise PlaceDiscoveryRejected("at_least_twelve_races_required")
    if (type(train_count) is not int or train_count<4 or train_count>len(rows)-8
        or type(selection_count) is not int or not 1<=selection_count<=8):
        raise PlaceDiscoveryRejected("three_windows_required")
    seen=set();last=None
    for row in rows:
        if type(row) is not dict or set(row)!={"snapshot","forecast_frozen_utc",
                                            "outcome_utc","first_second"}:
            raise PlaceDiscoveryRejected("row_schema_invalid")
        s=row["snapshot"]
        try:_feature_row(s,expected_keys=FEATURE_SCHEMA)
        except (FeatureBridgeRejected,ValueError) as exc:
            raise PlaceDiscoveryRejected("feature_snapshot_invalid") from exc
        race=s["race_id"]
        if type(race) is not str or not race.startswith("LAB-") or race in seen:
            raise PlaceDiscoveryRejected("duplicate_or_nonlab_race")
        seen.add(race)
        cut=_utc(s["feature_cutoff_utc"]);start=_utc(s["race_start_utc"])
        freeze=_utc(row["forecast_frozen_utc"]);outcome=_utc(row["outcome_utc"])
        if ((last is not None and cut<=last) or not cut<=freeze<start<outcome):
            raise PlaceDiscoveryRejected("outcome_or_cutoff_leakage")
        last=cut
        winner=row["first_second"];nums={h["number"] for h in s["runners"]}
        if (type(winner) is not list or len(winner)!=2 or
            winner[0]==winner[1] or
            any(type(n) is not int or n not in nums for n in winner)):
            raise PlaceDiscoveryRejected("first_second_invalid")
    rest=len(rows)-train_count
    mid=train_count+rest//2
    train,validation,holdout=rows[:train_count],rows[train_count:mid],rows[mid:]
    if len(validation)<4 or len(holdout)<4:
        raise PlaceDiscoveryRejected("insufficient_independent_validation")
    family=[(k,) for k in FEATURE_SCHEMA]+list(combinations(FEATURE_SCHEMA,2))
    ranking=sorted(family,key=lambda keys:(
        -_score(train,keys)["first_second_mean_minus_unplaced"],keys))
    selected=[]
    for keys in ranking[:selection_count]:
        a,b,c=(_score(window,keys) for window in (train,validation,holdout))
        selected.append({"features":list(keys),"training":a,"validation":b,
                         "untouched_holdout":c,
                         "refuted":b["first_second_mean_minus_unplaced"]<=0 or
                                    c["first_second_mean_minus_unplaced"]<=0,
                         "candidate_only":True})
    body={"schema":"kyoto_p2_first_second_lab_discovery.v1",
          "feature_family_size":len(family),
          "selection_method":"TRAIN_ONLY_FIXED_SINGLE_AND_PAIR",
          "race_ids":{"training":[r["snapshot"]["race_id"] for r in train],
                      "validation":[r["snapshot"]["race_id"] for r in validation],
                      "holdout":[r["snapshot"]["race_id"] for r in holdout]},
          "selected":selected,"input_sha256":_hash(rows),
          "comparison_adjustment_required":True,
          "holdout_selection_authorized":False,
          "real_JRA_evidence_authenticated":False,
          "production_model_changed":False,"real_bet_authorized":False}
    return {**body,"receipt_sha256":_hash(body)}
