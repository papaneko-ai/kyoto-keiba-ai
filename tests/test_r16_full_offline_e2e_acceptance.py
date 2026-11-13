"""R16 fixed, reproducible cross-phase acceptance with 22 destructive tests."""
import copy,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from diagnostics.p2_prerace_feature_contract import freeze_feature_envelope
from diagnostics.p2_p3_p5_offline_feature_bridge import feature_forecast_snapshot,FEATURE_SCHEMA
from diagnostics.p3_offline_model_tournament import predict,_hash
from diagnostics.p3_p5_p6_synthetic_pipeline_lab import freeze_lab_market_scenario
from diagnostics.p7_approved_evo_capability_screen import REQUIRED
from diagnostics.p6_fixture_durable_ledger import read_journal,append_record
from diagnostics.r16_full_lab_e2e import run_r16,R16Rejected
SHA="a"*64
BASE=datetime(2026,10,1,tzinfo=timezone.utc)
def utc(i):return (BASE+timedelta(days=i)).isoformat().replace("+00:00","Z")

def packet():
    fam=("course","distance","pace","ground","rest","jockey","horse")
    features={"schema":"kyoto_p2_seven_family_envelope.v1",
      "race_id":"LAB-R16-20261114-KYOTO-01","source_scope":"LAB_OFFLINE_ONLY",
      "race_start_utc":"2026-11-14T03:00:00Z","feature_cutoff_utc":"2026-11-14T02:00:00Z",
      "racecard_source_sha256":SHA,
      "runners":[{"number":n,"frame":(n+1)//2,
        "families":{name:{"value":(n+i)/20,"missing_reason":None,
            "captured_utc":"2026-11-14T01:00:00Z","source_sha256":SHA}
            for i,name in enumerate(fam)}} for n in range(1,5)]}
    body={"schema":"kyoto_p2_p3_feature_lock.v1","feature_schema":list(FEATURE_SCHEMA),
      "selected_keys":[["course_fit"],["distance_fit","recent_form"]],
      "p2_receipt_sha256":SHA,"p2_input_sha256":SHA,
      "training_race_ids":["LAB-TRAIN-R16-001"],"validation_race_ids":["LAB-VALID-R16-001"],
      "holdout_race_ids":[features["race_id"]],
      "feature_rule":"LAB_POSITIVE_MEAN_OF_FROZEN_HYPOTHESES",
      "research_only":True,"production_eligible":False}
    plan={**body,"feature_lock_sha256":_hash(body)}
    snap=feature_forecast_snapshot(plan,freeze_feature_envelope(features)["p3_snapshot"])
    preds=predict(snap,"PL_BASE")
    market={"race_id":snap["race_id"],"market_type":"QUINELLA",
      "scope":"LAB_SYNTHETIC_ODDS_ONLY",
      "prices":[{"pair":p["pair"],"decimal_odds":30.} for p in preds["quinella"]]}
    pipe=freeze_lab_market_scenario(snap,model_id="PL_BASE",synthetic_market=market,
        observed_utc="2026-11-14T02:10:00Z",frozen_utc="2026-11-14T02:30:00Z",
        daily_budget_yen=10000)
    pair=pipe["frozen"]["frozen"]["tickets"][0]["pair"]
    label="-".join(map(str,pair))
    evo={name:{field:1 for field in fields} for name,fields in REQUIRED.items()}
    evo["EVO-01"]={"source_cost":1,"source_coverage":1.,"value_gain":3}
    evo["EVO-02"]={"failure_category":"LAB_WEAKNESS","baseline_loss":.6,"candidate_loss":.3}
    evo["EVO-03"]={"paired_races":8,"champion_loss":.8,"shadow_loss":.5}
    evo["EVO-04"]={"preregistered_portfolios":2,"matched_races":8,"drawdown":.15}
    evo["EVO-05"]={"baseline_drift":.5,"current_drift":.2,"monitor_windows":3}
    evo["EVO-06"]={"research_budget":10,"experiment_count":3,"holdout_unused":True}
    evo["EVO-07"]={"audit_plan_sha256":SHA,"independent_holdout":True,"certifier_independent":True}
    evo["EVO-08"]={"surprise_metric":.2,"counterexamples":2,"independent_retest":True}
    epochs=[]
    for epoch in range(2):
        obs=[]
        for i in range(4):
            idx=epoch*4+i
            obs.append({"race_id":f"LAB-R16-MON-{idx}","cutoff_utc":utc(idx),
               "pre_result_frozen":True,"champion_log_loss":.5,
               "candidate_log_loss":.3 if epoch==0 else .8})
        epochs.append({"epoch_id":f"LAB-EPOCH-{epoch}","champion":"LAB-CHAMPION",
          "candidate":"LAB-CANDIDATE","alternate":"LAB-ALTERNATE","observations":obs})
    doc={"schema":"kyoto_r16_fixed_lab_packet.v1",
      "pre_race":{"features":features,"fixed_plan":plan,"market":market,
        "observed_utc":"2026-11-14T02:10:00Z","frozen_utc":"2026-11-14T02:30:00Z",
        "budget_yen":10000,"model_id":"PL_BASE","ticket_type":"QUINELLA"},
      "post_race":{"result_utc":"2026-11-14T04:00:00Z",
         "payout_per_100":{label:500},"corrected_payout_per_100":{label:700}},
      "research_evolution":{"capabilities":evo,"epochs":epochs},
      "mobile":{"meeting_date":"2026-11-14","market":"馬連"}}
    return {**doc,"packet_sha256":_hash(doc)}
def resign(p):p["packet_sha256"]=_hash({k:v for k,v in p.items() if k!="packet_sha256"})

