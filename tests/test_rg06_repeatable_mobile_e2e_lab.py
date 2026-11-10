"""RG06B entire deterministic LAB replay and preexisting P8 mobile UI controls."""
import copy
import json
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from diagnostics.rg06_repeatable_mobile_e2e_lab import (
    repeatable_research_e2e,research_replay_once,ReproducibilityRejected
)
ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/"docs/diagnostics/jra_p1_batch14_96_profiles_20261106/status.json"
APP=ROOT/"diagnostics/p8_mobile_readonly_planner_app.py"

class EndToEndMobileResearchTests(unittest.TestCase):
    def test_entire_research_path_reproducible_quinella(self):
        raw=STATUS.read_bytes()
        x=repeatable_research_e2e(budget_yen=10000,ticket_type="QUINELLA",
                                  historical_status_bytes=raw)
        self.assertTrue(x["same_input_same_output"])
        self.assertEqual(x["independent_replays"],2)
        self.assertFalse(x["live_racing_verified"])
        self.assertFalse(x["actual_bet_authorized"])
        self.assertEqual(x["network_requests"],0)
        self.assertEqual(x,repeatable_research_e2e(budget_yen=10000,
                          ticket_type="QUINELLA",historical_status_bytes=raw))
    def test_same_status_different_budget_changes_digest(self):
        raw=STATUS.read_bytes()
        a=repeatable_research_e2e(budget_yen=1000,ticket_type="QUINELLA",
                                  historical_status_bytes=raw)
        b=repeatable_research_e2e(budget_yen=2000,ticket_type="QUINELLA",
                                  historical_status_bytes=raw)
        self.assertNotEqual(a["receipt_sha256"],b["receipt_sha256"])
    def test_market_toggle_changes_receipt_and_full_pair_coverage(self):
        raw=STATUS.read_bytes()
        a=research_replay_once(budget_yen=1000,ticket_type="QUINELLA",
                               historical_status_bytes=raw)
        b=research_replay_once(budget_yen=1000,ticket_type="BRACKET",
                               historical_status_bytes=raw)
        self.assertEqual(a["synthetic_pairs_checked"],3)
        self.assertEqual(b["synthetic_pairs_checked"],2)
        self.assertNotEqual(a["replay_sha256"],b["replay_sha256"])
    def test_tampered_historical_status_rejected(self):
        doc=json.loads(STATUS.read_bytes())
        doc["runner_count"]=999
        with self.assertRaises(ReproducibilityRejected):
            repeatable_research_e2e(budget_yen=1000,ticket_type="QUINELLA",
                  historical_status_bytes=json.dumps(doc).encode())
    def test_missing_original_bytes_rejected(self):
        with self.assertRaisesRegex(ReproducibilityRejected,"historical_status_bytes_required"):
            repeatable_research_e2e(budget_yen=1000,ticket_type="QUINELLA",
                                  historical_status_bytes=b"")
    def test_bad_budget_rejected(self):
        with self.assertRaises(ValueError):
            repeatable_research_e2e(budget_yen=125,ticket_type="QUINELLA",
                                  historical_status_bytes=STATUS.read_bytes())
    def test_wrong_ticket_type_rejected(self):
        with self.assertRaisesRegex(ReproducibilityRejected,"ticket_type_invalid"):
            repeatable_research_e2e(budget_yen=1000,ticket_type="LIVE",
                                  historical_status_bytes=STATUS.read_bytes())
    def test_mobile_widgets_and_e2e_live_together(self):
        app=AppTest.from_file(str(APP),default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value,"148頭")
        self.assertEqual(app.metric[1].value,"96頭")
        self.assertEqual(app.radio[0].value,"馬連")
        self.assertEqual(len(app.button),0)
        self.assertGreaterEqual(len(app.success),1)
        self.assertGreaterEqual(len(app.success),1)
        app.radio[0].set_value("枠連")
        app.number_input[0].set_value(15000)
        app.slider[0].set_value(4)
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.radio[0].value,"枠連")
        self.assertEqual(app.number_input[0].value,15000)
        self.assertEqual(len(app.slider),6)
        self.assertEqual(len(app.button),0)
        self.assertGreaterEqual(len(app.success),1)
    def test_no_production_network_bet_buttons(self):
        content=APP.read_text(encoding="utf8")
        for forbidden in ("requests.get","urllib.request","st.button(","submit_order","place_bet","turso"):
            self.assertNotIn(forbidden,content.lower() if forbidden=="turso" else content)
    def test_diagnostic_uses_same_e2e_entrypoint(self):
        code=APP.read_text(encoding="utf8")
        self.assertIn("repeatable_research_e2e(",code)
        self.assertIn("historical_status_bytes=STATUS.read_bytes()",code)
        self.assertIn('st.stop()',code)

if __name__=="__main__":unittest.main()
