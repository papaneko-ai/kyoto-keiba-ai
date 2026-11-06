import unittest,tempfile
from datetime import datetime,timezone
from diagnostics.jra_p1_batches07_08_probe import fetch_batch
class NeverHTTP:
 def __call__(self,*a,**kw):raise AssertionError("unexpected network")
class Intake(unittest.TestCase):
 def test_no_http_after_cutoff(self):
  for b in ("batch_07","batch_08"):
   with self.subTest(b=b),tempfile.TemporaryDirectory() as folder:
    try:
     r=fetch_batch(folder,batch_id=b,opener=NeverHTTP(),sleep=lambda x:None,clock=lambda:datetime(2026,11,7,tzinfo=timezone.utc))
     self.assertEqual(r["official_network_requests"],0)
    except ValueError as e:
     if b=="batch_07":raise
     self.assertIn(str(e),("batch07_receipt_or_replay_missing","batch07_not_independently_verified"))
 def test_skip_is_prohibited(self):
  with tempfile.TemporaryDirectory() as folder:
   with self.assertRaises(ValueError):fetch_batch(folder,batch_id="batch_09",opener=NeverHTTP())
if __name__=="__main__":unittest.main()
