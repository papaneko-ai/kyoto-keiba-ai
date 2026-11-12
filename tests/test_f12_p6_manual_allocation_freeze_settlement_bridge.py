"""F12 manual/auto selected stake -> P6 immutable freeze -> payout correction.

LAB fixtures only. Not JRA official prerace evidence or live investment.
"""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from test_p6_source_bound_ranked_freeze_lab import RankedPreResultFreezeTests
from test_p6_final_html_settlement_lab import html
from diagnostics.kyoto_f12_ticket_budget_planner import plan_f12
from diagnostics.p6_source_bound_ranked_freeze_lab import (
    freeze_ranked_research_day,FrozenRankingRejected)
from diagnostics.p6_final_html_settlement_lab import settle_ranked_lab_results,FinalResultRejected
from diagnostics.p6_fixture_durable_ledger import read_journal


class F12ToP6FreezeTests(unittest.TestCase):
    def setUp(self):
        self.fx=RankedPreResultFreezeTests(methodName="test_pre_result_frozen_and_restart_replay")
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.ranking=self.fx.ranking
        self.assertTrue(self.ranking["selected"])
        # All candidate pairs are previously source-checked P5 ranked pairs;
        # the F12 planner may only adjust their weight and exposure.
        self.candidates=[
            {"race":row["race"],"priority":row["rank"],"eligible":True,
             "ticket_type":self.ranking["ticket_type"],
             "tickets":[{"pair":t["pair"],"weight":100}
                        for t in row["tickets"]]}
            for row in self.ranking["selected"]]
        self.inputs={
            "day_budget_yen":1000,
            "exposure_target_yen":700,
            "market":self.ranking["ticket_type"],
            "mode":"MANUAL","candidates":self.candidates,
            "selected_races":[self.ranking["selected"][0]["race"]],
            "manual_race_amounts":{self.ranking["selected"][0]["race"]:600},
            "concentrate":True}
        self.plan=plan_f12(**self.inputs)
        self.path=self.fx.root/"f12-frozen"

    def freeze(self,**updates):
        args={
            "day_inputs":[self.fx.input],"ranking":self.ranking,
            "destination":self.path,
            "commit_utc":self.fx.when,
            "f12_inputs":self.inputs,"f12_receipt":self.plan}
        args.update(updates)
        return freeze_ranked_research_day(**args)

    def capture(self,prior,version=1,payout=500,target=None):
        return settle_ranked_lab_results(
            prior_directory=prior,destination=target or self.fx.root/"settled",
            expected_prior_manifest_sha256=hashlib.sha256(
                (prior/"manifest.json").read_bytes()).hexdigest(),
            result_captures={str(row["race"]):{
                "raw":html(payout,race=row["race"]),
                "captured_utc":"2026-11-14T05:10:00Z",
                "declared_scope":"LAB_RESULT_FIXTURE_ONLY",
            } for row in json.loads((prior/"manifest.json").read_text())["journals"]},
            version=version)

    def test_manual_exact_600_yen_freeze_and_replay(self):
        rec=self.freeze()
        self.assertEqual(rec["allocation_source"],"F12_RECOMPUTED_USER_SELECTION")
        self.assertEqual(rec["f12_receipt_sha256"],self.plan["plan_sha256"])
        self.assertEqual(rec["f12_mode"],"MANUAL")
        self.assertEqual(rec["research_spent_yen"],600)
        self.assertEqual(rec["unspent_yen"],400)
        self.assertFalse(rec["real_paper_trade_authorized"])
        self.assertEqual(len(rec["journals"]),1)
        j=rec["journals"][0]
        entry=read_journal(self.path/j["file"],expected_head=j["journal_head_sha256"])
        self.assertEqual([x["stake_yen"] for x in entry["entries"][0]["payload"]["record"]["frozen"]["tickets"]],[600])
        self.assertEqual(entry["result"]["status"],"UNSETTLED")

    def test_manual_precommit_to_result_and_correction(self):
        frozen=self.freeze()
        first=self.capture(self.path)
        self.assertEqual(first["allocation_source"],"F12_RECOMPUTED_USER_SELECTION")
        self.assertEqual(first["f12_receipt_sha256"],self.plan["plan_sha256"])
        self.assertEqual(first["research_spent_yen"],600)
        self.assertEqual(first["settled_fixture_payout_yen"],3000)
        self.assertEqual(first["settled_fixture_profit_yen"],2400)
        second=self.capture(self.fx.root/"settled",version=2,payout=300,
                            target=self.fx.root/"corrected")
        self.assertEqual(second["research_spent_yen"],600)
        self.assertEqual(second["f12_receipt_sha256"],first["f12_receipt_sha256"])
        self.assertEqual(second["settled_fixture_payout_yen"],1800)
        self.assertEqual(second["settled_fixture_profit_yen"],1200)
        old=read_journal(self.path/"race-01.jsonl")
        self.assertEqual(len(old["entries"]),1)
        self.assertEqual(frozen["research_spent_yen"],second["research_spent_yen"])

    def test_auto_ranking_budget_target_freezes(self):
        inputs={**self.inputs,"mode":"AUTO","manual_race_amounts":None}
        plan=plan_f12(**inputs)
        rec=self.freeze(f12_inputs=inputs,f12_receipt=plan)
        self.assertEqual(rec["f12_mode"],"AUTO")
        self.assertEqual(rec["research_spent_yen"],700)
        self.assertEqual(rec["unspent_yen"],300)

    def test_selected_all_zero_no_journals(self):
        inputs={**self.inputs,"manual_race_amounts":{1:0}}
        plan=plan_f12(**inputs)
        rec=self.freeze(f12_inputs=inputs,f12_receipt=plan)
        self.assertEqual(rec["research_spent_yen"],0)
        self.assertEqual(rec["journals"],[])
        self.assertFalse(rec["real_paper_trade_authorized"])
        result=self.capture(self.path)
        self.assertEqual(result["settled_fixture_payout_yen"],0)
        self.assertEqual(result["settled_fixture_profit_yen"],0)

    def test_empty_user_selection_remains_no_bet(self):
        inputs={**self.inputs,"selected_races":[],"manual_race_amounts":{}}
        plan=plan_f12(**inputs)
        rec=self.freeze(f12_inputs=inputs,f12_receipt=plan)
        self.assertEqual(rec["journals"],[])
        self.assertEqual(rec["research_spent_yen"],0)
        self.assertEqual(rec["user_selected_races"],[])

    def test_user_forced_unranked_pair_not_allowed(self):
        inputs=copy.deepcopy(self.inputs)
        inputs["candidates"][0]["tickets"]=[{"pair":[1,3],"weight":100}]
        with self.assertRaises(FrozenRankingRejected):
            self.freeze(f12_inputs=inputs,f12_receipt=plan_f12(**inputs))
        self.assertFalse(self.path.exists())

    def test_forged_stake_even_with_correct_hash_rejected(self):
        fake=copy.deepcopy(self.plan)
        fake["selected"][0]["tickets"][0]["stake_yen"]+=100
        fake["spent_yen"]+=100
        from diagnostics.kyoto_f12_ticket_budget_planner import _digest
        fake["plan_sha256"]=_digest({k:v for k,v in fake.items() if k!="plan_sha256"})
        with self.assertRaisesRegex(FrozenRankingRejected,"f12_recomputed_receipt_mismatch"):
            self.freeze(f12_receipt=fake)
        self.assertFalse(self.path.exists())

    def test_f12_inputs_mismatched_rejected(self):
        with self.assertRaises(FrozenRankingRejected):
            self.freeze(f12_inputs={**self.inputs,"day_budget_yen":2000})
        self.assertFalse(self.path.exists())

    def test_manual_incomplete_arguments_blocked(self):
        args=copy.deepcopy(self.inputs);args.pop("concentrate")
        with self.assertRaisesRegex(FrozenRankingRejected,"complete_inputs"):
            self.freeze(f12_inputs=args)

    def test_cannot_mix_risk_and_manual_bridges(self):
        with self.assertRaisesRegex(FrozenRankingRejected,"mutually_exclusive"):
            self.freeze(capital_receipt={"fake":"value"},capital_policy={"fake":"value"})

    def test_pre_cutoff_and_immutable_target_required(self):
        with self.assertRaisesRegex(FrozenRankingRejected,"pre_cutoff_commit_required"):
            self.freeze(commit_utc="2026-11-14T04:51:00Z")
        self.assertFalse(self.path.exists())
        self.freeze()
        before=(self.path/"manifest.json").read_bytes()
        with self.assertRaisesRegex(FrozenRankingRejected,"immutable_target_must_be_new"):
            self.freeze()
        self.assertEqual(before,(self.path/"manifest.json").read_bytes())

    def test_f12_result_provenance_tampering_safe_stop(self):
        self.freeze()
        path=self.path/"manifest.json"
        raw=json.loads(path.read_text())
        raw["f12_inputs_sha256"]="g"*64
        path.write_text(json.dumps(raw))
        with self.assertRaisesRegex(FinalResultRejected,"f12_allocation_provenance_invalid"):
            self.capture(self.path)
        self.assertFalse((self.fx.root/"settled").exists())

    def test_determinism_on_new_output_directory(self):
        first=self.freeze()
        other=self.freeze(destination=self.fx.root/"duplicate")
        self.assertEqual(first,other)
        self.assertEqual((self.path/"manifest.json").read_bytes(),
                         (self.fx.root/"duplicate"/"manifest.json").read_bytes())

if __name__=="__main__":
    unittest.main()
