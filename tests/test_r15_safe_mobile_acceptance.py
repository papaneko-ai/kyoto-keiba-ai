"""R15 fixed mobile preview, tap controls and fail-closed destructive tests."""
import copy,unittest
from pathlib import Path
from diagnostics.p8_r15_safe_mobile_viewmodel import build_mobile_state,MobileStateRejected
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"diagnostics"/"kyoto_new_mobile_paper_ui.py"

class R15MobileAcceptance(unittest.TestCase):
    def setUp(self):self.kw={"meeting_date":"2026-11-14","market":"馬連","budget_yen":10000}
    def state(self,**kw):return build_mobile_state(**{**self.kw,**kw})
    def reject(self,**kw):
        with self.assertRaises(MobileStateRejected):self.state(**kw)
    def test_explicit_meeting_date(self):self.assertEqual(self.state()["meeting_date"],"2026-11-14")
    def test_change_date_changes_receipt(self):self.assertNotEqual(self.state()["receipt_sha256"],self.state(meeting_date="2026-11-15")["receipt_sha256"])
    def test_change_market_changes_receipt(self):self.assertNotEqual(self.state()["receipt_sha256"],self.state(market="枠連")["receipt_sha256"])
    def test_budget_upper_bound_and_zero(self):
        for n in (0,100,1000000):self.assertEqual(self.state(budget_yen=n)["daily_budget_ceiling_yen"],n)
    def test_budget_fraction_rejected(self):self.reject(budget_yen=150)
    def test_negative_budget_rejected(self):self.reject(budget_yen=-100)
    def test_noninteger_budget_rejected(self):self.reject(budget_yen=100.0)
    def test_invalid_market_rejected(self):self.reject(market="単勝")
    def test_invalid_date_rejected(self):self.reject(meeting_date="2026-02-30")
    def test_race_count_cap(self):self.reject(requested_races=5)
    def test_ticket_count_cap(self):self.reject(requested_tickets=4)
    def test_zero_races_legal_skip(self):self.assertEqual(self.state(requested_races=0)["requested_races"],0)
    def test_no_fake_rankings(self):self.assertEqual(self.state()["rankings"],[])
    def test_no_fabricated_predictions_or_tickets(self):
        x=self.state();self.assertEqual(x["recommendations"],[]);self.assertEqual(x["frozen_tickets"],[])
    def test_no_fake_cumulative_profit(self):self.assertIsNone(self.state()["cumulative_profit_yen"])
    def test_no_fake_evolution_history(self):self.assertEqual(self.state()["evolution_history"],[])
    def test_no_unverified_source_promotion(self):self.reject(source_authenticated=True)
    def test_no_unauthorized_freeze(self):self.reject(quotes_frozen=True)
    def test_no_unconnected_paper_write(self):self.reject(paper_ledger_connected=True)
    def test_no_fake_evolution_certification(self):self.reject(evolution_certified=True)
    def test_no_spend_or_network(self):
        x=self.state();self.assertFalse(x["betting_enabled"]);self.assertFalse(x["simulation_write_enabled"]);self.assertEqual(x["network_requests"],0)
    def test_deterministic(self):self.assertEqual(self.state(),self.state())
    def test_streamlit_existing_layout_is_integrated(self):
        s=APP.read_text(encoding="utf-8")
        for section in ("開催日（表示用","仮想資金の設定","推奨レース・買い目","仮想投資の成績","AIの自己進化","運用モード","build_mobile_state"):
            self.assertIn(section,s)
        self.assertNotIn("from app import",s)
    def test_streamlit_app_wide_controls(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_file(str(APP),default_timeout=35).run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertEqual(at.radio[0].value,"馬連")
        self.assertTrue(any(b.label=="仮想馬券を登録" and b.disabled for b in at.button))
        at.radio[0].set_value("枠連")
        at.number_input[0].set_value(15000)
        at.run()
        self.assertFalse(at.exception,[e.message for e in at.exception])
        self.assertEqual(at.radio[0].value,"枠連")
        self.assertEqual(at.number_input[0].value,15000)
if __name__=="__main__":unittest.main()
