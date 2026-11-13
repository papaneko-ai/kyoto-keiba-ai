"""Evidence-scored fixed 16-gate readiness before authentic JRA acquisition.

The four initial scoped receipts are established by rerunning exact named
destructive/positive LAB test suites. Other gates remain unverified.
No JRA network, real betting, secret access or production modifications.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

RUBRIC="docs/diagnostics/kyoto_predata_readiness_rubric_v1.json"
CHECKS={
    "R03":("test_p2_first_second_feature_discovery_lab.py",12),
    "R05":("test_p3_three_window_selection_lab.py",13),
    "R06":("test_r06_pair_frame_fixed_acceptance.py",14),
    "R09":("test_p3_p5_p6_synthetic_day_lab.py",14),
    "R12":("test_p6_virtual_settlement_fixture_lab.py",18),
}
IDS=tuple(f"R{i:02d}" for i in range(1,17))
class ReadinessRejected(ValueError):pass

def _json_bytes(v):
    return json.dumps(v,ensure_ascii=False,sort_keys=True,
                      separators=(",",":"),allow_nan=False).encode("utf-8")

def digest(v):
    return sha256(_json_bytes(v)).hexdigest()

def verify_rubric(rubric):
    if (type(rubric) is not dict or rubric.get("schema")!="kyoto_predata_readiness_rubric.v1"
        or rubric.get("denominator")!=16 or type(rubric.get("gates")) is not list
        or len(rubric["gates"])!=16
        or tuple(x.get("id") for x in rubric["gates"] if type(x) is dict)!=IDS):
        raise ReadinessRejected("fixed_rubric_identity_invalid")
    for gate in rubric["gates"]:
        if (set(gate)!={"id","title","phase","acceptance","automation"}
            or any(type(gate[k]) is not str or not gate[k].strip()
                   for k in ("title","phase","acceptance"))
            or (gate["automation"] is not None and
                (gate["id"] not in CHECKS or gate["automation"]!={"suite":CHECKS[gate["id"]][0],"tests":CHECKS[gate["id"]][1]}))):
            raise ReadinessRejected("fixed_gate_schema_or_test_contract_changed")
    return True

def evaluate(root, *, run_tests=True, results=None):
    root=Path(root)
    raw=(root/RUBRIC).read_bytes()
    rubric=json.loads(raw.decode("utf-8"))
    verify_rubric(rubric)
    if results is not None and (type(results) is not dict or set(results)!=set(CHECKS)
        or any(type(v) is not bool for v in results.values())):
        raise ReadinessRejected("test_attestation_schema_invalid")
    completed={}
    for gate_id,(filename,expected_count) in CHECKS.items():
        if not (root/"tests"/filename).is_file():
            raise ReadinessRejected("required_test_missing:"+gate_id)
        if results is not None:
            completed[gate_id]=results[gate_id]
            continue
        if not run_tests:
            completed[gate_id]=False
            continue
        proc=subprocess.run(
            [sys.executable,"-m","unittest","discover","-s","tests",
             "-p",filename,"-v"],cwd=root,capture_output=True,
            text=True,timeout=90,check=False)
        print("READINESS_TEST_GATE="+gate_id+" rc="+str(proc.returncode),flush=True)
        print(proc.stdout[-1500:],flush=True)
        print(proc.stderr[-3000:],flush=True)
        # unittest's summary must match the frozen test family size.
        evidence=proc.stdout+"\n"+proc.stderr
        completed[gate_id]=(proc.returncode==0 and
                            "Ran "+str(expected_count)+" tests in " in evidence
                            and "\nOK" in evidence)
    rows=[]
    for gate in rubric["gates"]:
        gid=gate["id"]
        passed=completed.get(gid,False)
        rows.append({"id":gid,"title":gate["title"],
                     "state":"PASS_OFFLINE_SCOPE_ONLY" if passed else "UNVERIFIED",
                     "evidence_suite":CHECKS[gid][0] if passed else None,
                     "contributes_to_real_operational_score":False})
    count=sum(x["state"]=="PASS_OFFLINE_SCOPE_ONLY" for x in rows)
    body={"schema":"kyoto_predata_readiness_report.v1",
         "rubric_sha256":sha256(raw).hexdigest(),
         "total_gates":16,"passed_gates":count,
         "remaining_gates":16-count,"completion_percent":round(100*count/16,2),
         "accepted_gate_ids":[x["id"] for x in rows if x["state"]=="PASS_OFFLINE_SCOPE_ONLY"],
         "gates":rows,"all_pass":count==16,
         "real_jra_authenticated":False,
         "live_paper_trading_authorized":False,
         "original_20_gate_score_unchanged":True,
         "revert_to_original_scoring_now":count==16}
    return {**body,"report_sha256":digest(body)}

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=".")
    p.add_argument("--out",required=True)
    args=p.parse_args(argv)
    result=evaluate(args.root)
    output=Path(args.out)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PRE_JRA_READINESS="+str(result["passed_gates"])+"/16 ("+
          str(result["completion_percent"])+"%)")
    print("PRE_JRA_READINESS_REVERT_ONLY_ON_100="+str(result["revert_to_original_scoring_now"]))

if __name__=="__main__":main()
