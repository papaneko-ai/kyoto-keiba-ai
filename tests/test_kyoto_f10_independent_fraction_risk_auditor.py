"""F10 second-independent risk auditor: corruption and false live-state checks."""
import copy,unittest
from pathlib import Path
from tests.test_kyoto_f10_conservative_capital_overlay import fixture
from diagnostics.kyoto_f10_conservative_capital_overlay import overlay_lab_risk
from diagnostics.kyoto_f10_independent_fraction_risk_auditor import verify,F10AuditRejected,digest

class IndependentF10Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rubric=Path("docs/diagnostics/kyoto_final_completion_criteria_v1.json").read_bytes()
    def witness(self):
        hand,quotes=fixture()
        decision=overlay_lab_risk(f11_handoff=hand,lab_quotes=quotes,
                                  decision_utc="2026-11-14T03:05:00Z")
        return {
            "schema":"kyoto_F10_offline_risk_witness.v1",
            "ci_run_id":"43136221923",
            "ci_head_sha":"b34c2d8005e93cc75475dcd05a715cc22dc0ee60",
            "lab_source_f11_f12_handoff":hand,
            "lab_quotes":quotes,"decision":decision,
            "real_market_authenticated":False,
            "production_paper_trade_authorized":False}
    def test_verified_witness(self):
        x=verify(self.witness(),self.rubric)
        self.assertEqual(x["accepted_points"],5)
        self.assertFalse(x["actual_paper_trade_verified"])
    def test_rehashed_wrong_stake_rejected(self):
        w=self.witness()
        w["decision"]["decisions"][0]["accepted_stake_yen"]+=100
        w["decision"]["risk_sha256"]=digest({k:v for k,v in w["decision"].items() if k!="risk_sha256"})
        with self.assertRaisesRegex(F10AuditRejected,"independently_recalculated_stake_mismatch"):
            verify(w,self.rubric)
    def test_rehashed_changed_ev_rejected(self):
        w=self.witness()
        w["decision"]["decisions"][0]["stressed_net_per_yen"]+=1
        w["decision"]["risk_sha256"]=digest({k:v for k,v in w["decision"].items() if k!="risk_sha256"})
        with self.assertRaisesRegex(F10AuditRejected,"risk_ev_wrong"):
            verify(w,self.rubric)
    def test_fake_live_claim_rejected(self):
        w=self.witness();w["decision"]["live_source_authenticated"]=True
        with self.assertRaises(F10AuditRejected):verify(w,self.rubric)
    def test_wrong_ci_rejected(self):
        w=self.witness();w["ci_run_id"]="wrong"
        with self.assertRaises(F10AuditRejected):verify(w,self.rubric)
    def test_changed_rubric_rejected(self):
        with self.assertRaises(F10AuditRejected):verify(self.witness(),self.rubric+b" ")

if __name__=="__main__":unittest.main()
