"""Independent operational readiness measure; never equate research CI with live use.

A capability receives points ONLY with explicitly classified external, non-synthetic
operational evidence. Missing evidence is UNVERIFIED, not a factual failure.
The denominator and stage dependencies are fixed; this module performs no HTTP.
"""
import argparse,hashlib,json
from pathlib import Path

SCHEMA="kyoto_operational_readiness.v1"
GATES=(
 ("LIVE_RACECARD",15,()),
 ("LIVE_MARKET",15,("LIVE_RACECARD",)),
 ("PRE_RACE_FEATURES",10,("LIVE_RACECARD",)),
 ("MODEL_VALIDATION",15,("PRE_RACE_FEATURES",)),
 ("MARKET_EV",10,("LIVE_MARKET","MODEL_VALIDATION")),
 ("REAL_PAPER_TRADE",15,("MARKET_EV",)),
 ("OFFICIAL_SETTLEMENT",10,("REAL_PAPER_TRADE",)),
 ("MOBILE_END_TO_END",10,("OFFICIAL_SETTLEMENT",)),
)
REQUIRED={"LIVE_RACECARD":"live_racecard","LIVE_MARKET":"live_market",
          "PRE_RACE_FEATURES":"pre_race_features","MODEL_VALIDATION":"out_of_sample_model",
          "MARKET_EV":"live_ev","REAL_PAPER_TRADE":"precommitted_paper_trade",
          "OFFICIAL_SETTLEMENT":"official_result_settlement",
          "MOBILE_END_TO_END":"mobile_end_to_end"}
ALLOWED_FIELDS={"gate_id","evidence_kind","source_sha256","verified_by","verified_at_utc",
                "independent_receipt","race_day","source_reference","pass"}

class OperationalError(ValueError):pass

def _digest(obj):
 return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def evaluate(receipts, *, independent_verifier=None):
 """A verified receipt requires an independent callback, not just a claim.

 No verifier -> 0 *verified* points, not a statement that 0% of code exists.
 A callback must actually check bytes, timing, origin and relevant real-world
 functionality; GitHub CI alone does not satisfy it.
 """
 if type(receipts) is not list:raise OperationalError("receipts_must_be_list")
 seen=set();verified=set();rows=[]
 for receipt in receipts:
  if type(receipt) is not dict or set(receipt)!=ALLOWED_FIELDS:
   raise OperationalError("receipt_schema_invalid")
  gate=receipt["gate_id"]
  if gate not in REQUIRED or gate in seen:raise OperationalError("unknown_or_duplicate_gate")
  seen.add(gate)
  if receipt["evidence_kind"]!=REQUIRED[gate] or receipt["pass"] is not True:
   raise OperationalError("wrong_evidence_type_or_failed")
  for k in ("source_sha256","verified_by","verified_at_utc","independent_receipt","race_day","source_reference"):
   if type(receipt[k]) is not str or not receipt[k]:
    raise OperationalError("missing_receipt_field")
  if len(receipt["source_sha256"])!=64 or any(c not in "0123456789abcdef" for c in receipt["source_sha256"]):
   raise OperationalError("invalid_source_hash")
  # Even a plausible receipt is unverified without independent rechecking.
  if independent_verifier is not None and independent_verifier(receipt) is True:
   verified.add(gate)
 score=0
 for gate,points,deps in GATES:
  if gate in verified and all(d in verified for d in deps):
   state="VERIFIED_OPERATIONAL";score+=points
  elif gate in seen:
   state="CLAIM_UNVERIFIED_OR_DEPENDENCY_BLOCKED"
  else:
   state="NO_OPERATIONAL_RECEIPT"
  rows.append({"id":gate,"points":points,"state":state,"dependencies":list(deps)})
 return {"schema":SCHEMA,"metric":"VERIFIED_OPERATIONAL_READINESS",
         "verified_points":score,"total_points":100,
         "verified_fraction":score/100,
         "unverified_points":100-score,
         "interpretation":"LOWER_BOUND_OF_INDEPENDENTLY_VERIFIED_OPERATIONAL_CAPABILITIES_NOT_PERCENT_OF_CODE_COMPLETE",
         "research_ci_not_accepted":True,
         "gates":rows,"receipt_manifest_sha256":_digest(receipts)}

def main(argv=None):
 p=argparse.ArgumentParser()
 p.add_argument("--receipts",default="docs/diagnostics/kyoto_operational_receipts_v1.json")
 p.add_argument("--out",required=True)
 args=p.parse_args(argv)
 manifest=json.loads(Path(args.receipts).read_text(encoding="utf-8"))
 if manifest.get("schema")!=SCHEMA or set(manifest)!={"schema","receipts"}:
  raise OperationalError("manifest_schema_invalid")
 # CI deliberately cannot self-attest external operational proof.
 report=evaluate(manifest["receipts"])
 Path(args.out).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print("KYOTO_OPERATIONAL_VERIFIED="+str(report["verified_points"])+"/100")
 print("KYOTO_OPERATIONAL_UNVERIFIED="+str(report["unverified_points"])+"/100")
 print("KYOTO_OPERATIONAL_NOT_EQUIVALENT_TO_RESEARCH_SCORE=TRUE")

if __name__=="__main__":
 main()
