"""Offline operator handoff for independently supplied, permitted race originals.

This is a practical file-to-verification entry point, NOT an origin
authentication mechanism or authorization for automated JRA access.
It reuses the established three-original strict parser, then produces
an immutable evidence-gap report and a machine-readable next-action list.
"""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
from tempfile import NamedTemporaryFile

from diagnostics.p1_three_original_dual_intake import inspect_three_original_dual_intake

class HandoffRejected(ValueError):pass

def assess_originals(bundle:bytes,snapshot:dict,*,observed_utc:str,channel:str):
 if type(bundle) is not bytes or not bundle:raise HandoffRejected("bundle_bytes_required")
 if type(snapshot) is not dict:raise HandoffRejected("snapshot_required")
 if channel not in ("PC","SP"):raise HandoffRejected("channel_invalid")
 # The existing parser is the single source of truth; never duplicate it.
 parsed=inspect_three_original_dual_intake(
  bundle,snapshot,observed_utc=observed_utc,racecard_channel=channel,
  verify_market_originals=True)
 if not parsed["racecard_roster_original_verified"] or not parsed["market_prices_original_verified"]:
  raise HandoffRejected("three_original_content_binding_incomplete")
 if parsed["prediction_ready"] or parsed["actual_orders_authorized"]:
  raise HandoffRejected("unsafe_existing_parser_release")
 return {"schema":"kyoto_p1_offline_operator_handoff.v1",
         "classification":"THREE_ORIGINALS_CONTENT_VERIFIED_ORIGIN_NOT_AUTHENTICATED",
         "meeting_date":parsed["meeting_date"],"race":parsed["race"],
         "channel":channel,
         "originals_sha256":parsed["source_sha256"],
         "bundle_sha256":hashlib.sha256(bundle).hexdigest(),
         "snapshot_sha256":parsed["snapshot_sha256"],
         "roster_count":parsed["racecard_roster_receipt"]["runner_count"],
         "quinella_pair_count":parsed["market_original_receipts"]["odds"]["pair_count"],
         "bracket_pair_count":parsed["market_original_receipts"]["bracket_odds"]["pair_count"],
         "source_content_verified":True,
         "official_origin_authenticated":False,
         "official_sales_state_authenticated":False,
         "official_withdrawal_state_authenticated":False,
         "real_operational_score_eligible":False,
         "prediction_ready":False,
         "actual_orders_authorized":False,
         "network_requests":0,
         "remaining_requirements":[
           "independently authenticate official source and collection authorization",
           "independently verify capture times precede actual race cutoff",
           "independently verify official sales state and scratches at capture",
           "obtain external operational verifier acceptance before scoring"]}

def _safe_out(out:Path,inputs):
 target=out.resolve()
 if target in [p.resolve() for p in inputs]:
  raise HandoffRejected("cannot_overwrite_original_inputs")
 if out.is_symlink() or out.exists():
  raise HandoffRejected("immutable_output_already_exists")
 # Output must be in a pre-existing directory: no implicit directory mutation.
 if not out.parent.is_dir():raise HandoffRejected("output_parent_missing")

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--bundle",required=True,type=Path)
 p.add_argument("--snapshot",required=True,type=Path)
 p.add_argument("--observed-utc",required=True)
 p.add_argument("--channel",required=True,choices=("PC","SP"))
 p.add_argument("--out",required=True,type=Path)
 a=p.parse_args(argv)
 _safe_out(a.out,(a.bundle,a.snapshot))
 report=assess_originals(a.bundle.read_bytes(),
     json.loads(a.snapshot.read_text(encoding="utf-8")),
     observed_utc=a.observed_utc,channel=a.channel)
 # Exclusive creation: never replace any previous evidence or inputs.
 with a.out.open("x",encoding="utf-8") as f:
  json.dump(report,f,ensure_ascii=False,sort_keys=True,indent=2)
  f.write("\n")
 print(json.dumps({"classification":report["classification"],
                   "content_verified":True,
                   "real_operational_score_eligible":False,
                   "prediction_ready":False},ensure_ascii=False))
 return report

if __name__=="__main__":main()
