"""Approved EVO-01..08 capability-specific research candidate screening.

Unlike HYP-01..08 feature rules, these are the eight approved *capabilities*.
This generates testable research proposals and rejects insufficient evidence.
No promotion, live operation, real wagers or autonomous code modification.
"""
import hashlib,json
from pathlib import Path

MANIFEST=Path(__file__).resolve().parents[1]/"docs/diagnostics/kyoto_ai_evolution_requirements_manifest_20261106.json"
EXPECTED=tuple("EVO-%02d"%i for i in range(1,9))
REQUIRED={
 "EVO-01":("source_cost","source_coverage","value_gain"),
 "EVO-02":("failure_category","baseline_loss","candidate_loss"),
 "EVO-03":("paired_races","champion_loss","shadow_loss"),
 "EVO-04":("preregistered_portfolios","matched_races","drawdown"),
 "EVO-05":("baseline_drift","current_drift","monitor_windows"),
 "EVO-06":("research_budget","experiment_count","holdout_unused"),
 "EVO-07":("audit_plan_sha256","independent_holdout","certifier_independent"),
 "EVO-08":("surprise_metric","counterexamples","independent_retest"),
}
class CapabilityRejected(ValueError):pass

def screen_capabilities(observations,*,manifest_path=MANIFEST):
 """Evidence-free/partial capabilities remain explicitly blocked.

 observations: dict keyed by EVO IDs; each value is a research-only dict.
 No numerical effectiveness or official provenance is inferred from presence.
 """
 manifest=json.loads(Path(manifest_path).read_text(encoding="utf-8"))
 if manifest.get("schema")!="kyoto_evolution.v1" or set(manifest.get("features",{}))!=set(EXPECTED):
  raise CapabilityRejected("approved_manifest_mismatch")
 if type(observations) is not dict or not set(observations).issubset(EXPECTED):
  raise CapabilityRejected("unknown_capability")
 proposals=[]
 for eid in EXPECTED:
  item=observations.get(eid)
  fields=REQUIRED[eid]
  if item is None:
   status="BLOCKED_MISSING_RESEARCH_EVIDENCE";missing=list(fields)
  elif type(item) is not dict or any(type(k) is not str for k in item):
   raise CapabilityRejected("invalid_evidence_schema")
  else:
   if set(item)-set(fields):raise CapabilityRejected("unexpected_evidence_field")
   missing=[k for k in fields if k not in item]
   for k,v in item.items():
    if type(v) not in (int,float,str,bool) or (type(v) is str and not v):
     raise CapabilityRejected("invalid_evidence_value")
   status="RESEARCH_HYPOTHESIS_ONLY" if not missing else "BLOCKED_INCOMPLETE_RESEARCH_EVIDENCE"
  proposals.append({"id":eid,"approved_capability":manifest["features"][eid],
                    "required_evidence_fields":list(fields),"missing_fields":missing,
                    "status":status,"candidate_for_independent_falsification":not missing,
                    "certified":False,"promoted":False})
 payload={"schema":"kyoto_p7_approved_evo_capability_screen.v1",
          "manifest_sha256":hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest(),
          "capabilities":proposals,"approved_capability_count":8,
          "research_hypothesis_count":sum(x["candidate_for_independent_falsification"] for x in proposals),
          "independent_evolution_certified":False,"auto_promote":False,
          "prediction_ready":False,"real_bet_authorized":False}
 return {**payload,"receipt_sha256":hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()).hexdigest()}

def falsify_research_candidates(observations):
 """Predeclared capability-specific counterexample gates, not certification.

 Numeric evidence is synthetic/research-only. The eight rules are fixed and
 conservative; unknown or insufficient evidence is rejected, not promoted.
 """
 from math import isfinite
 screened=screen_capabilities(observations)
 results=[]
 for entry in screened["capabilities"]:
  eid=entry["id"];item=observations.get(eid)
  if entry["status"]!="RESEARCH_HYPOTHESIS_ONLY":
   results.append({"id":eid,"verdict":"INSUFFICIENT_EVIDENCE","counterexample":None,"deployable":False})
   continue
  def num(key):
   v=item[key]
   if type(v) not in (int,float) or not isfinite(v) or v<0:
    raise CapabilityRejected("invalid_numeric_evidence_"+eid+"_"+key)
   return float(v)
  # Rule definitions are research falsification examples, not performance proof.
  if eid=="EVO-01":
   counterexample=num("value_gain")<=num("source_cost") or num("source_coverage")<0.9
  elif eid=="EVO-02":
   counterexample=num("candidate_loss")>=num("baseline_loss")
  elif eid=="EVO-03":
   counterexample=num("paired_races")<4 or num("shadow_loss")>=num("champion_loss")
  elif eid=="EVO-04":
   counterexample=num("preregistered_portfolios")<2 or num("matched_races")<4 or num("drawdown")>0.25
  elif eid=="EVO-05":
   counterexample=num("monitor_windows")<3 or num("current_drift")>=num("baseline_drift")
  elif eid=="EVO-06":
   counterexample=num("experiment_count")<3 or num("research_budget")==0 or item["holdout_unused"] is not True
  elif eid=="EVO-07":
   h=item["audit_plan_sha256"]
   counterexample=(type(h) is not str or len(h)!=64 or any(c not in "0123456789abcdef" for c in h)
                   or item["independent_holdout"] is not True or item["certifier_independent"] is not True)
  else:
   counterexample=num("surprise_metric")<=0 or num("counterexamples")<1 or item["independent_retest"] is not True
  results.append({"id":eid,"verdict":"REFUTED_RESEARCH_CANDIDATE" if counterexample else "NOT_REFUTED_RESEARCH_ONLY",
                  "counterexample":counterexample,"deployable":False})
 return {"schema":"kyoto_p7_approved_evo_falsification.v1",
         "screen_receipt_sha256":screened["receipt_sha256"],"results":results,
         "certified":False,"auto_promote":False,"live_prediction_ready":False}
