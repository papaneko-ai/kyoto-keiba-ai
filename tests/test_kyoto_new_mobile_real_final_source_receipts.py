"""Actual prior JRA final-only view model + Streamlit headless no-bet tests."""
import json,tempfile,unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from diagnostics.kyoto_p6_real_final_mobile_viewmodel import view,ActualFinalViewRejected,RECEIPT

ROOT=Path(__file__).resolve().parents[1]
class MobileTrueFinalResultTests(unittest.TestCase):
 def mutate(self,change):
    data=json.loads(RECEIPT.read_text(encoding="utf8"))
    change(data)
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/"modified.json"
        path.write_text(json.dumps(data,ensure_ascii=False),encoding="utf8")
        return view(path)
 def test_exact_two_actual_races_not_profits(self):
    x=view()
    self.assertEqual(len(x["rows"]),2)
    self.assertIsNone(x["real_virtual_investment_profit"])
    self.assertFalse(x["actual_prerace_market_odds_verified"])
 def test_real_oct25_payout(self):
    x=view()["rows"][0]
    self.assertEqual(x["馬連払戻（100円）"],15090)
    self.assertEqual(x["枠連払戻（100円）"],1540)
 def test_real_nov08_payout(self):
    x=view()["rows"][1]
    self.assertEqual(x["馬連払戻（100円）"],1670)
    self.assertEqual(x["枠連払戻（100円）"],1330)
 def test_source_sha_mutation_refused(self):
    with self.assertRaises(ActualFinalViewRejected):
        self.mutate(lambda d:d["races"][0].update(source_sha256="f"*64))
 def test_real_payout_mutation_refused(self):
    with self.assertRaises(ActualFinalViewRejected):
        self.mutate(lambda d:d["races"][0]["quinella"].update(yen_per_100=999))
 def test_forecast_relabel_refused(self):
    with self.assertRaises(ActualFinalViewRejected):
        self.mutate(lambda d:d.update(actual_pre_race_quinella_bracket_prices_authenticated=True))
 def test_fake_paper_profit_refused(self):
    with self.assertRaises(ActualFinalViewRejected):
        self.mutate(lambda d:d.update(actual_paper_pnl_available=True))
 def test_source_db_sha_mutation_refused(self):
    with self.assertRaises(ActualFinalViewRejected):
        self.mutate(lambda d:d.update(official_sqlite_registry_sha256="0"*64))
 def test_duplicate_original_race_refused(self):
    with self.assertRaises(ActualFinalViewRejected):
        self.mutate(lambda d:d["races"].__setitem__(1,d["races"][0]))
 def test_browser_results_tab_renders_historical_finals(self):
    a=AppTest.from_file(str(ROOT/"diagnostics"/"kyoto_new_mobile_paper_ui.py"),default_timeout=25).run()
    self.assertFalse(a.exception,[str(x) for x in a.exception])
    self.assertTrue(any("JRA公式の過去の確定結果" in str(x.label) for x in a.expander))
    self.assertTrue(any("事前の仮想馬券を登録した事実はありません" in str(x.value) for x in a.info))
    self.assertTrue(any(b.label=="仮想馬券を登録" and b.disabled for b in a.button))
 def test_browser_never_forges_virtual_roi(self):
    a=AppTest.from_file(str(ROOT/"diagnostics"/"kyoto_new_mobile_paper_ui.py"),default_timeout=25).run()
    self.assertFalse(a.exception)
    self.assertTrue(any(x.value=="未確定" for x in a.metric))
    self.assertTrue(any("発走前オッズではありません" in str(x.value) for x in a.caption))
if __name__=="__main__":unittest.main()
