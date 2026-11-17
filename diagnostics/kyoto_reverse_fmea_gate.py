"""Independent reverse-coverage FMEA: source AST first, not test-count first.

Exact source bytes are compared to the registered baseline commit. Newly
introduced functions or changed executable source force re-review, rather than
silently inheriting a previous PASS label. All uncovered risks stay explicit.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

LEDGER="docs/diagnostics/KYOTO_REVERSE_FMEA_GAP_REGISTER_20261116.json"
OLD_MATRIX="docs/diagnostics/KYOTO_PREDICTABLE_FAILURE_MATRIX_20261116.json"
KNOWN_RISKS={f"GAP-{i:02d}" for i in range(1,23)}

class AuditCoverageRejected(ValueError): pass

def reachable_local_modules(root:Path, seed_files:set[str]) -> set[str]:
    """Discover transitive function-local and top-level diagnostics imports."""
    pending=list(seed_files)
    known=set()
    while pending:
        path=pending.pop()
        if path in known:
            continue
        source=root/path
        if not source.is_file() or source.is_symlink():
            continue
        known.add(path)
        try:
            tree=ast.parse(source.read_bytes(),filename=path)
        except SyntaxError as exc:
            raise AuditCoverageRejected(f"dependency_not_parseable:{path}") from exc
        for node in ast.walk(tree):
            modules=[]
            if isinstance(node,ast.Import):
                modules.extend(a.name for a in node.names)
            elif isinstance(node,ast.ImportFrom) and node.module:
                modules.append(node.module)
                modules.extend(node.module+"."+alias.name for alias in node.names)
            for name in modules:
                if name.startswith("diagnostics."):
                    candidate=name.replace(".","/")+".py"
                    if candidate not in known and (root/candidate).is_file():
                        pending.append(candidate)
    return known



def inspect(root:Path, ledger:dict, *, verify_git:bool=True) -> dict:
    if ledger.get("schema")!="kyoto_fmea_reverse_coverage_v1":
        raise AuditCoverageRejected("incorrect_fmea_schema")
    surfaces=ledger.get("surfaces",[])
    risks=ledger.get("risks",[])
    baseline=ledger.get("source_commit")
    if not isinstance(baseline,str) or len(baseline)!=40:
        raise AuditCoverageRejected("missing_source_commit")
    if not isinstance(surfaces,list) or len(surfaces)<29:
        raise AuditCoverageRejected("source_surface_register_incomplete")
    if not isinstance(risks,list) or {x.get("id") for x in risks}!=KNOWN_RISKS:
        raise AuditCoverageRejected("known_predictable_risk_missing_or_added_without_review")
    actual=set()
    class_methods=set()
    dynamic_import_markers=[]
    source_sha={}
    files={s["source"] for s in surfaces}
    if len(files)!=22:
        raise AuditCoverageRejected("source_module_inventory_incomplete")
    for file in files:
        path=root/file
        if not path.is_file() or path.is_symlink():
            raise AuditCoverageRejected("critical_source_missing_or_symlink")
        raw=path.read_bytes()
        source_sha[file]=hashlib.sha256(raw).hexdigest()
        try: tree=ast.parse(raw,filename=file)
        except SyntaxError as exc:
            raise AuditCoverageRejected("critical_source_not_parseable") from exc
        for node in tree.body:
            if isinstance(node,ast.ClassDef):
                for child in node.body:
                    if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef)):
                        class_methods.add(f"{file}:{node.name}.{child.name}")
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=="__import__":
                dynamic_import_markers.append(file)
            elif isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=="import_module":
                dynamic_import_markers.append(file)
        names=[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
        if len(names)!=len(set(names)):
            raise AuditCoverageRejected("duplicate_function_name")
        actual.update(f"{file}:{name}" for name in names)
        if verify_git:
            frozen_blobs=ledger.get("source_git_blob_sha1",{})
            if (set(frozen_blobs)!={s["source"] for s in surfaces}
                or not all(isinstance(value,str) and len(value)==40
                           for value in frozen_blobs.values())):
                raise AuditCoverageRejected("locked_source_blob_registry_missing")
            # GitHub checkout is intentionally shallow. Git hash-object hashes
            # actual bytes without depending on historical commits present
            # in the local checkout.
            try:
                observed=subprocess.check_output(
                    ["git","hash-object",str(path)],cwd=root,
                    stderr=subprocess.PIPE,timeout=7,text=True).strip()
            except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
                raise AuditCoverageRejected("source_hashing_failed") from exc
            if observed!=frozen_blobs[file]:
                raise AuditCoverageRejected(f"source_changed_requires_new_fmea:{file}")
    reviewed=[f"{s['source']}:{s['function']}" for s in surfaces]
    if len(reviewed)!=len(set(reviewed)) or actual!=set(reviewed):
        missing=actual-set(reviewed)
        stale=set(reviewed)-actual
        raise AuditCoverageRejected(f"unreviewed_or_stale_functions:missing={sorted(missing)}:stale={sorted(stale)}")
    risk_ids=set()
    referenced=set()
    for risk in risks:
        rid=risk.get("id")
        if rid in risk_ids: raise AuditCoverageRejected("duplicate_risk")
        risk_ids.add(rid)
        paths=risk.get("affected_surfaces")
        if not isinstance(paths,list) or len(paths)<2:
            raise AuditCoverageRejected("risk_missing_independent_function_paths")
        for item in paths:
            if not isinstance(item,str) or item.count(":")!=1:
                raise AuditCoverageRejected("invalid_risk_function_path")
            file_short,func=item.split(":")
            matched=[p for p in actual if p.endswith("/"+file_short+":"+func)]
            if len(matched)!=1:
                raise AuditCoverageRejected(f"risk_references_nonexistent_function:{rid}:{item}")
            referenced.add(matched[0])
        if risk.get("test_proven") is not False or risk.get("remediated") is not False:
            raise AuditCoverageRejected("unverified_risk_was_silently_marked_fixed")
        if risk.get("severity") not in ("BLOCKER","OPEN"):
            raise AuditCoverageRejected("invalid_risk_severity")
    old=json.loads((root/OLD_MATRIX).read_text(encoding="utf8"))
    if old.get("schema")!="kyoto_predictable_failure_matrix.v1" or len(old.get("entries",[]))!=30:
        raise AuditCoverageRejected("previous_test_baseline_unavailable")
    all_reachable=reachable_local_modules(root,files)
    imported_not_yet_reviewed=sorted(all_reachable-files)
    return {
        "schema":"kyoto_reverse_fmea_examination_v1",
        "source_commit":baseline,
        "source_sha256":source_sha,
        "critical_modules":len(files),
        "class_methods_discovered_but_not_yet_independently_reviewed":len(class_methods),
        "class_method_paths_not_yet_reviewed":sorted(class_methods),
        "dynamic_import_sites":sorted(set(dynamic_import_markers)),
        "top_level_functions_not_yet_independently_reviewed":len([s for s in surfaces if s.get("review_status")=="UNREVIEWED_INDEPENDENT_FMEA"]),
        "reachable_local_diagnostics_modules":len(all_reachable),
        "additional_reachable_modules_not_yet_reviewed":len(imported_not_yet_reviewed),
        "additional_reachable_module_paths":imported_not_yet_reviewed,
        "top_level_functions_discovered":len(actual),
        "top_level_functions_registered":len(reviewed),
        "top_level_functions_unregistered":0,
        "functions_without_linked_new_risk":sorted(actual-referenced),
        "previous_tests_count":len(old["entries"]),
        "additional_predictable_failure_families":len(risks),
        "high_severity_unresolved":len([r for r in risks if r["severity"]=="BLOCKER"]),
        "all_additional_risks_unresolved":True,
        "completeness_demonstrated":False,
        "evidence_scope":"source_AST_and_frozen_code+FMEA_register_only",
        "note":"Absence of unregistered functions does not prove absence of failures in APIs, external HTML, cross-run race conditions, subprocesses or dependencies.",
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path("."))
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--require-closed",action="store_true")
    args=p.parse_args()
    root=args.root.resolve()
    ledger_path=root/LEDGER
    ledger=json.loads(ledger_path.read_text(encoding="utf8"))
    result=inspect(root,ledger)
    result["evaluated_at_utc"]=datetime.now(timezone.utc).isoformat()
    result["ledger_sha256"]=hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf8")
    print(f"INDEPENDENT_AST_SURFACES={result['top_level_functions_discovered']}/{result['top_level_functions_registered']}")
    print(f"NEW_PREDICTABLE_RISKS={result['additional_predictable_failure_families']}")
    print(f"UNREVIEWED_REACHABLE_MODULES={result['additional_reachable_modules_not_yet_reviewed']}")
    print(f"UNREVIEWED_TOP_LEVEL_FUNCTIONS={result['top_level_functions_not_yet_independently_reviewed']}")
    print(f"UNREVIEWED_CLASS_METHODS={result['class_methods_discovered_but_not_yet_independently_reviewed']}")
    for name in result["additional_reachable_module_paths"]:
        print("UNREVIEWED_DEPENDENCY="+name)
    print(f"UNRESOLVED_HIGH={result['high_severity_unresolved']}")
    print("FORESEEABLE_FAILURE_COMPLETENESS=NOT_DEMONSTRATED")
    if args.require_closed:
        raise SystemExit("RELEASE_CERTIFICATION_BLOCKED_BY_UNRESOLVED_FMEA_RISKS")

if __name__=="__main__":
    main()
