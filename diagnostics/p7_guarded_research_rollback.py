"""P7 guarded research-only model selection and rollback.

No code deployment, external write, purchase, or claim of real performance.
Precommitted thresholds and independent chronological observations are mandatory.
"""
from __future__ import annotations
import hashlib,json,math
from datetime import datetime,timezone

class PromotionRejected(ValueError):pass

def _utc(s):
 try:
  t=datetime.fromisoformat(s.replace("Z","+00:00"))
  if t.utcoffset()!=timezone.utc.utcoffset(None):
   raise ValueError("UTC required")
  return t
 except (ValueError,TypeError,AttributeError) as exc:
  raise PromotionRejected("invalid_utc_time") from exc

def _digest(obj):
 return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def evaluate_pairwise(observations,*,min_races=4):
 """Each independent race has champion and candidate pre-result log loss.

 Pre-registration is explicitly required; self-attestation does not establish
 genuine JRA pre-race evidence. Score on identical race IDs and cutoffs.
 """
 if type(observations) is not list or len(observations)<min_races or type(min_races) is not int or min_races<3:
  raise PromotionRejected("insufficient_paired_races")
 seen=set();previous=None;deltas=[]
 for o in observations:
  if type(o) is not dict or set(o)!={"race_id","cutoff_utc","pre_result_frozen","champion_log_loss","candidate_log_loss"}:
   raise PromotionRejected("paired_observation_schema_invalid")
  rid=o["race_id"];t=_utc(o["cutoff_utc"])
  if type(rid) is not str or not rid or rid in seen:
   raise PromotionRejected("duplicate_race")
  seen.add(rid)
  if previous is not None and t<=previous:
   raise PromotionRejected("chronological_leakage")
  previous=t
  if o["pre_result_frozen"] is not True:
   raise PromotionRejected("not_frozen_before_result")
  a=o["champion_log_loss"];b=o["candidate_log_loss"]
  if any(type(x) not in (float,int) or not math.isfinite(x) or x<0 for x in (a,b)):
   raise PromotionRejected("invalid_proper_scores")
  deltas.append(float(a-b))
 return {"races":len(deltas),"champion_mean_log_loss":math.fsum(o["champion_log_loss"] for o in observations)/len(deltas),
         "candidate_mean_log_loss":math.fsum(o["candidate_log_loss"] for o in observations)/len(deltas),
         "candidate_improvement":math.fsum(deltas)/len(deltas),
         "paired_win_races":sum(x>0 for x in deltas),
         "paired_losses":sum(x<0 for x in deltas)}

def guard_research_champion(*,champion,candidate,alternate,observations,
                            min_races=4,min_mean_improvement=0.01,
                            min_paired_win_fraction=0.75,prior_decision_sha256=None):
 """Fail closed: only propose a research shadow choice, never deploy.

 Champion remains when evidence is insufficient, nonpositive, or a challenger
 has too few paired race wins. An alternate is *not* silently promoted: it
 requires its own separately attested paired evidence and audit.
 """
 names=(champion,candidate,alternate)
 if any(type(n) is not str or not n for n in names) or len(set(names))!=3:
  raise PromotionRejected("three_distinct_model_versions_required")
 if type(min_mean_improvement) not in (int,float) or not math.isfinite(min_mean_improvement) or min_mean_improvement<=0:
  raise PromotionRejected("improvement_threshold_invalid")
 if type(min_paired_win_fraction) not in (int,float) or not 0.5<min_paired_win_fraction<=1:
  raise PromotionRejected("win_fraction_threshold_invalid")
 if prior_decision_sha256 is not None and (type(prior_decision_sha256) is not str or len(prior_decision_sha256)!=64 or any(c not in "0123456789abcdef" for c in prior_decision_sha256)):
  raise PromotionRejected("invalid_prior_decision_anchor")
 score=evaluate_pairwise(observations,min_races=min_races)
 passing=(score["candidate_improvement"]>=min_mean_improvement and
          score["paired_win_races"]/score["races"]>=min_paired_win_fraction)
 decision="SHADOW_CANDIDATE_ELIGIBLE_FOR_INDEPENDENT_AUDIT" if passing else "ROLLBACK_TO_RETAINED_CHAMPION"
 payload={"schema":"kyoto_p7_research_guarded_rollback.v1","status":"RESEARCH_ONLY_NOT_DEPLOYED",
          "champion":champion,"candidate":candidate,"alternate":alternate,
          "decision":decision,"retained_champion":champion,
          "alternate_requires_independent_audit":True,
          "thresholds":{"min_races":min_races,"min_mean_improvement":min_mean_improvement,
                        "min_paired_win_fraction":min_paired_win_fraction},
          "paired_evidence":score,
          "observation_sha256":_digest(observations),
          "prior_decision_sha256":prior_decision_sha256,
          "auto_deploy":False,"actual_bet_authorized":False,
          "external_write":False}
 return {**payload,"decision_sha256":_digest(payload)}

def monitor_research_decisions(epochs,*,min_races=4):
 """Chronological forward monitor; each window is independent and nonoverlap.

 No same race can be reused to manufacture repeated certification.
 """
 if type(epochs) is not list or not epochs:
  raise PromotionRejected("monitor_epochs_required")
 seen=set();last=None;reports=[]
 for e in epochs:
  if type(e) is not dict or set(e)!={"epoch_id","champion","candidate","alternate","observations"}:
   raise PromotionRejected("monitor_epoch_schema_invalid")
  if type(e["epoch_id"]) is not str or not e["epoch_id"] or e["epoch_id"] in {x["epoch_id"] for x in reports}:
   raise PromotionRejected("duplicate_epoch")
  obs=e["observations"]
  score=evaluate_pairwise(obs,min_races=min_races)
  first=_utc(obs[0]["cutoff_utc"]);end=_utc(obs[-1]["cutoff_utc"])
  if last is not None and first<=last:
   raise PromotionRejected("monitor_overlapping_time_windows")
  last=end
  for x in obs:
   if x["race_id"] in seen:raise PromotionRejected("monitor_duplicate_race_across_epochs")
   seen.add(x["race_id"])
  verdict=guard_research_champion(champion=e["champion"],candidate=e["candidate"],
             alternate=e["alternate"],observations=obs,min_races=min_races,
             prior_decision_sha256=reports[-1]["decision_sha256"] if reports else None)
  reports.append({"epoch_id":e["epoch_id"],"first_utc":first.isoformat(),
                  "last_utc":end.isoformat(),"score":score,
                  "decision":verdict["decision"],"decision_sha256":verdict["decision_sha256"],
                  "retained_champion":verdict["retained_champion"]})
 return {"schema":"kyoto_p7_research_forward_monitor.v1","status":"RESEARCH_ONLY",
         "epochs":reports,"unique_races":len(seen),
         "decision_chain_head":reports[-1]["decision_sha256"],
         "auto_deploy":False,"prediction_ready":False}
