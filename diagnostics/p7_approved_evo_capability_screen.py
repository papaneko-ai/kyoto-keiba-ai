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
