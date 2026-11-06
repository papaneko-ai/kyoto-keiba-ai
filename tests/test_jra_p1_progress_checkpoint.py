import unittest
from diagnostics.jra_p1_progress_checkpoint import checkpoint
class CheckpointTests(unittest.TestCase):
 def test_exact_remaining_count(self):
  d=checkpoint()
  self.assertEqual((d["total_profiles_structured"],d["remaining_unqueried"]),(18,130))
  self.assertEqual(len(d["pending_batch_ids"]),22)
 def test_next_batch_is_not_first(self):
  d=checkpoint()
  self.assertEqual(d["next_batch_id"],"batch_02")
  self.assertTrue(all(x["horse_number"]!=1 for x in d["next_batch_items"]))
 def test_does_not_claim_training_or_durable_original(self):
  d=checkpoint()
  self.assertFalse(d["training_ready"])
  self.assertFalse(d["next_batch_automatically_authorized"])
  self.assertFalse(d["original_html_long_term_retention_verified"])
 def test_deterministic_checkpoint(self):self.assertEqual(checkpoint(),checkpoint())
if __name__=="__main__":unittest.main()
