"""P5 risk allocation -> P6 frozen journal real integration, strictly LAB-only."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from test_p4_source_bound_model_ev_research import SourceBoundMarketResearch
from diagnostics.p4_source_bound_model_ev_research import compare_source_market_to_frozen_model
from diagnostics.p5_source_bound_race_ranking_lab import rank_lab_research_races
from diagnostics.p5_bounded_risk_capital_lab import research_capital_control
from diagnostics.p6_source_bound_ranked_freeze_lab import freeze_ranked_research_day,FrozenRankingRejected
from diagnostics.p6_fixture_durable_ledger import read_journal

POLICY={"exposure_fraction":0.90,
        "max_race_fraction":0.50,
        "max_pair_fraction":0.30,
        "max_pair_stake_yen":20000,
        "downside_guard":0.0}
class RiskToFreezeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.fixture=SourceBoundMarketResearch(methodName="test_both_markets_original_bound_same_model_comparison")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.source=self.fixture.args()
        p4=compare_source_market_to_frozen_model(**self.source)
        self.ranking=rank_lab_research_races([p4],daily_budget_yen=100000)
        self.capital=research_capital_control(self.ranking,**POLICY)
    def freeze(self,**changes):
        kwargs={
            "day_inputs":[self.source],
            "ranking":self.ranking,
            "destination":self.root/"risk-freeze",
            "commit_utc":"2026-11-13T05:02:00Z",
            "capital_policy":POLICY,
            "capital_receipt":self.capital,
        }
        kwargs.update(changes)
        return freeze_ranked_research_day(**kwargs)
    def test_recomputed_capital_freezes_identical_stakes(self):
        receipt=self.freeze()
        self.assertEqual(receipt["allocation_source"],"P5_RECOMPUTED_BOUNDED_RISK_CAPITAL")
        self.assertEqual(receipt["capital_receipt_sha256"],self.capital["capital_sha256"])
        self.assertEqual(receipt["research_spent_yen"],self.capital["research_spent_yen"])
        self.assertEqual(receipt["unspent_yen"],100000-self.capital["research_spent_yen"])
        self.assertFalse(receipt["official_origin_authenticated"])
        self.assertFalse(receipt["real_paper_trade_authorized"])
        frozen_positions=[]
        for item in receipt["journals"]:
            ledger=read_journal(self.root/"risk-freeze"/item["file"],
                                expected_head=item["journal_head_sha256"])
            self.assertEqual(ledger["result"]["status"],"UNSETTLED")
            frozen_positions.extend(ledger["entries"][0]["payload"]["record"]["frozen"]["tickets"])
        self.assertEqual(sum(p["stake_yen"] for p in frozen_positions),self.capital["research_spent_yen"])
        self.assertEqual(len(frozen_positions),sum(t["heuristic_stake_yen"]>0 for row in self.capital["selected"] for t in row["tickets"]))
    def test_replay_deterministic_across_new_directories(self):
        a=self.freeze()
        b=self.freeze(destination=self.root/"second")
        self.assertEqual(a,b)
        for j in a["journals"]:
            self.assertEqual((self.root/"risk-freeze"/j["file"]).read_bytes(),
                             (self.root/"second"/j["file"]).read_bytes())
    def test_modification_of_capital_stakes_detected_before_write(self):
        forged=copy.deepcopy(self.capital)
        if forged["selected"]:
            forged["selected"][0]["tickets"][0]["heuristic_stake_yen"]+=100
        else:
            forged["research_spent_yen"]+=100
        with self.assertRaisesRegex(FrozenRankingRejected,"capital_recomputed_receipt_mismatch"):
            self.freeze(capital_receipt=forged)
        self.assertFalse((self.root/"risk-freeze").exists())
    def test_self_rehashed_fake_capital_not_accepted(self):
        forged=copy.deepcopy(self.capital)
        forged["research_spent_yen"]+=100
        from diagnostics.p5_bounded_risk_capital_lab import _digest
        forged["capital_sha256"]=_digest({k:v for k,v in forged.items() if k!="capital_sha256"})
        with self.assertRaises(FrozenRankingRejected):
            self.freeze(capital_receipt=forged)
    def test_wrong_policy_detected(self):
        policy={**POLICY,"downside_guard":0.9}
        with self.assertRaisesRegex(FrozenRankingRejected,"capital_recomputed_receipt_mismatch"):
            self.freeze(capital_policy=policy)
    def test_policy_or_receipt_missing_fails_closed(self):
        with self.assertRaises(FrozenRankingRejected):
            self.freeze(capital_policy=None)
        with self.assertRaises(FrozenRankingRejected):
            self.freeze(capital_receipt=None)
    def test_zero_budget_no_journals_and_no_forced_stakes(self):
        zero=rank_lab_research_races(
            [compare_source_market_to_frozen_model(**self.source)],
            daily_budget_yen=0)
        allocation=research_capital_control(zero,**POLICY)
        out=self.freeze(ranking=zero,capital_receipt=allocation)
        self.assertEqual(out["journals"],[])
        self.assertEqual(out["research_spent_yen"],0)
        self.assertEqual(out["unspent_yen"],0)
    def test_post_cutoff_freeze_rejected_without_output(self):
        with self.assertRaisesRegex(FrozenRankingRejected,"pre_cutoff_commit_required"):
            self.freeze(commit_utc="2026-11-14T04:51:00Z")
        self.assertFalse((self.root/"risk-freeze").exists())
    def test_no_overwrite_existing_verified_journals(self):
        first=self.freeze()
        before=(self.root/"risk-freeze"/"manifest.json").read_bytes()
        with self.assertRaises(FrozenRankingRejected):
            self.freeze()
        self.assertEqual((self.root/"risk-freeze"/"manifest.json").read_bytes(),before)
        self.assertEqual(json.loads(before),first)

if __name__=="__main__":
    unittest.main()
