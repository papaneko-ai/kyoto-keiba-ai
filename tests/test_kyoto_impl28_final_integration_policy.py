"""Offline contract for the approved finish-stage consolidation policy."""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
POLICY=ROOT/"docs/KYOTO_AI_FINAL_INTEGRATION_LIGHTWEIGHT_AND_RECOVERY_POLICY_20261120.md"
ROADMAP=ROOT/"docs/KYOTO_IMPL26_A_TO_D_FINAL_GATE_PROGRESS_20261120.md"
RISK=ROOT/"docs/KYOTO_IMPL26_RISK_AND_INCIDENT_EVOLUTION_20261120.md"

class FinalIntegrationPolicy(unittest.TestCase):
    def test_policy_is_normatively_linked_from_existing_final_gate(self):
        p=POLICY.read_text(encoding="utf-8")
        roadmap=ROADMAP.read_text(encoding="utf-8")
        self.assertIn(POLICY.name,roadmap)
        self.assertIn("D1～D6",p)
        self.assertIn("コンパイル",p)
        self.assertIn("Python",p)
        self.assertIn("Streamlit",p)
    def test_both_deployment_and_recovery_are_mandatory(self):
        p=POLICY.read_text(encoding="utf-8")
        for phrase in ["実運用版","完全復旧版","SHA256","P1～P8","ALG-01～13","EVO-01～08","スマホ","仮想投資","Turso","依存"]:
            self.assertIn(phrase,p)
    def test_preserve_existing_gate_and_risk_denominators(self):
        p=POLICY.read_text(encoding="utf-8")
        r=RISK.read_text(encoding="utf-8")
        ids=[line.split(" | ")[1] for line in r.splitlines() if line.startswith("| R") and " | P" in line]
        self.assertEqual(len(ids),40)
        self.assertEqual(len(set(ids)),40)
        for s in ["P0 11/20","P1 4/19","P2 0/1","D 2/6","NO_GO"]:
            self.assertIn(s,p)
        self.assertIn("新たな「D7」は作らない",p)
    def test_retain_8_slot_source_and_secrets_protection(self):
        p=POLICY.read_text(encoding="utf-8")
        self.assertIn("11-21/22",p)
        for s in ["8予約枠","Secrets","Turso","本番main","固定collector"]:
            self.assertIn(s,p)
    def test_no_completion_false_pass(self):
        p=POLICY.read_text(encoding="utf-8")
        for s in ["本方針の記録を理由","軽量化","NO_GO","未実装・未検証"]:
            self.assertIn(s,p)

if __name__=="__main__":
    unittest.main()
