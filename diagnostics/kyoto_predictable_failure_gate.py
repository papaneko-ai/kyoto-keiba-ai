"""Executable coverage audit for foreseeable Kyoto race-data acquisition failures.

Coverage is defined before execution in a locked, versioned matrix.  Each
listed test is found by parsing the actual Python AST and is run in a separate
Python unittest subprocess. No successful test is inferred from its name.

This checks the enumerated predictable risks, not unknowable live HTML states.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MATRIX = "docs/diagnostics/KYOTO_PREDICTABLE_FAILURE_MATRIX_20261116.json"
PHASES = {"pre_http","navigation","transport","timestamp","provenance",
          "capture","storage","handoff","false_success","cross_host"}
KINDS = {"valid","negative","boundary","adversarial","integration","destructive"}

class MatrixRejected(ValueError):
    pass

def verify_matrix(root: Path, payload: dict) -> list[dict]:
    """Validate the coverage contract before running any listed test."""
    if not isinstance(payload,dict) or payload.get("schema")!="kyoto_predictable_failure_matrix.v1":
        raise MatrixRejected("schema_invalid")
    if set(payload.get("required_phases",[]))!=PHASES:
        raise MatrixRejected("required_phases_missing")
    if set(payload.get("required_kinds",[]))!=KINDS:
        raise MatrixRejected("required_kinds_missing")
    policy=payload.get("policy",{})
    if any(policy.get(name) is not True for name in
           ("zero_missing_tests","zero_duplicate_ids","runner_requires_execution_receipts",
            "no_synthetic_live_success","zero_predicted_market_acceptance_without_verified_source")):
        raise MatrixRejected("policy_weakened")
    entries=payload.get("entries")
    if not isinstance(entries,list) or len(entries)<30:
        raise MatrixRejected("insufficient_risk_coverage")
    seen=set()
    actual_phases=set()
    actual_kinds=set()
    prepared=[]
    for index,entry in enumerate(entries):
        if not isinstance(entry,dict):
            raise MatrixRejected(f"entry_not_object:{index}")
        required=("id","phase","risk","kind","test_file","test","source_file","source_token")
        if not all(isinstance(entry.get(k),str) and entry[k] for k in required):
            raise MatrixRejected(f"incomplete_entry:{index}")
        rid=entry["id"]
        if rid in seen:
            raise MatrixRejected(f"duplicate_id:{rid}")
        seen.add(rid)
        if entry["phase"] not in PHASES or entry["kind"] not in KINDS:
            raise MatrixRejected(f"unknown_axis:{rid}")
        actual_phases.add(entry["phase"])
        actual_kinds.add(entry["kind"])
        test_path=Path(entry["test_file"])
        source_path=Path(entry["source_file"])
        if (test_path.is_absolute() or source_path.is_absolute()
            or ".." in test_path.parts or ".." in source_path.parts
            or not str(test_path).startswith("tests/")
            or not test_path.suffix==".py"):
            raise MatrixRejected(f"path_out_of_scope:{rid}")
        for path in (test_path,source_path):
            full=root / path
            if not full.is_file() or full.is_symlink():
                raise MatrixRejected(f"source_or_test_absent:{rid}:{path}")
        source=(root/source_path).read_text(encoding="utf8")
        if entry["source_token"] not in source:
            raise MatrixRejected(f"source_invariant_absent:{rid}")
        code=(root/test_path).read_text(encoding="utf8")
        try:
            tree=ast.parse(code)
        except SyntaxError as exc:
            raise MatrixRejected(f"test_syntax_invalid:{rid}") from exc
        cls=[node.name for node in tree.body if isinstance(node,ast.ClassDef)
             and any(isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef))
                     and f.name==entry["test"] for f in node.body)]
        if len(cls)!=1:
            raise MatrixRejected(f"test_method_missing_or_ambiguous:{rid}")
        dotted=".".join(test_path.with_suffix("").parts)+"."+cls[0]+"."+entry["test"]
        prepared.append({"id":rid,"case":dotted,"day":"20261115" if
            ("nov15" in test_path.name or test_path.name=="test_kyoto_sp_observed_source.py")
            else "20261121"})
    if actual_phases!=PHASES or actual_kinds!=KINDS:
        raise MatrixRejected("risk_axes_not_covered")
    deferred=payload.get("explicit_deferred_gates")
    if (not isinstance(deferred,list) or len(deferred)<3
        or any(d.get("may_use_for_prediction") is not False for d in deferred)):
        raise MatrixRejected("live_deferred_gates_missing_or_weakened")
    return prepared

def audit(root: Path, manifest: Path, report: Path, *, execute: bool=True) -> dict:
    root=root.resolve()
    raw=manifest.read_bytes()
    payload=json.loads(raw.decode("utf8"))
    prepared=verify_matrix(root,payload)
    checks=[]
    for case in prepared:
        result={"id":case["id"],"test":case["case"],"target_day":case["day"],
                "state":"NOT_EXECUTED"}
        if execute:
            env=os.environ.copy()
            env["KYOTO_TARGET_DAY"]=case["day"]
            env["PYTHONPATH"]=str(root)
            try:
                proc=subprocess.run([sys.executable,"-m","unittest","-q",case["case"]],
                    cwd=root,env=env,capture_output=True,text=True,timeout=35)
                result["state"]="PASS" if proc.returncode==0 else "FAIL"
                result["returncode"]=proc.returncode
                result["log_tail"]=(proc.stdout+"\n"+proc.stderr)[-1100:]
            except subprocess.TimeoutExpired:
                result["state"]="TIMEOUT"
            except OSError as exc:
                result["state"]="EXECUTION_ERROR"
                result["error_class"]=type(exc).__name__
        checks.append(result)
    passing=sum(c["state"]=="PASS" for c in checks)
    result={
        "schema":"kyoto_predictable_failure_execution.v1",
        "evaluated_at_utc":datetime.now(timezone.utc).isoformat(),
        "matrix_sha256":hashlib.sha256(raw).hexdigest(),
        "matrix_path":str(manifest.relative_to(root)) if manifest.is_relative_to(root) else str(manifest),
        "count":len(checks),"passing":passing,
        "failed":len(checks)-passing,
        "all_enumerated_coverage_tests_passed":passing==len(checks) and execute,
        "live_jra_proven":False,
        "prediction_ready":False,
        "source_only_observation":True,
        "deferred_gates":payload["explicit_deferred_gates"],
        "tests":checks,
    }
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path("."))
    p.add_argument("--matrix",type=Path,default=Path(MATRIX))
    p.add_argument("--report",type=Path,required=True)
    args=p.parse_args()
    root=args.root.resolve()
    matrix=args.matrix if args.matrix.is_absolute() else root/args.matrix
    summary=audit(root,matrix,args.report)
    print(f"FORESEEABLE_RISK_CASES={summary['passing']}/{summary['count']}")
    print(f"UNRESOLVED_TESTS={summary['failed']}")
    print("LIVE_JRA_PROVEN=FALSE")
    print("PREDICTION_READY=FALSE")
    if not summary["all_enumerated_coverage_tests_passed"]:
        raise SystemExit(1)

if __name__=="__main__":
    main()
