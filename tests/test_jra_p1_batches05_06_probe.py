import tempfile,unittest
from datetime import datetime,timezone
from diagnostics.jra_p1_batches05_06_probe import fetch_batch
class NoNetwork:
 def __call__(self,*args,**kwargs):raise AssertionError("HTTP MUST NOT RUN")
class Checks(unittest.TestCase):
 def test_batch05_cutoff(self):
  with tempfile.TemporaryDirectory() as p:
   r=fetch_batch(p,batch_id="batch_05",opener=NoNetwork(),clock=lambda:datetime(2026,11,7,tzinfo=timezone.utc),sleep=lambda x:None)
   self.assertEqual(r["official_network_requests"],0)
   self.assertEqual(r["state"],"BLOCKED")
 def test_batch06_requires_previous_proof(self):
  with tempfile.TemporaryDirectory() as p:
   try:
    result=fetch_batch(p,batch_id="batch_06",opener=NoNetwork(),clock=lambda:datetime(2026,11,7,tzinfo=timezone.utc),sleep=lambda x:None)
    self.assertEqual(result["official_network_requests"],0)
   except ValueError as e:
    self.assertIn(str(e),("batch05_receipt_missing","batch05_not_source_verified","batch05_independent_replay_missing"))
 def test_batch07_rejected(self):
  with tempfile.TemporaryDirectory() as p:
   with self.assertRaises(ValueError):fetch_batch(p,batch_id="batch_07",opener=NoNetwork())
if __name__=="__main__":unittest.main()
