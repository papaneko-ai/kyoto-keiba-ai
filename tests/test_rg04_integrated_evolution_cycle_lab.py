"""RG04 research candidate => blind holdout => independent score => rollback."""
import copy
import unittest
from datetime import datetime,timedelta,timezone
from diagnostics.rg04_integrated_evolution_cycle_lab import (
    research_evolution_cycle,EvolutionIntegrationRejected,_hash)

FEATURES=("recent_form","speed_index","jockey_index","draw_advantage",
          "track_fit","pace_fit","training_index","value_signal")

def group(start,count,*,winner=1):
    output=[]
    for i in range(count):
        d=datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(days=start+i)
        at=lambda h:(d+timedelta(hours=h)).isoformat()
        h1={k:(0.9 if k=="recent_form" else 0.1) for k in FEATURES}
        h2={k:(0.1 if k=="recent_form" else 0.1) for k in FEATURES}
        raw={"race_id":f"LAB-EVO-{start+i:02d}",
             "cutoff_utc":at(1),"source_kind":"LAB_SYNTHETIC_ONLY",
             "runners":[{"horse_number":1,"features":h1},
                        {"horse_number":2,"features":h2}]}
        output.append({"frozen":{**raw,"sha256":_hash(raw)},
                       "outcome":{"race_id":raw["race_id"],"result_utc":at(2),
                                  "winner":winner,"source_kind":"LAB_SYNTHETIC_ONLY"}})
    return output

def evaluate(training=None,holdout=None,**kw):
    return research_evolution_cycle(training if training is not None else group(0,6),
             holdout if holdout is not None else group(8,10),
             plan_locked_utc="2026-01-08T00:00:00+00:00",**kw)
class Rg04ResearchCycle(unittest.TestCase):
    def test_training_selected_then_independent_improvement(self):
        r=evaluate()
        self.assertEqual(r["verdict"],"LAB_SHADOW_ELIGIBLE_NO_DEPLOY")
        self.assertEqual(r["selected_hypothesis_id"],"HYP-01")
        self.assertEqual(r["retained_champion"],"LAB-CHAMPION")
        self.assertFalse(r["production_changed"])
        self.assertFalse(r["alternate_promoted"])
        self.assertFalse(r["actual_bet_authorized"])
        self.assertEqual(r,evaluate())
    def test_deteriorating_candidate_reverts_to_champion(self):
        r=evaluate(holdout=group(8,10,winner=2))
        self.assertEqual(r["verdict"],"LAB_REJECT_AND_RETAIN_CHAMPION")
        self.assertEqual(r["rollback_result"],"ROLLBACK_TO_RETAINED_CHAMPION")
        self.assertEqual(r["retained_champion"],"LAB-CHAMPION")
        self.assertFalse(r["auto_deploy"])
    def test_future_outcome_before_race_rejected(self):
        h=group(8,10)
        h[1]["outcome"]["result_utc"]=h[1]["frozen"]["cutoff_utc"]
        with self.assertRaisesRegex(EvolutionIntegrationRejected,"outcome_before_cutoff"):
            evaluate(holdout=h)
    def test_outcome_contamination_of_precommit_refused(self):
        h=group(8,10);h[0]["frozen"]["winner"]=1
        with self.assertRaisesRegex(EvolutionIntegrationRejected,"frozen_schema_invalid"):
            evaluate(holdout=h)
    def test_changed_frozen_features_rejected(self):
        h=group(8,10);h[2]["frozen"]["runners"][0]["features"]["recent_form"]=0.2
        with self.assertRaisesRegex(EvolutionIntegrationRejected,"frozen_features_tampered"):
            evaluate(holdout=h)
    def test_holdout_used_in_training_rejected(self):
        h=group(5,10)
        with self.assertRaisesRegex(EvolutionIntegrationRejected,"model_lock"):
            evaluate(holdout=h)
    def test_train_end_after_plan_lock_rejected(self):
        t=group(5,6)
        with self.assertRaisesRegex(EvolutionIntegrationRejected,"model_lock"):
            evaluate(training=t)
    def test_training_outcome_unavailable_for_next_freeze(self):
        t=group(0,6)
        t[0]["outcome"]["result_utc"]="2026-01-04T00:00:00+00:00"
        with self.assertRaisesRegex(EvolutionIntegrationRejected,"training_result_not_available"):
            evaluate(training=t)
    def test_holdout_outcome_unavailable_for_next_freeze(self):
        h=group(8,10)
        h[0]["outcome"]["result_utc"]="2026-01-11T00:00:00+00:00"
        with self.assertRaisesRegex(EvolutionIntegrationRejected,"holdout_result_not_available"):
            evaluate(holdout=h)
    def test_unregistered_hypotheses_not_named_EVO(self):
        r=evaluate()
        self.assertTrue(r["selected_hypothesis_id"].startswith("HYP-"))
        self.assertNotIn("EVO-01",r["selected_hypothesis_id"])
        self.assertTrue(r["candidate"].endswith("HYP-01"))
    def test_duplicate_holdout_race_rejected(self):
        h=group(8,10);h[1]=copy.deepcopy(h[0])
        with self.assertRaisesRegex(EvolutionIntegrationRejected,"duplicate_or_mismatched_race"):
            evaluate(holdout=h)
    def test_nonlab_sources_rejected(self):
        h=group(8,10);h[0]["outcome"]["source_kind"]="OFFICIAL_JRA"
        with self.assertRaisesRegex(EvolutionIntegrationRejected,"nonlab_provenance"):
            evaluate(holdout=h)
    def test_multiplicity_changes_audit_to_rejection(self):
        r=evaluate(comparison_count=1000)
        self.assertEqual(r["verdict"],"LAB_REJECT_AND_RETAIN_CHAMPION")
    def test_bad_candidate_no_automatic_alternate(self):
        r=evaluate(holdout=group(8,10,winner=2))
        self.assertFalse(r["alternate_promoted"])
        self.assertEqual(r["retained_champion"],"LAB-CHAMPION")
    def test_min_holdout_sample_enforced(self):
        with self.assertRaisesRegex(EvolutionIntegrationRejected,"six_training_and_ten"):
            evaluate(holdout=group(8,9))
    def test_forged_candidate_version_collision_rejected(self):
        with self.assertRaisesRegex(EvolutionIntegrationRejected,"model_id_conflict"):
            evaluate(champion="LAB-CANDIDATE-HYP-01")
if __name__=="__main__":unittest.main()
