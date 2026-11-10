"""P1-03 bounded PC/SP acquisition fallback: injected, no actual HTTP."""
import copy
import unittest
from diagnostics.p1_authorized_pc_sp_fallback import controlled_racecard_fallback,AcquisitionRejected

PC=(b'<html><body>2026\x94N11\x8c\x8e14\x93\xfa 1\x83\x8c\x81[\x83X'
    b'<table><tr><th class="horse"></th><th class="num"></th><th class="waku"></th></tr>'
    b'<tr><td class="horse"><a href="/JRADB/accessU.html?CNAME=a">A</a></td>'
    b'<td class="num">1</td><td class="waku"><img alt="\x98g1"></td></tr>'
    b'<tr><td class="horse"><a href="/JRADB/accessU.html?CNAME=b">B</a></td>'
    b'<td class="num">2</td><td class="waku"><img alt="\x98g2"></td></tr></table></body></html>')
SP=(b'<html><table><tr><td class="uban">1</td><td class="wban">1</td>'
    b'<td><a href="/JRADB/accessU.html?CNAME=a">A</a></td></tr>'
    b'<tr><td class="uban">2</td><td class="wban">2</td>'
    b'<td><a href="/JRADB/accessU.html?CNAME=b">B</a></td></tr></table></html>')
URLS={"PC":"https://jra.jp/JRADB/accessD.html?CNAME=pw01abc/A",
      "SP":"https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01abc/B"}
REF={"race_number":1,"race_date":"2026-11-14","roster_verified":True,
     "runners":[{"horse_number":1,"frame_number":1,"horse_name":"A"},
                {"horse_number":2,"frame_number":2,"horse_name":"B"}]}
STAMP="2026-11-13T05:00:00Z"

class SourceFallbackTests(unittest.TestCase):
    def args(self,fetcher=None,**changes):
        def good(channel,url):
            return {"raw":PC if channel=="PC" else SP,
                "captured_utc":STAMP,"final_url":url}
        d={"meeting_date":"2026-11-14","race":1,
           "cutoff_utc":"2026-11-14T04:50:00Z",
           "observed_utc":STAMP,"independently_frozen_roster":copy.deepcopy(REF),
           "observed_urls":dict(URLS),"transport_scope":"LAB_SIMULATED_TRANSPORT",
           "fetcher":good if fetcher is None else fetcher}
        d.update(changes);return d
    def run_it(self,fetcher=None,**kwargs):
        return controlled_racecard_fallback(**self.args(fetcher,**kwargs))
    def test_valid_pc_selected_and_sp_not_requested(self):
        called=[]
        def provider(channel,url):
            called.append(channel)
            return {"raw":PC if channel=="PC" else SP,"captured_utc":STAMP,"final_url":url}
        a=self.run_it(provider)
        self.assertEqual(called,["PC"])
        self.assertEqual(a["receipt"]["selected_channel"],"PC")
        self.assertFalse(a["receipt"]["real_prediction_authorized"])
        self.assertEqual(a["selected_original_bytes"],PC)
        self.assertEqual(a,self.run_it(provider))
    def test_failed_pc_falls_back_to_sp_exact_roster(self):
        attempts=[]
        def provider(c,u):
            attempts.append(c)
            if c=="PC":raise OSError("simulated outage")
            return {"raw":SP,"captured_utc":STAMP,"final_url":u}
        a=self.run_it(provider)
        self.assertEqual(attempts,["PC","SP"])
        self.assertTrue(a["receipt"]["fallback_used"])
        self.assertEqual(a["selected_original_bytes"],SP)
    def test_wrong_pc_roster_does_not_defeat_valid_sp(self):
        def provider(c,u):
            return {"raw":PC.replace(b'>B<',b'>Z<') if c=="PC" else SP,
                    "captured_utc":STAMP,"final_url":u}
        a=self.run_it(provider)
        self.assertEqual(a["receipt"]["selected_channel"],"SP")
    def test_both_invalid_no_source_released(self):
        def fail(c,u):return {"raw":b"garbage","captured_utc":STAMP,"final_url":u}
        a=self.run_it(fail)
        self.assertIsNone(a["selected_original_bytes"])
        self.assertEqual(a["receipt"]["result"],"BLOCKED")
    def test_after_cutoff_never_calls_provider(self):
        called=[]
        with self.assertRaisesRegex(AcquisitionRejected,"meeting_day_or_cutoff_invalid"):
            self.run_it(lambda c,u:called.append(c),
                         observed_utc="2026-11-14T04:51:00Z")
        self.assertEqual(called,[])
    def test_future_timestamp_no_release(self):
        def future(c,u):return {"raw":PC if c=="PC" else SP,
             "captured_utc":"2026-11-15T01:00:00Z","final_url":u}
        a=self.run_it(future)
        self.assertIsNone(a["selected_original_bytes"])
    def test_redirect_to_untrusted_host_blocked(self):
        def redirect(c,u):return {"raw":PC if c=="PC" else SP,
             "captured_utc":STAMP,"final_url":"https://evil.example/JRADB/accessD.html?CNAME=pw01abc/A"}
        a=self.run_it(redirect)
        self.assertIsNone(a["selected_original_bytes"])
    def test_wrong_host_in_observed_link_rejected_before_fetch(self):
        urls=dict(URLS);urls["PC"]="https://evil.example/JRADB/accessD.html?CNAME=pw01abc/A"
        with self.assertRaisesRegex(AcquisitionRejected,"untrusted_or_unobserved"):
            self.run_it(observed_urls=urls)
    def test_unverified_independent_reference_rejected(self):
        ref=copy.deepcopy(REF);ref["roster_verified"]=False
        with self.assertRaisesRegex(AcquisitionRejected,"independent_reference_required"):
            self.run_it(independently_frozen_roster=ref)
    def test_strange_transport_scope_rejected(self):
        with self.assertRaisesRegex(AcquisitionRejected,"explicit_transport_scope_required"):
            self.run_it(transport_scope="REAL_JRA_READY")
    def test_no_fetcher_rejected(self):
        with self.assertRaisesRegex(AcquisitionRejected,"injected_fetcher_required"):
            self.run_it(fetcher=42)
    def test_schema_mismatch_never_releases(self):
        def fail(c,u):return {"raw":PC if c=="PC" else SP}
        self.assertIsNone(self.run_it(fail)["selected_original_bytes"])
    def test_max_one_request_each_channel(self):
        attempts=[]
        def fail(c,u):
            attempts.append(c)
            raise OSError("blocked")
        self.run_it(fail)
        self.assertEqual(attempts,["PC","SP"])
    def test_cross_date_reference_rejected(self):
        ref=copy.deepcopy(REF);ref["race_date"]="2026-11-15"
        with self.assertRaisesRegex(AcquisitionRejected,"independent_reference_required"):
            self.run_it(independently_frozen_roster=ref)
    def test_no_predictive_credit_even_for_operator_supplied(self):
        a=self.run_it(transport_scope="OPERATOR_SUPPLIED_TRANSPORT")
        self.assertFalse(a["receipt"]["official_origin_independently_authenticated"])
        self.assertFalse(a["receipt"]["real_paper_trade_authorized"])
        self.assertFalse(a["receipt"]["official_dual_market_verified"])

if __name__=="__main__":unittest.main()
