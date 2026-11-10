import copy
import unittest
from diagnostics.p7_guarded_research_rollback import (
 guard_research_champion,monitor_research_decisions,PromotionRejected)

def sample(offset=0,good=False):
 return [{"race_id":f"LAB-{i+offset}","cutoff_utc":f"2026-10-{i+offset+1:02d}T04:00:00Z",
          "pre_result_frozen":True,"champion_log_loss":0.5,
          "candidate_log_loss":0.3 if good else 0.8} for i in range(4)]

def choose(rows):
 return guard_research_champion(champion="champion-v1",candidate="candidate-v2",
                                alternate="alternate-v3",observations=rows)

def epoch(i,good=False):
 return {"epoch_id":f"EPOCH-{i}","champion":"champion-v1","candidate":"candidate-v2",
         "alternate":"alternate-v3","observations":sample(i*4,good)}

class GuardedEvolutionTests(unittest.TestCase):
 def test_deterioration_rolls_back_and_alternate_not_automatically_promoted(self):
  r=choose(sample())
  self.assertEqual(r["decision"],"ROLLBACK_TO_RETAINED_CHAMPION")
  self.assertEqual(r["retained_champion"],"champion-v1")
  self.assertTrue(r["alternate_requires_independent_audit"])
  self.assertFalse(r["auto_deploy"])
  self.assertFalse(r["actual_bet_authorized"])
  self.assertEqual(r,choose(sample()))
 def test_improvement_still_only_shadow(self):
  r=choose(sample(good=True))
  self.assertEqual(r["decision"],"SHADOW_CANDIDATE_ELIGIBLE_FOR_INDEPENDENT_AUDIT")
  self.assertEqual(r["retained_champion"],"champion-v1")
  self.assertFalse(r["auto_deploy"])
 def test_mixed_win_rate_fails_threshold(self):
  rows=sample(good=True)
  rows[0]["candidate_log_loss"]=0.9
  rows[1]["candidate_log_loss"]=0.9
  self.assertEqual(choose(rows)["decision"],"ROLLBACK_TO_RETAINED_CHAMPION")
 def test_future_label_changes_digest_and_verdict_not_prior_epochs(self):
  e=[epoch(0),epoch(1,True)]
  before=monitor_research_decisions(e)
  e[1]["observations"][-1]["candidate_log_loss"]=0.9
  after=monitor_research_decisions(e)
  self.assertEqual(before["epochs"][0],after["epochs"][0])
  self.assertNotEqual(before["decision_chain_head"],after["decision_chain_head"])
 def test_two_independent_windows_and_decision_chain(self):
  r=monitor_research_decisions([epoch(0),epoch(1,True)])
  self.assertEqual(r["unique_races"],8)
  self.assertEqual(len(r["epochs"]),2)
  self.assertEqual(r["epochs"][0]["decision"],"ROLLBACK_TO_RETAINED_CHAMPION")
  self.assertEqual(r["epochs"][1]["decision"],"SHADOW_CANDIDATE_ELIGIBLE_FOR_INDEPENDENT_AUDIT")
  self.assertEqual(r,monitor_research_decisions([epoch(0),epoch(1,True)]))
 def test_reject_duplicate_race_and_time_order(self):
  rows=sample();rows[1]["race_id"]=rows[0]["race_id"]
  with self.assertRaisesRegex(PromotionRejected,"duplicate_race"):
   choose(rows)
  rows=sample();rows[1]["cutoff_utc"]=rows[0]["cutoff_utc"]
  with self.assertRaisesRegex(PromotionRejected,"chronological_leakage"):
   choose(rows)
 def test_reject_unfrozen_or_invalid_score(self):
  rows=sample();rows[0]["pre_result_frozen"]=False
  with self.assertRaisesRegex(PromotionRejected,"not_frozen_before_result"):
   choose(rows)
  rows=sample();rows[0]["candidate_log_loss"]=float("nan")
  with self.assertRaisesRegex(PromotionRejected,"invalid_proper_scores"):
   choose(rows)
 def test_reject_insufficient_or_same_models(self):
  with self.assertRaisesRegex(PromotionRejected,"insufficient_paired_races"):
   choose(sample()[:2])
  with self.assertRaisesRegex(PromotionRejected,"three_distinct_model_versions_required"):
   guard_research_champion(champion="a",candidate="a",alternate="b",observations=sample())
 def test_reject_cross_epoch_duplicate(self):
  a=epoch(0);b=epoch(1)
  b["observations"][0]["race_id"]=a["observations"][0]["race_id"]
  with self.assertRaisesRegex(PromotionRejected,"monitor_duplicate_race_across_epochs"):
   monitor_research_decisions([a,b])
 def test_reject_overlap_and_reversed_epochs(self):
  with self.assertRaisesRegex(PromotionRejected,"monitor_overlapping_time_windows"):
   monitor_research_decisions([epoch(1),epoch(0)])
 def test_reject_threshold_relaxation(self):
  for kwargs in ({"min_mean_improvement":0},{"min_paired_win_fraction":0.4}):
   with self.assertRaises(PromotionRejected):
    guard_research_champion(champion="a",candidate="b",alternate="c",observations=sample(),**kwargs)
 def test_no_external_write_in_any_state(self):
  for rows in (sample(),sample(good=True)):
   r=choose(rows)
   self.assertFalse(r["external_write"])
   self.assertFalse(r["auto_deploy"])

if __name__=="__main__":unittest.main()
