"""Execute both production release gate Python blocks with zero JRA network.

The inspected code is extracted from the actual main-branch workflow, not a
parallel reimplementation of its admission conditions.
"""
import io
import json
import os
import re
import subprocess
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import request

WORKFLOW=Path(".github/workflows/kyoto-20261121-22-two-source-production-observer.yml")
LEDGER=Path("docs/diagnostics/KYOTO_20261116_INDEPENDENT_RELEASE_BLOCKERS.json")
SHA="d5e0de7cc39afe8fd168f40a1915e9ddfb668f1a"
RECEIPT="KYOTO-AUDIT-20261121-independent001"

def source_blocks():
    s=WORKFLOW.read_text(encoding="utf8")
    key="      - name: Independent release authorization gate blocks unresolved critical defects before JRA HTTP"
    parts=s.split(key)
    if len(parts)!=3:
        raise AssertionError("both production release gates must exist")
    result=[]
    for block in parts[1:]:
        block=block.split("      - name: Race date, immutable commit, secret, first attempt and non-replay guard",1)[0]
        raw=block.split("python - <<'PY'\n",1)[1].split("\n          PY",1)[0]
        result.append(textwrap.dedent(raw))
    return result

def run_block(source,ledger,*,approved_vars):
    env={"COLLECTOR_SHA":SHA,"RELEASED_SOURCE_SHA":SHA if approved_vars else "",
         "RELEASE_RECEIPT_ID":RECEIPT if approved_vars else "",
         "GITHUB_REPOSITORY":"papaneko-ai/kyoto-keiba-ai",
         "GH_TOKEN":"test-github-token"}
    doc={"content":__import__("base64").b64encode(json.dumps(ledger).encode()).decode()}
    calls=[]
    def fake_urlopen(req,timeout=12):
        url=req.full_url
        calls.append(url)
        if "api.github.com" not in url or "RELEASE_BLOCKERS" not in url:
            raise AssertionError("unexpected external call")
        return io.BytesIO(json.dumps(doc).encode("utf8"))
    with patch.dict(os.environ,env),patch("subprocess.check_output",return_value=SHA+"\n"),patch.object(request,"urlopen",fake_urlopen):
        exec(compile(source,"production_release_gate","exec"),{"__name__":"__main__"})
    return calls

class ProductionReleaseGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blocks=source_blocks()
        cls.ledger=json.loads(LEDGER.read_text(encoding="utf8"))
    def test_open_issues_exist_and_are_high_critical(self):
        self.assertEqual(self.ledger["status"],"RELEASE_BLOCKED")
        self.assertGreaterEqual(len(self.ledger["issues"]),6)
        self.assertTrue(any(x["severity"]=="CRITICAL" for x in self.ledger["issues"]))
        self.assertTrue(all(x["state"]=="OPEN" for x in self.ledger["issues"]))
    def test_both_lanes_reject_unapproved_even_before_github_lookup(self):
        for block in self.blocks:
            with self.subTest(block=block[:30]):
                with self.assertRaisesRegex(SystemExit,"UNRELEASED_OR_CRITICAL_FINDINGS_OPEN_NO_JRA_HTTP"):
                    run_block(block,self.ledger,approved_vars=False)
    def test_even_forged_matching_vars_cannot_override_open_register(self):
        for block in self.blocks:
            with self.subTest(block=block[:30]):
                with self.assertRaisesRegex(SystemExit,"RELEASE_REGISTER_NOT_INDEPENDENTLY_CLEARED_NO_JRA_HTTP"):
                    run_block(block,self.ledger,approved_vars=True)
    def test_hypothetical_closed_register_requires_evidence_and_sha(self):
        closed=json.loads(json.dumps(self.ledger))
        closed["status"]="RELEASE_AUTHORIZED"
        closed["issues"]=[{**x,"state":"CLOSED_WITH_INDEPENDENT_EVIDENCE"} for x in closed["issues"]]
        closed["required_approval"]={
            "status":"APPROVED","approved_commit_sha":SHA,"receipt":RECEIPT,
            "independent_source_recheck":True,"full_e2e_test":True}
        # This proves conditional logic, NOT that any real finding is resolved.
        for block in self.blocks:
            self.assertEqual(len(run_block(block,closed,approved_vars=True)),1)
        closed["required_approval"]["full_e2e_test"]=False
        for block in self.blocks:
            with self.assertRaisesRegex(SystemExit,"RELEASE_REGISTER_NOT_INDEPENDENTLY_CLEARED_NO_JRA_HTTP"):
                run_block(block,closed,approved_vars=True)

if __name__=="__main__":
    unittest.main()
