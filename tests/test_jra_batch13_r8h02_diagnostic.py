import tempfile,unittest
from datetime import datetime,timezone
from diagnostics.jra_batch13_r8h02_one_shot_diagnostic import probe,CUTOFF,preflight
class NoHTTP:
    def __call__(self,*args,**kwargs):raise AssertionError("network_must_not_be_called")
class IncidentNoNetwork(unittest.TestCase):
    def test_incident_is_anchored_to_latest_checkpoint(self):
        self.assertTrue(preflight())
    def test_expired_time_refuses_network(self):
        with tempfile.TemporaryDirectory() as d:
            outcome=probe(d,opener=NoHTTP(),clock=lambda:CUTOFF)
            self.assertEqual(outcome["network_requests"],0)
            self.assertEqual(outcome["reason"],"cutoff_expired_no_http")
    def test_before_cutoff_no_http_simulated_failure(self):
        with tempfile.TemporaryDirectory() as d:
            outcome=probe(d,opener=NoHTTP(),clock=lambda:datetime(2026,11,6,tzinfo=timezone.utc))
            self.assertEqual(outcome["network_requests"],1)
            self.assertEqual(outcome["state"],"BLOCKED")
            self.assertIn("AssertionError",outcome["reason"])
if __name__=="__main__":unittest.main()
