"""Actual hybrid P3->P7 laboratory journal evolution cycle with destructive replay tests."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from diagnostics.p7_hybrid_model_registry import register_model
from diagnostics.p7_hybrid_shadow_evolution_cycle import (
    read_shadow,freeze_lab_pair,settle_lab_pair,scored_pairs,
    record_shadow_decision,ShadowCycleRejected)
from test_p3_hybrid_prediction_contract import model,fixture

WIN=[1,3]

def prediction(mid,snapshot,winning_probability):
    numbers=[r["horse_number"] for r in snapshot["runners"]]
    other=(1-winning_probability)/(len(numbers)*(len(numbers)-1)/2-1)
    q=[]
    for a in numbers:
        for b in numbers:
            if a<b:
                q.append({"pair":[a,b],"probability":winning_probability if [a,b]==WIN else other})
    frames={r["horse_number"]:r["frame_number"] for r in snapshot["runners"]}
    grouped={}
    for row in q:
        key=tuple(sorted(frames[x] for x in row["pair"]))
        grouped[key]=grouped.get(key,0.0)+row["probability"]
    bracket=[{"pair":list(key),"probability":value} for key,value in sorted(grouped.items())]
    return {"model_id":mid,"source_sha256":snapshot["source_sha256"],
            "feature_schema_sha256":snapshot["feature_schema_sha256"],
            "cutoff_utc":snapshot["cutoff_utc"],
            "quinella":q,"bracket":bracket}

class CycleTests(unittest.TestCase):
 def setUp(self):
    t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
    self.reg=Path(t.name)/"registry.jsonl"
    self.path=Path(t.name)/"journal.jsonl"
    register_model(self.reg,model("BASE"))
    register_model(self.reg,model("NEW","MODIFY",["BASE"]))
    self.snap,_=fixture()
 def freeze(self,i,*,candidate=.7,champion=.15,expected_head=None):
    snap=copy.deepcopy(self.snap)
    snap["race_id"]=f"LAB-RACE-{i:02d}"
    snap["source_sha256"]=hashlib.sha256(f"lab-source-{i}".encode()).hexdigest()
    snap["cutoff_utc"]=f"2026-11-13T0{i}:00:00Z"
    c=prediction("BASE",snap,champion)
    q=prediction("NEW",snap,candidate)
    head=read_shadow(self.path)["head"] if expected_head is None else expected_head
    return freeze_lab_pair(self.path,self.reg,snap,c,q,
                            freeze_utc=f"2026-11-13T0{i-1}:45:00Z",expected_head=head)
 def settle(self,i,*,winners=WIN,when=None):
    return settle_lab_pair(self.path,f"LAB-RACE-{i:02d}",winners,
        outcome_utc=when or f"2026-11-13T0{i}:35:00Z",
        expected_head=read_shadow(self.path)["head"])
 def setup_four(self,*,reverse=False):
    for i in range(1,5):
        self.freeze(i,candidate=.1 if reverse else .7,
                    champion=.6 if reverse else .15)
    for i in range(1,5):self.settle(i)
 def decide(self):
    return record_shadow_decision(self.path,champion="BASE",candidate="NEW",
                                  alternate="ALT-UNDEPLOYED",
                                  expected_head=read_shadow(self.path)["head"])
 def test_four_races_candidate_shadow_only(self):
    self.setup_four()
    result=self.decide()
    self.assertEqual(result["shadow_decision"],"SHADOW_CANDIDATE_ELIGIBLE_FOR_INDEPENDENT_AUDIT")
    self.assertFalse(result["auto_deployed"])
    self.assertFalse(result["actual_JRA_improvement_verified"])
    self.assertEqual(len(read_shadow(self.path)["decisions"]),1)
 def test_bad_candidate_rollback_to_champion(self):
    self.setup_four(reverse=True)
    result=self.decide()
    self.assertEqual(result["shadow_decision"],"ROLLBACK_TO_RETAINED_CHAMPION")
 def test_live_outcome_claim_refused(self):
    self.freeze(1)
    with self.assertRaisesRegex(ShadowCycleRejected,"external_result_not_accepted"):
        from diagnostics.p7_hybrid_shadow_evolution_cycle import _append
        _append(self.path,"SETTLE",{"race_id":"LAB-RACE-01",
             "outcome_utc":"2026-11-13T01:35:00Z",
             "winning_pair":WIN,"label_scope":"JRA_OFFICIAL"},
             expected_head=read_shadow(self.path)["head"])
 def test_label_earlier_than_freeze_rejected(self):
    self.freeze(1)
    with self.assertRaisesRegex(ShadowCycleRejected,"result_not_after_cutoff"):
        self.settle(1,when="2026-11-13T00:50:00Z")
 def test_wrong_paired_race_rejected(self):
    self.freeze(1)
    with self.assertRaisesRegex(ShadowCycleRejected,"settle_missing_or_duplicate"):
        settle_lab_pair(self.path,"LAB-OTHER",WIN,outcome_utc="2026-11-13T01:35:00Z",
                        expected_head=read_shadow(self.path)["head"])
 def test_duplicate_result_rejected(self):
    self.freeze(1);self.settle(1)
    with self.assertRaisesRegex(ShadowCycleRejected,"settle_missing_or_duplicate"):self.settle(1)
 def test_duplicate_frozen_race_rejected(self):
    self.freeze(1)
    with self.assertRaisesRegex(ShadowCycleRejected,"freeze_duplicate_race"):
        self.freeze(1)
 def test_mutated_journal_event_rejected(self):
    self.freeze(1)
    data=self.path.read_text().replace("BASE","HACK")
    self.path.write_text(data)
    with self.assertRaisesRegex(ShadowCycleRejected,"journal_chain_invalid"):
        read_shadow(self.path)
 def test_truncated_journal_rejected(self):
    self.freeze(1)
    self.path.write_bytes(self.path.read_bytes().rstrip(b"\n"))
    with self.assertRaisesRegex(ShadowCycleRejected,"journal_partial"):read_shadow(self.path)
 def test_pre_result_model_switch_rejected(self):
    self.freeze(1)
    registry2=Path(self.reg.parent)/"other.jsonl"
    register_model(registry2,model("BASE"))
    register_model(registry2,model("NEW","MODIFY",["BASE"]))
    with self.assertRaisesRegex(ShadowCycleRejected,"distinct_challenger_required"):
        snap=copy.deepcopy(self.snap)
        snap["race_id"]="LAB-RACE-02"
        champ=prediction("BASE",snap,.2)
        freeze_lab_pair(self.path,self.reg,snap,champ,champ,
                        freeze_utc="2026-11-13T03:00:00Z",
                        expected_head=read_shadow(self.path)["head"])
 def test_unsettled_cannot_be_decided(self):
    for i in range(1,5):self.freeze(i)
    for i in range(1,4):self.settle(i)
    with self.assertRaisesRegex(ShadowCycleRejected,"all_precommitted"):
        self.decide()
 def test_stale_head_does_not_write(self):
    head=read_shadow(self.path)["head"]
    self.freeze(1)
    prior=self.path.read_bytes()
    with self.assertRaisesRegex(ShadowCycleRejected,"journal_stale_head"):
        self.freeze(2,expected_head=head)
    self.assertEqual(prior,self.path.read_bytes())
 def test_replay_deterministic_and_no_model_deployment(self):
    self.setup_four()
    before=read_shadow(self.path)
    scored=scored_pairs(self.path)
    self.assertEqual(scored,scored_pairs(self.path))
    self.assertEqual(before,read_shadow(self.path))
    self.assertEqual(len(scored),4)
    self.assertTrue(all(s["champion_log_loss"]>s["candidate_log_loss"] for s in scored))
 def test_same_settled_races_cannot_be_decided_twice(self):
    self.setup_four()
    self.decide()
    with self.assertRaisesRegex(ShadowCycleRejected,"decision_reuses_or_omits_races"):
        self.decide()
 def test_recomputed_verdict_detects_even_rehashed_forgery(self):
    from diagnostics.p7_hybrid_model_registry import _hash
    self.setup_four()
    self.decide()
    lines=[json.loads(x) for x in self.path.read_text().splitlines()]
    lines[-1]["data"]["decision"]["decision"]="ROLLBACK_TO_RETAINED_CHAMPION"
    lines[-1]["event_sha256"]=_hash({k:v for k,v in lines[-1].items() if k!="event_sha256"})
    self.path.write_text("\n".join(json.dumps(x,sort_keys=True) for x in lines)+"\n")
    with self.assertRaisesRegex(ShadowCycleRejected,"decision_not_reproducible"):
        read_shadow(self.path)
 def test_zero_result_probability_clamped_finite(self):
    self.freeze(1,candidate=0.0)
    self.settle(1)
    x=scored_pairs(self.path)
    self.assertTrue(x[0]["candidate_log_loss"]>20)
 def test_unknown_model_not_accepted(self):
    snap=copy.deepcopy(self.snap)
    p=prediction("MISSING",snap,.2)
    base=prediction("BASE",snap,.2)
    with self.assertRaises(ValueError):
        freeze_lab_pair(self.path,self.reg,snap,base,p,
                        freeze_utc="2026-11-13T03:00:00Z",
                        expected_head=read_shadow(self.path)["head"])
 def test_wrong_winner_rejected(self):
    self.freeze(1)
    with self.assertRaisesRegex(ShadowCycleRejected,"winning_pair_invalid"):
        self.settle(1,winners=[1,18])
if __name__=="__main__":unittest.main()
