import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

APP=Path(__file__).resolve().parents[1]/"diagnostics/p8_mobile_readonly_planner_app.py"
class MobileIntegrationTests(unittest.TestCase):
 def test_real_historical_readonly_and_manual_controls(self):
  app=AppTest.from_file(str(APP),default_timeout=30).run()
  self.assertFalse(app.exception)
  self.assertEqual(len(app.metric),2)
  self.assertEqual(app.metric[0].value,"148頭")
  self.assertEqual(app.metric[1].value,"96頭")
  self.assertEqual(app.radio[0].value,"馬連")
  self.assertEqual(len(app.slider),5)
  self.assertEqual(len(app.button),0)
  app.radio[0].set_value("枠連")
  app.number_input[0].set_value(15000)
  app.slider[0].set_value(4)
  app.run()
  self.assertFalse(app.exception)
  self.assertEqual(app.radio[0].value,"枠連")
  self.assertEqual(len(app.slider),6)
  self.assertEqual(len(app.button),0)
  self.assertTrue(any("15,000円" in str(x.value) for x in app.json))
 def test_no_network_or_actual_bet_imports(self):
  content=APP.read_text(encoding="utf-8")
  for forbidden in ("requests.get","urllib.request","st.button(","Turso","submit_order","place_bet"):
   self.assertNotIn(forbidden,content)

if __name__=="__main__":unittest.main()
