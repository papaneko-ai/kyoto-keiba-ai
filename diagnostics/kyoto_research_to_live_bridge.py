"""Bind each research graduation gate to concrete production-transition evidence.

This is a read-only crosswalk, not an authorization mechanism. It makes it
impossible to report a graduation feature as an operational racing feature
without a separate externally verified operational gate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

class BridgeRejected(ValueError): pass

CONNECTORS = (
  ("RG-01", ("REAL_PAPER_TRADE","OFFICIAL_SETTLEMENT"),
   ("diagnostics/p3_p6_research_no_bet.py","diagnostics/p6_fixture_durable_ledger.py")),
  ("RG-02", ("LIVE_MARKET","MARKET_EV"),
   ("diagnostics/p3_p6_research_no_bet.py","diagnostics/p1_three_original_dual_intake.py")),
  ("RG-03", ("PRE_RACE_FEATURES","MODEL_VALIDATION"),
   ("diagnostics/p3_research_calibration.py","diagnostics/jra_one_shot_market_capture.py")),
  ("RG-04", ("MODEL_VALIDATION","REAL_PAPER_TRADE"),
   ("diagnostics/p7_independent_holdout_research.py","diagnostics/p7_guarded_research_rollback.py")),
  ("RG-05", ("LIVE_RACECARD","LIVE_MARKET"),
   ("diagnostics/p1_operator_original_handoff.py","diagnostics/p1_three_original_dual_intake.py")),
  ("RG-06", ("MOBILE_END_TO_END",),
   ("diagnostics/p8_mobile_readonly_planner_app.py","diagnostics/kyoto_operational_readiness.py")),
)

def crosswalk(graduation, operational, *, code_file_exists):
    if (type(graduation) is not dict or
            graduation.get("schema") != "kyoto_research_graduation_result.v1" or
            type(graduation.get("areas")) is not list or
            len(graduation["areas"]) != 6):
        raise BridgeRejected("verified_graduation_report_required")
    if (type(operational) is not dict or
            operational.get("schema") != "kyoto_operational_readiness.v1" or
            type(operational.get("gates")) is not list or
            type(operational.get("verified_points")) is not int):
        raise BridgeRejected("independent_operational_report_required")
    gates={}
    for gate in operational["gates"]:
        if type(gate) is not dict or gate.get("id") in gates:
            raise BridgeRejected("invalid_or_duplicate_operational_gate")
        gates[gate.get("id")]=gate.get("state")
    rows=[]
    for index, (key, required_gates, sources) in enumerate(CONNECTORS):
        mark=graduation["areas"][index]
        if mark.get("id")!=key or type(mark.get("component_pass")) is not bool or type(mark.get("integration_pass")) is not bool:
            raise BridgeRejected("graduation_and_live_gate_misaligned")
        if any(k not in gates for k in required_gates):
            raise BridgeRejected("required_operational_gate_missing")
        source_files_exist=all(code_file_exists(path) is True for path in sources)
        operational_verified=all(gates[k]=="VERIFIED_OPERATIONAL" for k in required_gates)
        research_integrated=mark["component_pass"] and mark["integration_pass"]
        rows.append({
            "id":key,"research_component_pass":mark["component_pass"],
            "research_integrated":research_integrated,
            "known_adapter_code_present":source_files_exist,
            "required_independent_operational_gates":list(required_gates),
            "externally_verified_real_operation":operational_verified,
            "connection_state":("LIVE_VERIFIED" if operational_verified and research_integrated and source_files_exist
              else "RESEARCH_TO_LIVE_NOT_YET_VERIFIED"),
            "remaining":([] if operational_verified and research_integrated and source_files_exist else
               ["close_research_integration_gap"] * (not research_integrated) +
               ["independently_verify_live_sources_and_functionality"] * (not operational_verified) +
               ["restore_expected_code_paths"] * (not source_files_exist))
        })
    return {
        "schema":"kyoto_research_to_live_crosswalk.v1",
        "source_graduation_percent":graduation["graduation_percent"],
        "operational_verified_points":operational["verified_points"],
        "research_to_live_verified_areas":sum(r["connection_state"]=="LIVE_VERIFIED" for r in rows),
        "total_areas":6,
        "all_connected":all(r["connection_state"]=="LIVE_VERIFIED" for r in rows),
        "real_purchase_authorized":False,
        "this_report_does_not_authenticate_jra_sources":True,
        "rows":rows}

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=".")
    p.add_argument("--graduation",required=True)
    p.add_argument("--operational",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args(argv)
    root=Path(args.root).resolve()
    read=lambda path: json.loads(Path(path).read_text(encoding="utf8"))
    result=crosswalk(read(args.graduation),read(args.operational),
                     code_file_exists=lambda rel:(root/rel).is_file())
    Path(args.out).write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,
                                separators=(",",":"))+"\n",encoding="utf8")
    print("KYOTO_RESEARCH_TO_LIVE_VERIFIED="+str(result["research_to_live_verified_areas"])+"/6")
    print("KYOTO_RESEARCH_TO_LIVE_CONNECTED="+str(result["all_connected"]).upper())
    return result

if __name__=="__main__":main()
