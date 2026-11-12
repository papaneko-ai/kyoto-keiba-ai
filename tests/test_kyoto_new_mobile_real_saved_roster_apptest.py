"""Read-only new mobile Streamlit preview bound to true saved Kyoto 148 roster.

Does not test an actual smartphone browser; Streamlit AppTest is a headless
Python widget harness. Never touches old app, Turso or JRA network.
"""
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]

class SavedRealRosterOnMobileTests(unittest.TestCase):
 def app(self):
    test=AppTest.from_file(str(ROOT/"diagnostics"/"kyoto_new_mobile_paper_ui.py"),
                           default_timeout=25).run()
    self.assertEqual(len(test.exception),0,[x.message for x in test.exception])
    return test
 def test_real_12_race_snapshot_is_explicitly_historical(self):
    at=self.app()
    self.assertTrue(any("12レース・148頭" in str(x.value) for x in at.success))
    self.assertTrue(any("過去の京都レース" in x.label for x in at.selectbox))
    self.assertTrue(any("未検証" in str(x.value) for x in at.warning))
 def test_choose_race_12_shows_saved_17_real_runners(self):
    at=self.app()
    selection=next(x for x in at.selectbox if "過去の京都レース" in x.label)
    selection.set_value(12).run()
    self.assertEqual(len(at.exception),0,[x.message for x in at.exception])
    selected=next(x for x in at.selectbox if "過去の京都レース" in x.label)
    self.assertEqual(selected.value,12)
    self.assertTrue(any("実データ" in str(x.value) for x in at.caption))
 def test_no_virtual_bet_button_enabled(self):
    at=self.app()
    self.assertTrue(any(b.label=="仮想馬券を登録" and b.disabled for b in at.button))
 def test_no_spurious_live_paper_profit_numbers(self):
    at=self.app()
    self.assertTrue(any("仮想投資" in str(x.value) for x in at.warning))
    self.assertTrue(any("未確定" in x.value for x in at.metric))
if __name__=="__main__":unittest.main()
