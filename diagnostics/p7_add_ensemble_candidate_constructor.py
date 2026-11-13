"""LAB-only bounded ADD and ENSEMBLE candidate construction. No JRA IO or deployment."""
from __future__ import annotations
from math import fsum,log,isfinite
from diagnostics.p7_evo_bounded_candidate_constructor import CandidateBuildRejected,_utc
from diagnostics.p7_hybrid_model_registry import _hash,read_registry,registered_model,register_model
from diagnostics.p3_hybrid_prediction_contract import check_lab_prediction
from diagnostics.p7_hybrid_shadow_evolution_cycle import read_shadow

TEMPERATURES=(500,750,1250,1500)
WEIGHTS=(2500,5000,7500)
TRIAL_COUNT=len(TEMPERATURES)+len(WEIGHTS)
CODE_SHA=_hash({"kind":"LAB_ADD_TEMPERATURE_BLEND_V1","temps":TEMPERATURES,"weights":WEIGHTS})

def _derive(snapshot,base,model_id,weights):
    total=fsum(weights)
    if not isfinite(total) or total<=0:raise CandidateBuildRejected("invalid_probability_mass")
    frames={r["horse_number"]:r["frame_number"] for r in snapshot["runners"]}
    quinella=[];groups={}
    for q,w in zip(base["quinella"],weights):
        p=w/total;pair=q["pair"];key=tuple(sorted((frames[pair[0]],frames[pair[1]])))
        quinella.append({"pair":pair[:],"probability":p})
        groups[key]=groups.get(key,0)+p
    return {"model_id":model_id,"source_sha256":base["source_sha256"],
        "feature_schema_sha256":base["feature_schema_sha256"],
        "cutoff_utc":base["cutoff_utc"],"quinella":quinella,
        "bracket":[{"pair":list(k),"probability":v} for k,v in sorted(groups.items())]}

def _add(snapshot,base,model_id,temp):
    return _derive(snapshot,base,model_id,
        [x["probability"]**(temp/1000) for x in base["quinella"]])

def _ensemble(snapshot,base,added,model_id,weight):
    if [q["pair"] for q in base["quinella"]]!=[q["pair"] for q in added["quinella"]]:
        raise CandidateBuildRejected("incompatible_pair_order")
    w=weight/10000
    return _derive(snapshot,base,model_id,
        [(1-w)*b["probability"]+w*a["probability"] for b,a in zip(base["quinella"],added["quinella"])])

def _loss(pred,winner):
    p=[x["probability"] for x in pred["quinella"] if x["pair"]==winner]
    if len(p)!=1:raise CandidateBuildRejected("winner_pair_missing")
    return -log(max(p[0],1e-15))

