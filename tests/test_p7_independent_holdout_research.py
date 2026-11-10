import copy
import unittest
from diagnostics.p7_independent_holdout_research import adjudicate, AuditRejected

def study():
    ids = ["LAB-01", "LAB-02", "LAB-03", "LAB-04"]
    plan = {"champion":"old-v1", "candidate":"shadow-v2",
        "researcher_id":"researcher-A", "auditor_id":"auditor-B",
        "training_end_utc":"2026-01-01T00:00:00Z",
        "plan_locked_utc":"2026-01-02T00:00:00Z",
        "min_races":4, "min_mean_improvement":0.01,
        "min_win_fraction":0.75, "comparison_count":2,
        "holdout_race_ids":ids}
    obs = [{"race_id":rid,"frozen_utc":f"2026-02-0{i}T00:00:00Z",
        "result_utc":f"2026-02-0{i}T01:00:00Z",
        "champion_probability":0.4,"candidate_probability":0.8,
        "outcome":1} for i,rid in enumerate(ids,1)]
    return plan,obs

class HoldoutTests(unittest.TestCase):
    def test_positive_research_only_not_operational(self):
        p,o=study()
        a=adjudicate(p,o)
        self.assertEqual(a["research_verdict"],"RESEARCH_HOLDOUT_PASS")
        self.assertFalse(a["operationally_certified"])
        self.assertFalse(a["auto_deploy"])
        self.assertFalse(a["prediction_ready"])
        self.assertEqual(a,adjudicate(p,o))
    def test_deterioration_refused(self):
        p,o=study()
        for r in o:r["candidate_probability"]=0.2
        self.assertEqual(adjudicate(p,o)["research_verdict"],"RESEARCH_HOLDOUT_REJECT")
    def test_missing_race_rejected(self):
        p,o=study()
        with self.assertRaisesRegex(AuditRejected,"missing_or_added"):
            adjudicate(p,o[:-1])
    def test_unregistered_race_rejected(self):
        p,o=study()
        o[-1]["race_id"]="ADDED"
        with self.assertRaisesRegex(AuditRejected,"holdout_selection"):
            adjudicate(p,o)
    def test_future_knowledge_rejected(self):
        p,o=study()
        o[0]["result_utc"]=o[0]["frozen_utc"]
        with self.assertRaisesRegex(AuditRejected,"future_leakage"):
            adjudicate(p,o)
    def test_changed_temporal_order_rejected(self):
        p,o=study()
        o[1]["frozen_utc"]=o[0]["frozen_utc"]
        with self.assertRaisesRegex(AuditRejected,"future_leakage"):
            adjudicate(p,o)
    def test_roles_and_model_independence(self):
        p,o=study();p["auditor_id"]=p["researcher_id"]
        with self.assertRaisesRegex(AuditRejected,"not_independent"):
            adjudicate(p,o)
    def test_training_and_plan_order(self):
        p,o=study();p["training_end_utc"]=p["plan_locked_utc"]
        with self.assertRaisesRegex(AuditRejected,"plan_not_locked"):
            adjudicate(p,o)
    def test_multiple_comparisons_prevent_easy_pass(self):
        p,o=study();p["min_mean_improvement"]=0.5
        p["comparison_count"]=4
        self.assertEqual(adjudicate(p,o)["research_verdict"],"RESEARCH_HOLDOUT_REJECT")
    def test_cannot_inject_result_schema(self):
        p,o=study();o[0]["official_verified"]=True
        with self.assertRaisesRegex(AuditRejected,"observation_schema_invalid"):
            adjudicate(p,o)
    def test_nan_and_boolean_probabilities_rejected(self):
        p,o=study();o[0]["candidate_probability"]=float("nan")
        with self.assertRaisesRegex(AuditRejected,"invalid_probability"):
            adjudicate(p,o)
        p,o=study();o[0]["candidate_probability"]=True
        with self.assertRaisesRegex(AuditRejected,"invalid_probability"):
            adjudicate(p,o)
    def test_forged_certification_flag_never_certifies(self):
        p,o=study()
        a=adjudicate(p,o,independently_verified=True)
        self.assertFalse(a["operationally_certified"])
        self.assertFalse(a["actual_bet_authorized"])
if __name__=="__main__": unittest.main()
