"""Fail-closed Impl26 risk/incident/final-bug-gate verifier (stdlib only)."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
risk_doc = (ROOT / "docs/KYOTO_IMPL26_RISK_AND_INCIDENT_EVOLUTION_20261120.md").read_text(encoding="utf-8")
instructions = (ROOT / "docs/KYOTO_IMPL26_START_INSTRUCTIONS_AND_INCIDENT_AUTOMATION_20261120.md").read_text(encoding="utf-8")
ledger = json.loads((ROOT / "audit/impl26_fixed_risk_status.json").read_text(encoding="utf-8"))
workflow = (ROOT / ".github/workflows/kyoto-20261121-22-two-source-production-observer.yml").read_text(encoding="utf-8")
assert "段階D：全体横断の最終バグチェック" in instructions
assert "最重要・既存必須検査ゲート違反" in instructions
assert "次セクションの終点" in risk_doc
canonical = {}
for line in risk_doc.splitlines():
    m = re.match(r"^\| (R\d\d) \| (P[012]) \|", line)
    if m:
        if m.group(1) in canonical:
            raise SystemExit("DUPLICATE_RISK_ID")
        canonical[m.group(1)] = m.group(2)
expected = {f"R{i:02d}" for i in range(1,41)}
assert set(canonical) == expected, "CANONICAL_RISK_SCOPE_NOT_40"
assert [list(canonical.values()).count(p) for p in ("P0","P1","P2")] == [20,19,1]
entries = ledger["risks"]
assert len(entries) == 40 and {x["id"] for x in entries} == expected
allowed = {"OPEN","MITIGATED_WITH_PROOF","LIVE_VERIFICATION_PENDING",
           "ACCEPTED_WITH_REASON","INCIDENT_ACTIVE"}
counts = {"P0":0,"P1":0,"P2":0}
for x in entries:
    assert x["priority"] == canonical[x["id"]]
    assert x["status"] in allowed
    assert x.get("triage_complete") is True and x.get("next_evidence") and x.get("review_due_utc"), f"{x['id']}: TRIAGE_INCOMPLETE"
    if x["status"] in {"MITIGATED_WITH_PROOF","ACCEPTED_WITH_REASON"}:
        assert x.get("proof"), f"{x['id']}: EMPTY_PROOF_NOT_ALLOWED"
        if x["status"]=="ACCEPTED_WITH_REASON":
            assert x.get("acceptance_reason") and x.get("review_due_utc"), x["id"]
        counts[x["priority"]] += 1
# P0/P1 denominators are never inferred from test numbers.
scheduled = []
for line in workflow.splitlines():
    m = re.search(r"^\s+- cron: '([^']+)'", line)
    if m:
        scheduled.append(m.group(1))
assert scheduled == [
    "15 0 21 11 *","15 1 21 11 *","5 2 21 11 *","50 2 21 11 *",
    "15 0 22 11 *","15 1 22 11 *","10 2 22 11 *","55 2 22 11 *",
], "EIGHT_SCHEDULE_REGRESSION"
for token in ["needs: pc-originals-independent", "AES-GCM ciphertext or safe-stop receipt",
              "DAY22_CANDIDATE_NOT_PREFLIGHT_VERIFIED_NO_HTTP",
              "cancel-in-progress: false"]:
    assert token in workflow, f"PROTECTED_WORKFLOW_REGRESSION: {token}"
expected_checks = {
    "static_and_function_calls", "end_to_end_12R", "destructive_fault_injection",
    "risk_and_incident_regression", "performance_and_deadlines",
    "independent_report_and_decision"}
gate = ledger["final_gate"]
assert set(gate["checks"]) == expected_checks
for name, chk in gate["checks"].items():
    assert chk["status"] in {"NOT_RUN","PASS","FAIL","BLOCKED"}
    if chk["status"] == "PASS":
        assert chk.get("proof"), f"{name}: UNPROVEN_PASS"
all_pass = all(x["status"]=="PASS" for x in gate["checks"].values())
critical_open = any(x["priority"]=="P0" and x["status"] not in
                    {"MITIGATED_WITH_PROOF","ACCEPTED_WITH_REASON"}
                    for x in entries)
active_inc = any(x.get("status") != "CLOSED" for x in ledger["incidents"])
go = all_pass and not critical_open and not active_inc
if gate["status"]=="GO" and not go:
    raise SystemExit("FALSE_GO_NOT_ALLOWED")
print(f"IMPL26_LEDGER_VALID P0={counts['P0']}/20 P1={counts['P1']}/19 P2={counts['P2']}/1")
print(f"FINAL_AUDIT_GO={'YES' if go else 'NO'}; stage_D_pass={sum(x['status']=='PASS' for x in gate['checks'].values())}/6")
if "--require-go" in sys.argv and not go:
    raise SystemExit("NO_GO_FINAL_CHECK_INCOMPLETE")
