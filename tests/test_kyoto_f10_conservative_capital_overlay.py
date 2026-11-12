"""F10 offline conservative allocation acceptance; no JRA network or real bets."""
from __future__ import annotations
import copy
import unittest
from diagnostics.kyoto_f12_ticket_budget_planner import plan_f12
from diagnostics.kyoto_f10_conservative_capital_overlay import overlay_lab_risk,RiskRejected

def fixture(*,market="QUINELLA",budget=10000,target=3500,mode="AUTO"):
    if market=="QUINELLA":
        pairs=[[1,2],[1,3]]
    else:
        pairs=[[1,1],[1,2]]
    candidates=[{"race":i,"priority":i,"eligible":True,"ticket_type":market,
        "tickets":[{"pair":pair,"weight":weight}
                 for pair,weight in zip(pairs,[60,40])]}
                 for i in (1,2,3)]
    selected=[1,2,3]
    manual={i:100 for i in selected} if mode=="MANUAL" else None
    plan=plan_f12(day_budget_yen=budget,exposure_target_yen=target,
                  market=market,mode=mode,candidates=candidates,
                  selected_races=selected,manual_race_amounts=manual)
    handoff={
        "f11_source_sha256":"f"*64,"f12_plan":plan,
        "scope":"LAB_RANKING_TO_BUDGET_ONLY_NO_LIVE_FREEZE",
        "actual_purchase_authorized":False,"virtual_trade_frozen":False}
    quotes=[{
        "race":row["race"],"pair":t["pair"],"market":market,
        "odds":8.0,"probability":0.35,
        "observed_utc":"2026-11-14T03:00:00Z",
        "source_sha256":("a" if row["race"]==1 else "b")*64,
        "source_scope":"UNAUTHENTICATED_OFFLINE_LAB_MARKET"}
        for row in plan["selected"] for t in row["tickets"]]
    return handoff,quotes

def run(**kw):
    h,q=fixture()
    return overlay_lab_risk(f11_handoff=h,lab_quotes=q,
            decision_utc="2026-11-14T03:05:00Z",**kw)