def construct_add_ensemble(training_path,registry_path,*,base_id,add_id,ensemble_id,
                           plan_locked_utc,min_improvement=.005):
    state=read_shadow(training_path);locked=_utc(plan_locked_utc)
    if len(state["freezes"])<6 or len(state["settled"])!=len(state["freezes"]) or state["decisions"]:
        raise CandidateBuildRejected("complete_training_required")
    if type(min_improvement) not in (float,int) or not isfinite(min_improvement) or not 0<min_improvement<1:
        raise CandidateBuildRejected("invalid_gain_threshold")
    reg=registered_model(registry_path,base_id)
    if reg["model"]["kind"]!="BASELINE":raise CandidateBuildRejected("baseline_required")
    if not (type(add_id) is str and add_id.startswith("LAB-ADD-") and
            type(ensemble_id) is str and ensemble_id.startswith("LAB-ENS-")):
        raise CandidateBuildRejected("lab_ids_required")
    models=read_registry(registry_path)["models"]
    if add_id in models or ensemble_id in models:raise CandidateBuildRejected("candidate_id_already_registered")
    rows=[]
    for race,f in state["freezes"].items():
        s=f["snapshot"];b=f["predictions"][0];result=state["settled"][race]
        if (f["registry_head_sha256"]!=reg["registry_head_sha256"] or
            b["model_id"]!=base_id or _utc(result["outcome_utc"])>=locked):
            raise CandidateBuildRejected("training_source_or_time_invalid")
        check_lab_prediction(registry_path,s,b)
        rows.append((s,b,result["winning_pair"]))
    baseline=fsum(_loss(b,w) for s,b,w in rows)/len(rows)
    trials=[]
    for t in TEMPERATURES:
        avg=fsum(_loss(_add(s,b,add_id,t),w) for s,b,w in rows)/len(rows)
        trials.append(("ADD",t,None,avg))
    best_add=min(trials,key=lambda x:(x[3],x[1]))
    for weight in WEIGHTS:
        avg=fsum(_loss(_ensemble(s,b,_add(s,b,add_id,best_add[1]),ensemble_id,weight),w)
                 for s,b,w in rows)/len(rows)
        trials.append(("ENSEMBLE",best_add[1],weight,avg))
    best=min(trials,key=lambda x:(x[3],x[0],x[1],x[2] or 0))
    if baseline-best[3]<min_improvement:
        return {"state":"NO_CANDIDATE_BASELINE_RETAINED","trial_count":TRIAL_COUNT,
                "registered":False,"production_model_changed":False}
    cfg={"formula":"LAB_ADD_TEMPERATURE_BLEND_V1","temperature_bps":best_add[1],
         "selected_kind":best[0],"ensemble_weight_bps":best[2],
         "trial_count":TRIAL_COUNT,"training_head_sha256":state["head"]}
    end=max(_utc(state["settled"][r]["outcome_utc"]) for r in state["freezes"]).isoformat()
    common={"feature_schema_sha256":reg["model"]["feature_schema_sha256"],
            "code_sha256":CODE_SHA,"training_end_utc":end,"source_scope":"LAB_RESEARCH_ONLY"}
    add={"model_id":add_id,"kind":"ADD","parents":[base_id],
         "configuration_sha256":_hash({"cfg":cfg,"kind":"ADD"}),"weights_bps":[],**common}
    weight=best[2] or 5000
    ens={"model_id":ensemble_id,"kind":"ENSEMBLE","parents":[base_id,add_id],
         "configuration_sha256":_hash({"cfg":cfg,"kind":"ENSEMBLE"}),
         "weights_bps":[10000-weight,weight],**common}
    register_model(registry_path,add);register_model(registry_path,ens)
    body={"schema":"kyoto_lab_add_ensemble_generated.v1","plan_locked_utc":locked.isoformat(),
          "baseline_id":base_id,"add_id":add_id,"ensemble_id":ensemble_id,
          "selected_id":add_id if best[0]=="ADD" else ensemble_id,
          "config":cfg,"model_specs":[add,ens],
          "registry_head_sha256":read_registry(registry_path)["head"],
          "training_head_sha256":state["head"],"trial_count":TRIAL_COUNT,
          "training_gain":baseline-best[3],"source_scope":"LAB_RESEARCH_ONLY",
          "real_JRA_certified":False,"production_model_changed":False}
    return {**body,"proposal_sha256":_hash(body)}

def forecast_add_ensemble(proposal,registry_path,snapshot,baseline):
    if type(proposal) is not dict or proposal.get("schema")!="kyoto_lab_add_ensemble_generated.v1":
        raise CandidateBuildRejected("proposal_required")
    if _hash({k:v for k,v in proposal.items() if k!="proposal_sha256"})!=proposal.get("proposal_sha256"):
        raise CandidateBuildRejected("proposal_modified")
    registry=read_registry(registry_path)
    if (registry["head"]!=proposal["registry_head_sha256"] or
        [registry["models"].get(x["model_id"]) for x in proposal["model_specs"]]!=proposal["model_specs"]):
        raise CandidateBuildRejected("registry_changed")
    cfg=proposal["config"]
    add_spec,ens_spec=proposal["model_specs"]
    if (cfg.get("formula")!="LAB_ADD_TEMPERATURE_BLEND_V1"
        or cfg.get("trial_count")!=TRIAL_COUNT
        or proposal.get("trial_count")!=TRIAL_COUNT
        or cfg.get("training_head_sha256")!=proposal.get("training_head_sha256")
        or any(m.get("code_sha256")!=CODE_SHA for m in (add_spec,ens_spec))
        or add_spec.get("configuration_sha256")!=_hash({"cfg":cfg,"kind":"ADD"})
        or ens_spec.get("configuration_sha256")!=_hash({"cfg":cfg,"kind":"ENSEMBLE"})
        or add_spec.get("kind")!="ADD" or ens_spec.get("kind")!="ENSEMBLE"
        or add_spec.get("parents")!=[proposal["baseline_id"]]
        or ens_spec.get("parents")!=[proposal["baseline_id"],proposal["add_id"]]
        or add_spec.get("model_id")!=proposal["add_id"]
        or ens_spec.get("model_id")!=proposal["ensemble_id"]):
        raise CandidateBuildRejected("generated_model_provenance_invalid")
    w=cfg.get("ensemble_weight_bps")
    expected_weight=w if w is not None else 5000
    if (type(expected_weight) is not int or expected_weight not in (*WEIGHTS,5000)
        or ens_spec.get("weights_bps")!=[10000-expected_weight,expected_weight]):
        raise CandidateBuildRejected("ensemble_weights_modified")
    check_lab_prediction(registry_path,snapshot,baseline)
    if baseline["model_id"]!=proposal["baseline_id"] or _utc(snapshot["cutoff_utc"])<=_utc(proposal["plan_locked_utc"]):
        raise CandidateBuildRejected("wrong_baseline_or_cutoff")
    cfg=proposal["config"]
    if cfg["temperature_bps"] not in TEMPERATURES or cfg["trial_count"]!=TRIAL_COUNT:
        raise CandidateBuildRejected("invalid_config")
    add=_add(snapshot,baseline,proposal["add_id"],cfg["temperature_bps"])
    if cfg["selected_kind"]=="ADD" and cfg["ensemble_weight_bps"] is None:
        pred=add
    elif cfg["selected_kind"]=="ENSEMBLE" and cfg["ensemble_weight_bps"] in WEIGHTS:
        pred=_ensemble(snapshot,baseline,add,proposal["ensemble_id"],cfg["ensemble_weight_bps"])
    else:raise CandidateBuildRejected("invalid_selected_formula")
    if pred["model_id"]!=proposal["selected_id"]:raise CandidateBuildRejected("selected_model_changed")
    check_lab_prediction(registry_path,snapshot,pred)
    return pred