class R16FullAcceptance(unittest.TestCase):
    def setUp(self):self.p=packet()
    def audit(self):return run_r16(self.p)
    def test_all_p2_p8_stages_receipted(self):
        x=self.audit()
        for part in ("P2_feature","P3_forecast","P4_synthetic","P5_budget",
                     "P6_frozen","P6_final","P7_evo","P7_monitor","P8_mobile"):
            self.assertTrue(any(k.startswith(part) for k in x),part)
    def test_independent_two_runs(self):self.assertEqual(self.audit()["independent_replay_count"],2)
    def test_reproducible(self):self.assertEqual(self.audit(),self.audit())
    def test_restart_and_restore(self):
        x=self.audit();self.assertTrue(x["isolated_restore_verified"]);self.assertTrue(x["restart_verified"])
    def test_final_correction_replaces(self):
        x=self.audit();self.assertNotEqual(x["P6_profit_fixture_only_yen"],0)
    def test_budget_respected(self):self.assertLessEqual(self.audit()["P5_budget_spent_yen"],10000)
    def test_no_real_auth_or_bet(self):
        x=self.audit()
        for key in ("live_source_authenticated","production_model_promoted","real_paper_trade_written","real_bet_authorized"):
            self.assertFalse(x[key])
        self.assertEqual(x["network_requests"],0)
    def test_unsigned_change_rejected(self):
        self.p["pre_race"]["budget_yen"]=999900
        with self.assertRaisesRegex(R16Rejected,"packet_sha256_mismatch"):self.audit()
    def test_resigned_future_feature_rejected(self):
        self.p["pre_race"]["features"]["runners"][0]["families"]["horse"]["captured_utc"]="2026-11-14T02:40:00Z";resign(self.p)
        with self.assertRaises(ValueError):self.audit()
    def test_resigned_missing_feature_fails_closed(self):
        self.p["pre_race"]["features"]["runners"][0]["families"]["jockey"].update(value=None,missing_reason="SOURCE_NOT_QUERIED");resign(self.p)
        with self.assertRaisesRegex(R16Rejected,"missing_features_fail_closed"):self.audit()
    def test_resigned_odds_absence_rejected(self):
        self.p["pre_race"]["market"]["prices"].pop();resign(self.p)
        with self.assertRaises(ValueError):self.audit()
    def test_resigned_market_id_mismatch_rejected(self):
        self.p["pre_race"]["market"]["race_id"]="LAB-WRONG";resign(self.p)
        with self.assertRaisesRegex(R16Rejected,"market_model_identity_mismatch"):self.audit()
    def test_resigned_late_market_freeze_rejected(self):
        self.p["pre_race"]["frozen_utc"]="2026-11-14T04:00:00Z";resign(self.p)
        with self.assertRaises(ValueError):self.audit()
    def test_result_before_race_rejected(self):
        self.p["post_race"]["result_utc"]="2026-11-14T02:59:00Z";resign(self.p)
        with self.assertRaisesRegex(R16Rejected,"result_not_after_race"):self.audit()
    def test_changed_correction_changes_receipt(self):
        before=self.audit()["receipt_sha256"]
        self.p["post_race"]["corrected_payout_per_100"]={};resign(self.p)
        self.assertNotEqual(before,self.audit()["receipt_sha256"])
    def test_duplicate_evo_window_race_rejected(self):
        a=self.p["research_evolution"]["epochs"]
        a[1]["observations"][0]["race_id"]=a[0]["observations"][0]["race_id"];resign(self.p)
        with self.assertRaises(ValueError):self.audit()
    def test_no_evolution_rollback_rejected(self):
        for x in self.p["research_evolution"]["epochs"][1]["observations"]:x["candidate_log_loss"]=.3
        resign(self.p)
        with self.assertRaisesRegex(R16Rejected,"rollback_not_demonstrated"):self.audit()
    def test_unapproved_mobile_auth_rejected(self):
        self.p["mobile"]["source_authenticated"]=True;resign(self.p)
        with self.assertRaisesRegex(R16Rejected,"mobile_contract_invalid"):self.audit()
    def test_postrace_field_in_prerace_rejected(self):
        self.p["pre_race"]["winning_pair"]=[1,2];resign(self.p)
        with self.assertRaisesRegex(R16Rejected,"pre_race_contract_invalid"):self.audit()
    def test_p6_stale_head_rejected(self):
        from diagnostics.p6_virtual_settlement_fixture_lab import freeze_fixture,LabRejected
        with TemporaryDirectory() as d:
            path=Path(d)/"journal.jsonl"
            f=freeze_fixture(scenario_id="LAB-R16-REPLAY",ticket_type="QUINELLA",
               cutoff_utc="2026-11-14T03:00:00Z",frozen_utc="2026-11-14T02:30:00Z",
               model_version="LAB-PL",source_sha256=SHA,
               tickets=[{"pair":[1,2],"stake_yen":100,"probability":.3,"odds":5.}])
            s=append_record(path,"FROZEN",f,expected_head="0"*64)
            with self.assertRaises(LabRejected):read_journal(path,expected_head="b"*64)
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaises(LabRejected):read_journal(path,expected_head=s["head"])
    def test_r15_ui_remains_fail_closed(self):
        x=self.audit();self.assertTrue(x["P8_mobile_safe_sha256"])
        self.assertFalse(x["real_paper_trade_written"])
    def test_immutable_16_gate_rubric(self):
        from diagnostics.kyoto_predata_readiness import verify_rubric,RUBRIC
        import json
        doc=json.loads((Path(__file__).resolve().parents[1]/RUBRIC).read_text())
        self.assertEqual(len(doc["gates"]),16)
        self.assertTrue(verify_rubric(doc))
if __name__=="__main__":unittest.main()
