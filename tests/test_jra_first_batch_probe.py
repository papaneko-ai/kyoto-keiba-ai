import tempfile,unittest
from datetime import datetime,timezone
from diagnostics.jra_first_batch_probe import fetch_batch
class ExplodingNetwork:
 def __call__(self,*a,**kw):raise AssertionError("no_JRA_http_should_be_made")
class FirstBatchTests(unittest.TestCase):
 def test_no_http_after_cutoff(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=fetch_batch(tmp,clock=lambda:datetime(2026,11,7,tzinfo=timezone.utc),opener=ExplodingNetwork(),sleep=lambda x:None)
   self.assertEqual(r["official_network_requests"],0)
   self.assertEqual(r["state"],"BLOCKED")
 def test_only_explicit_first_batch(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(ValueError):
    fetch_batch(tmp,batch_id="batch_02",opener=ExplodingNetwork())
if __name__=="__main__":unittest.main()
