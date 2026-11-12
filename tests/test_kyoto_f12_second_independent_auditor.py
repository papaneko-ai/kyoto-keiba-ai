"""Second independent F12 auditor destructive tests, offline only."""
import copy, unittest
from pathlib import Path
from diagnostics.kyoto_f12_ticket_budget_planner import plan_f12
from diagnostics.kyoto_f12_second_independent_auditor import audit_f12,F12AuditRejected,digest
class F12AuditTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rubric=Path("docs/diagnostics/kyoto_final_completion_criteria_v1.json").read_bytes()
 def witness(self):
  source=[{"race":i,"priority":i,"eligible":True,"ticket_type":"QUINELLA",
       "tickets":[{"pair":p,"weight":w} for p,w in zip([[1,2],[2,3],[3,4]],[60,30,10])]}
       for i in range(1,5)]
  w=plan_f12(day_budget_yen=10000,exposure_target_yen=3500,market="QUINELLA",
       mode="AUTO",candidates=source,selected_races=[1,2,3])
  w.update(ci_run_id="43134360188",ci_head_sha="4b71a5621df15917381f31d0033946fdc144712c",
      rubric_sha256="92bae5c1d61d6ac00a5380dd8d5e08beb59f96c898b03c05a3c8bf8721ced632",
      F12_fixed_validation="OFFLINE_ONLY")
  return w
 def test_independent_acceptance(self):
  r=audit_f12(self.witness(),self.rubric)
  self.assertEqual(r["accepted_points"],5)
  self.assertFalse(r["real_paper_trading_certified"])
 def test_tampering_refused(self):
  w=self.witness();w["selected"][0]["tickets"][0]["stake_yen"]+=100
  with self.assertRaises(F12AuditRejected):audit_f12(w,self.rubric)
 def test_rehashed_wrong_stake_refused(self):
  w=self.witness();w["selected"][0]["tickets"][0]["stake_yen"]+=100
  body={k:v for k,v in w.items() if k not in (
   "ci_run_id","ci_head_sha","rubric_sha256","F12_fixed_validation","plan_sha256")}
  w["plan_sha256"]=digest(body)
  with self.assertRaisesRegex(F12AuditRejected,"independent_ticket_allocation_mismatch"):
   audit_f12(w,self.rubric)
 def test_fake_live_claim_refused(self):
  w=self.witness();w["real_purchase_authorized"]=True
  with self.assertRaises(F12AuditRejected):audit_f12(w,self.rubric)
 def test_wrong_rubric_refused(self):
  with self.assertRaises(F12AuditRejected):audit_f12(self.witness(),self.rubric+b" ")
 def test_wrong_ci_head_refused(self):
  w=self.witness();w["ci_head_sha"]="b"*40
  with self.assertRaises(F12AuditRejected):audit_f12(w,self.rubric)
if __name__=="__main__":unittest.main()
