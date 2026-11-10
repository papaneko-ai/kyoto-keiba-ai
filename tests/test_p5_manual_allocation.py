import unittest
from pathlib import Path
from diagnostics.p5_manual_allocation import allocate

class AllocationTests(unittest.TestCase):
 def test_budget_ceiling_and_determinism(self):
  self.assertEqual(allocate(10000,[50,30,20]),[5000,3000,2000])
  self.assertEqual(allocate(100,[1,1,1]),[100,0,0])
  for b in (0,100,200,10000,999900):
   for weights in ([1],[1,1],[100,0,0],[1,2,3,4],[0,0,0]):
    x=allocate(b,weights)
    self.assertEqual(x,allocate(b,weights))
    self.assertLessEqual(sum(x),b)
    self.assertTrue(all(v>=0 and v%100==0 for v in x))
 def test_no_positive_allocation_for_zero_weights(self):
  self.assertEqual(allocate(10000,[0,0]),[0,0])
 def test_reject_invalid_input(self):
  for b,w in ((-100,[1]),(150,[1]),(100,[101]),(100,[True]),(100,[]),
              (100,[1,1,1,1,1]),(1_000_100,[1])):
   with self.assertRaises(ValueError):allocate(b,w)
 def test_streamlit_app_controls_and_no_wager(self):
  from streamlit.testing.v1 import AppTest
  app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/"diagnostics/p5_manual_allocation_app.py"),default_timeout=30).run()
  self.assertFalse(app.exception)
  self.assertEqual(len(app.radio),1)
  self.assertEqual(app.radio[0].value,"馬連")
  self.assertEqual(len(app.slider),5)
  self.assertEqual(len(app.button),0)
  self.assertEqual(len(app.number_input),1)
  app.radio[0].set_value("枠連")
  app.number_input[0].set_value(20000)
  app.slider[0].set_value(2)
  app.run()
  self.assertFalse(app.exception)
  self.assertEqual(app.radio[0].value,"枠連")
  self.assertEqual(len(app.slider),4)
  self.assertEqual(len(app.button),0)

if __name__=="__main__":unittest.main()
