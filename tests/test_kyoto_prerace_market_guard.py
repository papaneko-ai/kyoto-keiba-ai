"""Offline-only negative and completeness tests for prereace market evidence."""
import copy
from hashlib import sha256
import unittest
from diagnostics.kyoto_prerace_market_guard import validate, PreraceMarketRejected

RAW=b"synthetic-html-bytes-NOT-ACTUAL-JRA"
URL="https://www.jra.go.jp/independently-verified-test-placeholder"
BASE={
    "race_id":"20261114_KYOTO_R01",
    "scheduled_start_utc":"2026-11-14T01:00:00Z",
    "observed_utc":"2026-11-14T00:58:00Z",
    "market_status":"ON_SALE",
    "ticket_type":"QUINELLA",
    "source_url":URL,
    "source_sha256":sha256(RAW).hexdigest(),
    "source_phase":"CAPTURED_BEFORE_START",
    "active_horses":[1,2,3],
    "horse_to_bracket":{"1":1,"2":2,"3":2},
    "pairs":[{"pair":[1,2],"odds":"4.5"},{"pair":[1,3],"odds":"5.0"},{"pair":[2,3],"odds":"3.2"}],
}
NOW="2026-11-14T00:59:00Z"

def check(evidence, *, raw=RAW, urls=None, now=NOW):
    return validate(evidence,raw_bytes=raw,verified_urls={URL} if urls is None else urls,now_utc=now)

class PreraceMarketTests(unittest.TestCase):
    def test_01_complete_quinella_grid(self):
        result=check(BASE)
        self.assertEqual(result["pair_count"],3)
        self.assertFalse(result["live_jra_source_verified"])
        self.assertFalse(result["approved_for_paper_freeze"])

    def test_02_same_bracket_quinella(self):
        evidence=copy.deepcopy(BASE)
        evidence["ticket_type"]="BRACKET_QUINELLA"
        evidence["pairs"]=[{"pair":[1,2],"odds":"4.5"},{"pair":[2,2],"odds":"3.0"}]
        self.assertEqual(check(evidence)["pair_count"],2)

    def test_03_negative_mutation_matrix(self):
        mutations={
            "postrace":lambda x:x.update(source_phase="RESULT_FINAL"),
            "market_stopped":lambda x:x.update(market_status="SUSPENDED"),
            "late_capture":lambda x:x.update(observed_utc="2026-11-14T01:00:00Z"),
            "future_capture":lambda x:x.update(observed_utc="2026-11-14T00:59:59Z"),
            "wrong_sha":lambda x:x.update(source_sha256="0"*64),
            "float_odds":lambda x:x["pairs"][0].update(odds=4.5),
            "nan_odds":lambda x:x["pairs"][0].update(odds="NaN"),
            "negative_odds":lambda x:x["pairs"][0].update(odds="-1"),
            "missing_pair":lambda x:x["pairs"].pop(),
            "duplicate_pair":lambda x:x["pairs"].append(copy.deepcopy(x["pairs"][0])),
            "inactive_horse":lambda x:x["pairs"][0].update(pair=[1,9]),
            "reversed_pair":lambda x:x["pairs"][0].update(pair=[2,1]),
            "missing_bracket":lambda x:x["horse_to_bracket"].pop("3"),
            "duplicate_horse":lambda x:x["active_horses"].append(2),
            "wrong_market":lambda x:x.update(ticket_type="WIN"),
            "extra_field":lambda x:x.update(production=True),
            "invalid_race":lambda x:x.update(race_id="../race"),
        }
        for name,change in mutations.items():
            with self.subTest(name=name):
                evidence=copy.deepcopy(BASE)
                change(evidence)
                with self.assertRaises(PreraceMarketRejected):
                    check(evidence)

    def test_04_missing_allowlist(self):
        with self.assertRaises(PreraceMarketRejected):
            check(BASE,urls=set())

    def test_05_stale_timestamp(self):
        with self.assertRaises(PreraceMarketRejected):
            check(BASE,now="2026-11-14T01:04:00Z")

    def test_06_after_race_start(self):
        with self.assertRaises(PreraceMarketRejected):
            check(BASE,now="2026-11-14T01:00:00Z")

    def test_07_changed_raw_original(self):
        with self.assertRaises(PreraceMarketRejected):
            check(BASE,raw=b"tampered")

    def test_08_nonexistent_same_bracket_market(self):
        evidence=copy.deepcopy(BASE)
        evidence["ticket_type"]="BRACKET_QUINELLA"
        evidence["horse_to_bracket"]={"1":1,"2":2,"3":3}
        evidence["pairs"]=[{"pair":[1,2],"odds":"4"},{"pair":[1,3],"odds":"4"},
                            {"pair":[2,3],"odds":"4"},{"pair":[2,2],"odds":"4"}]
        with self.assertRaises(PreraceMarketRejected):
            check(evidence)

if __name__=="__main__":
    unittest.main()
