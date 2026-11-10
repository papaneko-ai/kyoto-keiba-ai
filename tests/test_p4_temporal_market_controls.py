import copy
import json
import unittest
from diagnostics.jra_p1_offline_handoff import export_bundle
from test_p1_three_original_content_binding import StrictThreeOriginalContentTests,market_html,NOW
from diagnostics.p4_temporal_market_controls import audit_temporal_markets,TemporalMarketRejected
from diagnostics.p1_three_original_dual_intake import ThreeOriginalRejected

class MarketTemporalSourceAcceptance(unittest.TestCase):
    def setUp(self):
        self.fx=StrictThreeOriginalContentTests(methodName="test_all_three_originals_match")
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
    def current(self):
        return export_bundle(self.fx.manifest,self.fx.root,observed_utc=NOW)
    def params(self,**kw):
        args={"current_bundle":self.current(),
              "current_snapshot":copy.deepcopy(self.fx.snapshot),
              "current_observed_utc":NOW,"channel":"PC",
              "max_age_seconds":3600}
        args.update(kw)
        return args
    def audit(self,**kw):
        return audit_temporal_markets(**self.params(**kw))
    def test_originals_bound_freshness_and_explicit_policy_replay(self):
        p=b'{"scope":"LAB_DECLARED_POLICY","takeout_fraction":"0.25"}'
        r=self.audit(takeout_policy_bytes=p)
        self.assertEqual(r["takeout_assumed_fraction"],"0.25")
        self.assertFalse(r["takeout_verified_official"])
        self.assertTrue(r["current_prices_original_content_verified"])
        self.assertFalse(r["official_origin_authenticated"])
        self.assertFalse(r["actual_bet_authorized"])
        self.assertEqual(r,self.audit(takeout_policy_bytes=p))
    def test_default_conservative_freshness_refuses_stale_markets(self):
        with self.assertRaisesRegex(TemporalMarketRejected,"market_freshness_rejected"):
            self.audit(max_age_seconds=600)
    def test_market_original_content_tamper_rejected(self):
        s=copy.deepcopy(self.fx.snapshot);s["odds"][0]["decimal"]=7.7
        with self.assertRaisesRegex(ThreeOriginalRejected,"odds_original_prices_disagree"):
            self.audit(current_snapshot=s)
    def test_historical_final_cannot_masquerade_as_current(self):
        self.fx.set_original(1,market_html("馬連オッズ","umaren",["1 2 3.1"],final=True))
        with self.assertRaisesRegex(ThreeOriginalRejected,"historical_final_forbidden"):
            self.audit()
    def test_scratch_and_market_sale_rejected(self):
        s=copy.deepcopy(self.fx.snapshot);s["runners"][1]["status"]="WITHDRAWN"
        with self.assertRaises(ThreeOriginalRejected):self.audit(current_snapshot=s)
        s=copy.deepcopy(self.fx.snapshot);s["market_states"]["quinella"]["sales"]="SUSPENDED"
        with self.assertRaises(ThreeOriginalRejected):self.audit(current_snapshot=s)
    def test_takeout_is_never_inferred_from_inverse_odds(self):
        r=self.audit()
        self.assertIsNone(r["takeout_assumed_fraction"])
        self.assertFalse(r["takeout_verified_official"])
    def test_forged_official_takeout_prohibited(self):
        for data in (b'{"scope":"OFFICIAL","takeout_fraction":"0.25"}',
                     b'{"scope":"LAB_DECLARED_POLICY","takeout_fraction":"2"}',
                     b'{"scope":"LAB_DECLARED_POLICY","takeout_fraction":"NaN"}'):
            with self.assertRaisesRegex(TemporalMarketRejected,"takeout_policy_invalid"):
                self.audit(takeout_policy_bytes=data)
    def test_nonfinite_limits_fail_closed(self):
        with self.assertRaisesRegex(TemporalMarketRejected,"invalid_freshness_or_drift_limit"):
            self.audit(max_declared_odds_drift=float("nan"))
    def test_previous_market_missing_companion_is_rejected(self):
        with self.assertRaisesRegex(TemporalMarketRejected,"incomplete_prior_original_set"):
            self.audit(previous_bundle=self.current())
    def test_prior_and_current_equal_prices_reproducible(self):
        prev=export_bundle(self.fx.manifest,self.fx.root,observed_utc="2026-11-13T04:59:00Z")
        r=self.audit(previous_bundle=prev,previous_snapshot=copy.deepcopy(self.fx.snapshot),
                     previous_observed_utc="2026-11-13T04:59:00Z")
        self.assertEqual(r["observed_price_drifts"],{"odds":"0","bracket_odds":"0"})
        self.assertEqual(r["network_requests"],0)
    def test_price_change_verified_from_new_original_and_blocked_on_large_drift(self):
        old=export_bundle(self.fx.manifest,self.fx.root,observed_utc="2026-11-13T04:59:00Z")
        prior=copy.deepcopy(self.fx.snapshot)
        # A second independently captured immutable original is needed.
        self.fx.set_original(1,market_html("馬連オッズ","umaren",["1 2 9.9"]))
        self.fx.snapshot["odds"][0]["decimal"]=9.9
        self.fx.manifest["sources"][1]["captured_utc"]="2026-11-13T04:03:00Z"
        self.fx.snapshot["sources"]["odds"]["captured_utc"]="2026-11-13T04:03:00Z"
        self.fx.snapshot["market_states"]["quinella"]["observed_utc"]="2026-11-13T04:03:00Z"
        with self.assertRaisesRegex(TemporalMarketRejected,"market_drift_limit_exceeded"):
            self.audit(previous_bundle=old,previous_snapshot=prior,
                      previous_observed_utc="2026-11-13T04:59:00Z")
    def test_previous_market_from_wrong_race_rejected(self):
        s=copy.deepcopy(self.fx.snapshot);s["race"]=2
        with self.assertRaises(ThreeOriginalRejected):
            self.audit(previous_bundle=self.current(),previous_snapshot=s,
                       previous_observed_utc="2026-11-13T04:59:00Z")
    def test_nonchronological_claimed_observation_rejected(self):
        with self.assertRaisesRegex(TemporalMarketRejected,"nonchronological_quotes"):
            self.audit(previous_bundle=self.current(),previous_snapshot=copy.deepcopy(self.fx.snapshot),
                       previous_observed_utc=NOW)
    def test_price_missing_bracket_rejected(self):
        s=copy.deepcopy(self.fx.snapshot);s["bracket_odds"]=[]
        with self.assertRaises(ThreeOriginalRejected):self.audit(current_snapshot=s)

if __name__=="__main__":unittest.main()
