import tempfile,unittest
from datetime import datetime,timezone
from diagnostics.jra_next_three_batches_probe import fetch_batch
class ExplodingNetwork:
 def __call__(self,*args,**kwargs):raise AssertionError("unexpected_http")
class NextBatches(unittest.TestCase):
 def test_batch02_no_http_after_hard_cutoff(self):
  with tempfile.TemporaryDirectory() as d:
   r=fetch_batch(d,batch_id="batch_02",opener=ExplodingNetwork(),sleep=lambda n:None,
       clock=lambda:datetime(2026,11,7,tzinfo=timezone.utc))
   self.assertEqual(r["official_network_requests"],0)
   self.assertEqual(r["reason"],"pre_race_asof_cutoff_expired")
 def test_out_of_scope_batch_refused(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):fetch_batch(d,batch_id="batch_05",opener=ExplodingNetwork())
 def test_batch03_requires_prior_receipt(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):fetch_batch(d,batch_id="batch_03",opener=ExplodingNetwork())
if __name__=="__main__":unittest.main()