def audit_add_ensemble_holdout(proposal,training_path,holdout_path,registry_path,*,
                               min_races=10,comparison_count=TRIAL_COUNT):
    if type(comparison_count) is not int or comparison_count<TRIAL_COUNT or type(min_races) is not int or min_races<10:
        raise CandidateBuildRejected("multiplicity_understated")
    if type(proposal) is not dict or proposal.get("schema")!="kyoto_lab_add_ensemble_generated.v1":
        raise CandidateBuildRejected("proposal_required")
    if _hash({k:v for k,v in proposal.items() if k!="proposal_sha256"})!=proposal.get("proposal_sha256"):
        raise CandidateBuildRejected("proposal_modified")
    training=read_shadow(training_path);held=read_shadow(holdout_path)
    if training["head"]!=proposal["training_head_sha256"]:
        raise CandidateBuildRejected("training_changed")
    if (len(held["freezes"])<min_races or len(held["settled"])!=len(held["freezes"]) or
        held["decisions"] or set(training["freezes"])&set(held["freezes"])):
        raise CandidateBuildRejected("disjoint_complete_holdout_required")
    ll=[];bs=[]
    for race,f in held["freezes"].items():
        if (f["registry_head_sha256"]!=proposal["registry_head_sha256"] or
            _utc(f["freeze_utc"])<=_utc(proposal["plan_locked_utc"])):
            raise CandidateBuildRejected("holdout_freeze_invalid")
        base,new=f["predictions"];s=f["snapshot"]
        if forecast_add_ensemble(proposal,registry_path,s,base)!=new:
            raise CandidateBuildRejected("holdout_prediction_not_reproducible")
        winner=held["settled"][race]["winning_pair"]
        ll.append((_loss(base,winner),_loss(new,winner)))
        bs.append(tuple(fsum((x["probability"]-int(x["pair"]==winner))**2 for x in p["quinella"])
                        for p in (base,new)))
    score=lambda pairs:(fsum(a-b for a,b in pairs)/len(pairs),
                        sum(b<a for a,b in pairs)/len(pairs))
    l,b=score(ll),score(bs)
    passed=l[0]>=.01 and b[0]>0 and l[1]>=.75 and b[1]>=.75
    receipt={"schema":"kyoto_lab_add_ensemble_audit.v1",
        "proposal_sha256":proposal["proposal_sha256"],"holdout_head_sha256":held["head"],
        "holdout_races":len(ll),"comparison_count":comparison_count,
        "logloss_gain":l[0],"brier_gain":b[0],
        "decision":"LAB_ONLY_FURTHER_AUDIT" if passed else "LAB_REJECT_BASELINE_RETAINED",
        "independent_evo07_certified":False,"real_JRA_certified":False,
        "production_model_changed":False}
    return {**receipt,"audit_sha256":_hash(receipt)}
