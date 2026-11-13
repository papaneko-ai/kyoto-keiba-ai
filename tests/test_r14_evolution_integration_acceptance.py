"""R14 cross-capability acceptance; reuse independent established LAB fixtures."""
import copy,tempfile,unittest
from pathlib import Path
from tests.test_kyoto_f17_evo_eight_integrated_research import sample,RUBRIC
from test_p3_hybrid_prediction_contract import fixture,model
from diagnostics.p7_hybrid_model_registry import register_model,read_registry
from diagnostics.p7_r14_evolution_integration_acceptance import (
    audit_r14_lab,R14IntegrationRejected)
from diagnostics.kyoto_f17_evo_eight_integrated_research import dig,F17Rejected
from diagnostics.p7_guarded_research_rollback import PromotionRejected

def monitor(*,second_good=False):
    rows=[]
    for epoch in (0,1):
        obs=[]
        for i in range(4):
            day=epoch*4+i+1
            obs.append({"race_id":f"LAB-R14-{day}",
                "cutoff_utc":f"2026-10-{day:02d}T04:00:00Z",
                "pre_result_frozen":True,"champion_log_loss":.5,
                "candidate_log_loss":.3 if epoch==0 or second_good else .8})
        rows.append({"epoch_id":f"EPOCH-{epoch}","champion":"BASE","candidate":"MOD",
                     "alternate":"ADD","observations":obs})
    return rows

class R14Acceptance(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/"registry.jsonl"
        register_model(self.path,model("BASE"))
        register_model(self.path,model("MOD","MODIFY",["BASE"]))
        register_model(self.path,model("ADD","ADD",["BASE"]))
        register_model(self.path,model("ENS","ENSEMBLE",["MOD","ADD"],[5000,5000]))
        self.snapshot,base=fixture()
        self.preds=[{**copy.deepcopy(base),"model_id":mid}
                    for mid in ("BASE","MOD","ADD","ENS")]
        self.packet,self.f18=sample()
        self.epochs=monitor()
    def audit(self):
        return audit_r14_lab(self.packet,f18_witness=self.f18,
           rubric_bytes=RUBRIC,registry_path=self.path,snapshot=self.snapshot,
           predictions=self.preds,monitor_epochs=self.epochs)
    def test_eight_capabilities_four_kinds_and_two_windows(self):
        x=self.audit()
        self.assertEqual(len(x["evo_capabilities"]),8)
        self.assertEqual([m["kind"] for m in x["models"]],
            ["BASELINE","MODIFY","ADD","ENSEMBLE"])
        self.assertEqual(x["forward_monitor_epochs"],2)
    def test_same_source_and_cutoff_across_models(self):
        x=self.audit()
        self.assertEqual(x["same_race_id"],self.snapshot["race_id"])
        self.assertEqual(x["same_source_sha256"],self.snapshot["source_sha256"])
        self.assertEqual(x["same_cutoff_utc"],self.snapshot["cutoff_utc"])
    def test_bad_second_window_rolls_back(self):
        x=self.audit()
        self.assertTrue(x["rollback_demonstrated"])
        self.assertEqual(x["retained_champion"],"BASE")
    def test_non_deployed_and_no_jra_claim(self):
        x=self.audit()
        for key in ("independent_evo_real_world_certification",
            "shadow_candidates_production_adopted","unapproved_alternative_promotion",
            "production_model_changed","real_JRA_authenticated",
            "real_betting_authorized"):
            self.assertFalse(x[key])
        self.assertEqual(x["network_requests"],0)
    def test_deterministic(self):self.assertEqual(self.audit(),self.audit())
    def test_registry_is_not_mutated(self):
        before=read_registry(self.path)
        self.audit()
        self.assertEqual(before,read_registry(self.path))
    def test_missing_model_rejected(self):
        self.preds.pop()
        with self.assertRaisesRegex(R14IntegrationRejected,"four_model"):self.audit()
    def test_duplicate_model_rejected(self):
        self.preds[3]=self.preds[2]
        with self.assertRaisesRegex(R14IntegrationRejected,"distinct_registered"):self.audit()
    def test_incorrect_kind_order_rejected(self):
        self.preds[1],self.preds[2]=self.preds[2],self.preds[1]
        with self.assertRaisesRegex(R14IntegrationRejected,"baseline_modify"):self.audit()
    def test_wrong_source_sha_rejected(self):
        self.preds[1]["source_sha256"]="0"*64
        with self.assertRaises(ValueError):self.audit()
    def test_wrong_cutoff_rejected(self):
        self.preds[2]["cutoff_utc"]="2026-11-14T00:00:00Z"
        with self.assertRaises(ValueError):self.audit()
    def test_result_in_snapshot_rejected(self):
        self.snapshot["winning_pair"]=[1,2]
        with self.assertRaises(ValueError):self.audit()
    def test_fake_f17_evo_evidence_rejected(self):
        self.packet["evo_inputs"]["EVO-01"]["source_cost"]=200
        with self.assertRaises(F17Rejected):self.audit()
    def test_resealed_missing_evo_rejected(self):
        self.packet["evo_inputs"].pop("EVO-08")
        self.packet["source_sha256"]=dig({k:v for k,v in self.packet.items() if k!="source_sha256"})
        with self.assertRaises(F17Rejected):self.audit()
    def test_fake_independence_rejected(self):
        self.packet["evo_inputs"]["EVO-07"]["certifier_independent"]=False
        self.packet["source_sha256"]=dig({k:v for k,v in self.packet.items() if k!="source_sha256"})
        with self.assertRaises(F17Rejected):self.audit()
    def test_no_rollback_in_forward_windows_rejected(self):
        self.epochs=monitor(second_good=True)
        with self.assertRaisesRegex(R14IntegrationRejected,"rollback_not_demonstrated"):self.audit()
    def test_duplicate_monitored_race_rejected(self):
        self.epochs[1]["observations"][0]["race_id"]=self.epochs[0]["observations"][0]["race_id"]
        with self.assertRaises(PromotionRejected):self.audit()
    def test_unfrozen_monitor_rejected(self):
        self.epochs[0]["observations"][0]["pre_result_frozen"]=False
        with self.assertRaises(PromotionRejected):self.audit()
    def test_unauthorized_champion_swap_rejected(self):
        for epoch in self.epochs:epoch["champion"]="OTHERS"
        with self.assertRaisesRegex(R14IntegrationRejected,"champion_unapproved_promotion"):self.audit()
    def test_f17_original_witness_tampered_rejected(self):
        self.f18["ci_run_id"]="FORGED"
        with self.assertRaises(F17Rejected):self.audit()
if __name__=="__main__":unittest.main()