class F10ConservativeCapitalAcceptance(unittest.TestCase):
    def test_positive_without_forced_budget(self):
        r=run()
        self.assertGreater(r["risk_accepted_spent_yen"],0)
        self.assertLessEqual(r["risk_accepted_spent_yen"],r["f12_planned_spent_yen"])
        self.assertEqual(r["risk_accepted_spent_yen"]+r["unspent_yen"],10000)
        self.assertLessEqual(r["risk_accepted_spent_yen"],3500)
    def test_deterministic_digest(self):
        self.assertEqual(run(),run())
    def test_quote_age_rejected_by_skip(self):
        h,q=fixture()
        for x in q:x["observed_utc"]="2026-11-14T02:00:00Z"
        r=overlay_lab_risk(f11_handoff=h,lab_quotes=q,decision_utc="2026-11-14T03:05:00Z")
        self.assertTrue(r["all_skip"])
        self.assertTrue(all(x["skip_reason"]=="STALE_QUOTE" for x in r["decisions"]))
    def test_future_quote_skipped(self):
        h,q=fixture()
        for x in q:x["observed_utc"]="2026-11-14T03:10:00Z"
        r=overlay_lab_risk(f11_handoff=h,lab_quotes=q,decision_utc="2026-11-14T03:05:00Z")
        self.assertTrue(r["all_skip"])
        self.assertTrue(all(x["skip_reason"]=="FUTURE_QUOTE" for x in r["decisions"]))
    def test_probability_error_monotone(self):
        a=run(probability_error_bound=0)
        b=run(probability_error_bound=.2)
        self.assertLessEqual(b["risk_accepted_spent_yen"],a["risk_accepted_spent_yen"])
        self.assertTrue(b["all_skip"] or b["risk_accepted_spent_yen"]<a["risk_accepted_spent_yen"])
    def test_odds_drift_monotone(self):
        a=run(odds_drift_fraction=0)
        b=run(odds_drift_fraction=.7)
        self.assertLessEqual(b["risk_accepted_spent_yen"],a["risk_accepted_spent_yen"])
    def test_takeout_is_audited_but_not_twice_discounted(self):
        a=run(takeout_rate=.1)
        b=run(takeout_rate=.3)
        self.assertEqual(a["risk_accepted_spent_yen"],b["risk_accepted_spent_yen"])
        self.assertTrue(a["takeout_embedded_in_published_odds"])
        self.assertTrue(all(x["takeout_applied_to_published_odds_again"] is False for x in a["decisions"]))
    def test_stop_all_on_nonpositive_stressed_ev(self):
        h,q=fixture()
        for x in q:x["probability"]=.07
        r=overlay_lab_risk(f11_handoff=h,lab_quotes=q,decision_utc="2026-11-14T03:05:00Z")
        self.assertTrue(r["all_skip"])
        self.assertTrue(all(x["skip_reason"]=="NO_POSITIVE_STRESSED_EDGE" for x in r["decisions"]))
    def test_max_loss_cap_is_hard_bound(self):
        for loss in (0,100,200,500):
            r=run(max_loss_yen=loss)
            self.assertLessEqual(r["risk_accepted_spent_yen"],loss)
            self.assertEqual(r["maximum_loss_upper_bound_yen"],r["risk_accepted_spent_yen"])
    def test_tighter_fraction_cannot_increase_stake(self):
        a=run()
        b=run(max_daily_fraction=.15,max_race_fraction=.10,max_pair_fraction=.05,
              max_entity_fraction=.12)
        self.assertLessEqual(b["risk_accepted_spent_yen"],a["risk_accepted_spent_yen"])
    def test_common_horse_cap_within_each_race(self):
        r=run(max_entity_fraction=.05)
        for race in (1,2,3):
            amount=sum(x["accepted_stake_yen"] for x in r["decisions"]
                       if x["race"]==race and 1 in x["pair"])
            self.assertLessEqual(amount,500)
    def test_frame_cap_supports_same_frame(self):
        h,q=fixture(market="BRACKET")
        r=overlay_lab_risk(f11_handoff=h,lab_quotes=q,
                           decision_utc="2026-11-14T03:05:00Z")
        self.assertEqual(r["ticket_type"],"BRACKET")
        self.assertTrue(any(x["pair"]==[1,1] for x in r["decisions"]))
        self.assertTrue(all(x["accepted_stake_yen"]%100==0 for x in r["decisions"]))
    def test_cancelled_or_missing_quote_refused(self):
        h,q=fixture()
        with self.assertRaisesRegex(RiskRejected,"quotes_not_complete"):
            overlay_lab_risk(f11_handoff=h,lab_quotes=q[:-1],decision_utc="2026-11-14T03:05:00Z")
    def test_duplicate_quote_refused(self):
        h,q=fixture()
        with self.assertRaisesRegex(RiskRejected,"quote_missing_foreign_or_duplicate"):
            overlay_lab_risk(f11_handoff=h,lab_quotes=q+[q[0]],decision_utc="2026-11-14T03:05:00Z")
    def test_foreign_pair_refused(self):
        h,q=fixture()
        q[0]["pair"]=[9,10]
        with self.assertRaises(RiskRejected):
            overlay_lab_risk(f11_handoff=h,lab_quotes=q,decision_utc="2026-11-14T03:05:00Z")
    def test_market_mismatch_refused(self):
        h,q=fixture()
        q[0]["market"]="BRACKET"
        with self.assertRaises(RiskRejected):
            overlay_lab_risk(f11_handoff=h,lab_quotes=q,decision_utc="2026-11-14T03:05:00Z")
    def test_fake_authenticated_quote_refused(self):
        h,q=fixture()
        q[0]["source_scope"]="LIVE_JRA_AUTHENTICATED"
        with self.assertRaises(RiskRejected):
            overlay_lab_risk(f11_handoff=h,lab_quotes=q,decision_utc="2026-11-14T03:05:00Z")
    def test_fake_authorized_handoff_rejected(self):
        h,q=fixture()
        h["virtual_trade_frozen"]=True
        with self.assertRaises(RiskRejected):
            overlay_lab_risk(f11_handoff=h,lab_quotes=q,decision_utc="2026-11-14T03:05:00Z")
    def test_tampered_f12_plan_rejected(self):
        h,q=fixture()
        h["f12_plan"]["selected"][0]["tickets"][0]["stake_yen"]+=100
        with self.assertRaises(RiskRejected):
            overlay_lab_risk(f11_handoff=h,lab_quotes=q,decision_utc="2026-11-14T03:05:00Z")
    def test_nan_probability_rejected(self):
        h,q=fixture()
        q[0]["probability"]=float("nan")
        with self.assertRaises(RiskRejected):
            overlay_lab_risk(f11_handoff=h,lab_quotes=q,decision_utc="2026-11-14T03:05:00Z")
    def test_invalid_max_loss_and_fractions_rejected(self):
        for opts in (dict(max_loss_yen=150),dict(max_loss_yen=True),
                     dict(max_daily_fraction=1.1),dict(max_pair_fraction=.5),
                     dict(odds_drift_fraction=float("nan")),dict(takeout_rate=.5),
                     dict(max_quote_age_seconds=-1)):
            with self.subTest(opts=opts),self.assertRaises(RiskRejected):run(**opts)
    def test_manual_small_stake_and_exposure(self):
        h,q=fixture(mode="MANUAL")
        r=overlay_lab_risk(f11_handoff=h,lab_quotes=q,
                           decision_utc="2026-11-14T03:05:00Z")
        self.assertLessEqual(r["risk_accepted_spent_yen"],300)
    def test_no_real_liveness_or_real_bet_claim(self):
        r=run()
        for key in ("live_source_authenticated","probabilities_calibrated",
                    "live_paper_trades_written","real_purchase_authorized"):
            self.assertIs(r[key],False)
        self.assertEqual(r["scope"],"RESEARCH_ONLY_UNCALIBRATED_PRICES_NO_BETS")

if __name__=="__main__":unittest.main()
