"""Immutable-style evidence report for the Impl26 A-D final completion gate."""
import argparse
import json
import os
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

JOBS=("full-static-and-contracts","collector-full12-and-aes",
      "destructive-and-turso","time-and-night-before")
GROUPS={
    "D1":{"requires":"Static+AST 100%, unresolved signatures/imports/branches covered"},
    "D2":{"requires":"Single connected 12R G03-G06 -> AES -> all-run -> day22 E2E proof"},
    "D3":{"requires":"All required destructive cases, source survival and negative guards"},
    "D4":{"requires":"40 risks plus all incidents regression, idempotence, rollback"},
    "D5":{"requires":"PC/SP/market/horse time budgets validated with bounded end-to-end performance"},
    "D6":{"requires":"Independent evidence, recovery and formally reviewed GO/NO_GO"},
}
def summarize(ledger,jobs,sha):
    risks=ledger["risks"]
    assert len(risks)==40 and len({r["id"] for r in risks})==40
    statuses={x["name"]:x.get("conclusion") for x in jobs.get("jobs",[])}
    observed={name:statuses.get(name,"MISSING") for name in JOBS}
    counts={priority:Counter(r["status"] for r in risks if r["priority"]==priority)
            for priority in ("P0","P1","P2")}
    proven={p:counts[p].get("MITIGATED_WITH_PROOF",0)+counts[p].get("ACCEPTED_WITH_REASON",0)
            for p in counts}
    incs=ledger.get("incidents",[])
    # A successful broad CI is necessary but not sufficient for formal stage D.
    all_ci=all(x=="success" for x in observed.values())
    gates={}
    for key,value in GROUPS.items():
        gates[key]={"status":"PARTIAL" if all_ci else "BLOCKED",
                    "required":value["requires"],"formal_pass":False}
    if proven["P0"]<20:
        gates["D4"]["status"]="BLOCKED"
    final_go=False
    return {
        "schema":"kyoto_impl26_final_evidence_verdict.v1",
        "generated_utc":datetime.now(timezone.utc).isoformat(),
        "candidate_sha":sha,"collector_sha":"de2544c1e9f9951a265419461267146b4023c2ab",
        "source_only":True,"production_live_success_not_claimed":True,
        "risk_total":40,"risk_breakdown":{"P0":20,"P1":19,"P2":1},
        "proof_qualified":proven,
        "unknown_incidents":len(incs),
        "unclosed_incidents":sum(i.get("status")!="CLOSED" for i in incs),
        "broad_ci_jobs":observed,
        "broad_ci_all_pass":all_ci,
        "static_ast_files_previous_ci_lower_bound":576 if all_ci else None,
        "yaml_files_previous_ci_lower_bound":47 if all_ci else None,
        "unit_tests_previous_ci_lower_bound":251 if all_ci else None,
        "final_six_gates":gates,
        "final_decision":"GO" if final_go else "NO_GO",
        "blockers":[
            "P0 unresolved/proof-unqualified: "+str(20-proven["P0"])+"/20",
            "P1 unresolved/proof-unqualified: "+str(19-proven["P1"])+"/19",
            "INC remediation and all-transition proof remain incomplete",
            "Stage D full function-call/E2E/injection/performance/recheck six-group certification incomplete",
        ],
        "rollback_references":[
            "backup/impl26-nov21-sp12-deployed-20261120",
            "backup/impl26-sp12-collector-de254-20261120",
        ],
        "no_automated_collector_sha_promotion":True,
    }
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--ledger",default="audit/impl26_fixed_risk_status.json")
    parser.add_argument("--jobs",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    data=summarize(json.loads(Path(args.ledger).read_text()),
                   json.loads(Path(args.jobs).read_text()),os.getenv("GITHUB_SHA","UNKNOWN"))
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,sort_keys=True,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    md=["# 実装26 最終総合バグチェック・独立判定","",
        "判定: **"+data["final_decision"]+"**",
        "候補SHA: "+data["candidate_sha"],"",
        "P0: "+str(data["proof_qualified"]["P0"])+"/20",
        "P1: "+str(data["proof_qualified"]["P1"])+"/19",
        "未閉鎖INC: "+str(data["unclosed_incidents"]), "",
        "| 大分類 | CI/認定 |","|---|---|"]
    md += ["| "+name+" | "+detail["status"]+" |" for name,detail in data["final_six_gates"].items()]
    md += ["","## 未完了の合格条件"]+["- "+x for x in data["blockers"]]
    path.with_suffix(".md").write_text("\n".join(md)+"\n",encoding="utf8")
    print("IMPL26_FINAL_EVIDENCE",data["final_decision"],
          "A_P0",data["proof_qualified"]["P0"],"A_P1",data["proof_qualified"]["P1"],
          "B_INC",data["unclosed_incidents"],"CI_4_OF_4",data["broad_ci_all_pass"])
if __name__=="__main__":
    main()
