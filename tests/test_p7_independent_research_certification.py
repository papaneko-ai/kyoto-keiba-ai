import copy
import unittest
from diagnostics.p7_independent_research_certification import (
    independent_research_audit, IndependentResearchRejected
)
from diagnostics.p7_independent_holdout_research import AuditRejected

def study(n=10):
    ids=[f"LAB-RACE-{j:02d}" for j in range(n)]
    plan={
      "champion":"CHAMPION-v1", "candidate":"SHADOW-v2",
      "researcher_id":"generator", "auditor_id":"isolated-reviewer",
      "training_end_utc":"2026-01-01T00:00:00Z",
      "plan_locked_utc":"2026-01-02T00:00:00Z",
      "min_races":8, "min_mean_improvement":0.01,
      "min_win_fraction":0.8,"comparison_count":2,"holdout_race_ids":ids
    }
    rows=[{
      "race_id":rid,
      "frozen_utc":f"2026-02-{i+1:02d}T04:00:00Z",
      "result_utc":f"2026-02-{i+1:02d}T05:00:00Z",
      "champion_probability":0.35,
      "candidate_probability":0.75,
      "outcome":1,
    } for i,rid in enumerate(ids)]
    return plan, rows

class IndependentGateTests(unittest.TestCase):
    def test_improvement_passes_lab_only(self):
        p,r=study()
        x=independent_research_audit(p,r)
        self.assertEqual(x["research_gate"],"LAB_ONLY_PASS")
        self.assertFalse(x["evolution_certified_on_official_evidence"])
        self.assertFalse(x["real_operational_score_eligible"])
        self.assertFalse(x["production_model_changed"])
        self.assertEqual(x,independent_research_audit(p,r))
    def test_candidate_deterioration(self):
        p,r=study()
        for row in r: row["candidate_probability"]=0.1
        self.assertEqual(independent_research_audit(p,r)["research_gate"],"LAB_ONLY_REJECT")
    def test_one_lucky_race_not_enough(self):
        p,r=study()
        for row in r[:-1]:row["candidate_probability"]=0.3
        self.assertEqual(independent_research_audit(p,r)["research_gate"],"LAB_ONLY_REJECT")
    def test_many_comparisons_rejected(self):
        p,r=study();p["comparison_count"]=1000
        self.assertEqual(independent_research_audit(p,r)["research_gate"],"LAB_ONLY_REJECT")
    def test_predeclared_holdout_cannot_be_subset(self):
        p,r=study()
        with self.assertRaisesRegex(AuditRejected,"missing_or_added"):
            independent_research_audit(p,r[:-1])
    def test_holdout_cannot_be_replaced(self):
        p,r=study();r[3]["race_id"]="CHANGED-RACE"
        with self.assertRaisesRegex(AuditRejected,"holdout_selection"):
            independent_research_audit(p,r)
    def test_result_must_follow_freeze(self):
        p,r=study();r[0]["result_utc"]="2026-02-01T03:00:00Z"
        with self.assertRaisesRegex(AuditRejected,"future_leakage"):
            independent_research_audit(p,r)
    def test_earlier_test_cannot_enter_training(self):
        p,r=study();p["training_end_utc"]="2026-03-01T00:00:00Z"
        with self.assertRaisesRegex(AuditRejected,"plan_not_locked"):
            independent_research_audit(p,r)
    def test_unauthorized_extra_key_rejected(self):
        p,r=study();r[0]["price_from_future"]=100
        with self.assertRaisesRegex(AuditRejected,"observation_schema_invalid"):
            independent_research_audit(p,r)
    def test_auditor_must_be_separate(self):
        p,r=study();p["auditor_id"]=p["researcher_id"]
        with self.assertRaisesRegex(AuditRejected,"not_independent"):
            independent_research_audit(p,r)
    def test_alpha_cannot_be_relaxed(self):
        p,r=study()
        with self.assertRaisesRegex(IndependentResearchRejected,"alpha"):
            independent_research_audit(p,r,alpha=0.9)
    def test_tampering_changes_receipt(self):
        p,r=study();first=independent_research_audit(p,r)
        r[-1]["candidate_probability"]=0.74
        second=independent_research_audit(p,r)
        self.assertNotEqual(first["observations_sha256"],second["observations_sha256"])
        self.assertNotEqual(first["audit_sha256"],second["audit_sha256"])
if __name__=="__main__":
    unittest.main()
