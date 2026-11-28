import unittest
from datetime import datetime,timezone
from urllib.request import Request
from urllib.error import HTTPError
from diagnostics.kyoto_impl39_aux_gap_recovery import RecoveryTransport,missing_records,MAX_EXTRA,bind_observed_sp
from diagnostics.jra_one_shot_market_capture import ObservedRaceSpec,capture_hybrid
from diagnostics.jra_market_integrity_gate import normal_sales_open
from datetime import date
import tempfile
STAMP="2026-11-29T04:00:00Z"
END="2026-11-29T04:30:00Z"
URL="https://www.jra.go.jp/JRADB/accessO.html"
class Client:
    def __init__(self):self.calls=[];self.code=None
    def open(self,request,timeout):
        self.calls.append(request.full_url)
        if self.code:raise HTTPError(request.full_url,self.code,"test",{},None)
        return object()
class Pacer:
    def before_request(self):pass
class AuxGap(unittest.TestCase):
    def make(self):
        c=Client();state={"requests":15,"refused":False}
        t=RecoveryTransport(c,lambda:True,Pacer(),state,start=0,monotonic=lambda:180)
        t.clock=lambda:STAMP;t.race_cutoff=datetime.fromisoformat(END.replace("Z","+00:00"))
        return c,state,t
    def test_caps_and_refusal(self):
        c,s,t=self.make()
        for i in range(MAX_EXTRA):t.open(Request(URL))
        with self.assertRaises(ValueError):t.open(Request(URL))
        self.assertEqual(len(c.calls),MAX_EXTRA);self.assertEqual(s["requests"],35)
        c,s,t=self.make();c.code=429
        with self.assertRaises(HTTPError):t.open(Request(URL))
        with self.assertRaises(ValueError):t.profile("https://www.jra.go.jp/JRADB/accessU.html")
        self.assertTrue(s["refused"]);self.assertEqual(len(c.calls),1)
    def test_cutoff_origin_initial_refusal(self):
        c,s,t=self.make();t.clock=lambda:END
        with self.assertRaises(ValueError):t.open(Request(URL))
        t.clock=lambda:STAMP
        with self.assertRaises(ValueError):t.open(Request("https://example.org/JRADB/accessO.html"))
        s["refused"]=True
        with self.assertRaises(ValueError):t.open(Request(URL))
        self.assertEqual(c.calls,[])
    def test_reserve_for_profiles_and_pacing_cutoff(self):
        c,s,t=self.make()
        t.market_cap=12
        for i in range(12):t.open(Request(URL))
        with self.assertRaisesRegex(ValueError,"reserve_for_profiles"):t.open(Request(URL))
        u="https://www.jra.go.jp/JRADB/accessU.html"
        t.profile_cutoffs[u]=datetime.fromisoformat(END.replace("Z","+00:00"))
        t.read=lambda opener,url:opener.open(Request(url),timeout=12)
        t.profile(u)
        self.assertEqual(len(c.calls),13)
        t.pacer.before_request=lambda:setattr(t,"clock",lambda:END)
        with self.assertRaisesRegex(ValueError,"race_cutoff"):t.profile(u)
        self.assertEqual(len(c.calls),13)
    def test_sp_market_hosts_share_budget_refusal_and_keep_profiles_pc_only(self):
        c,s,t=self.make()
        for host in ("sp.jra.jp","app.jra.jp"):
            for path in ("accessD.html","accessO.html"):
                t.open(Request(f"https://{host}/JRADB/{path}"))
            with self.assertRaisesRegex(ValueError,"aux_recovery_origin"):
                t.open(Request(f"https://{host}/JRADB/accessU.html"))
        for bad in ("https://sp.jra.jp.evil.invalid/JRADB/accessO.html", "https://app.jra.jp:443/JRADB/accessO.html", "https://x@app.jra.jp/JRADB/accessO.html", "https://sp.jra.jp/JRADB/accessO.html#x"):
            with self.assertRaisesRegex(ValueError,"aux_recovery_origin"):t.open(Request(bad))
        for _ in range(MAX_EXTRA-4):t.open(Request(URL))
        with self.assertRaisesRegex(ValueError,"aux_recovery_boundary"):t.open(Request("https://sp.jra.jp/JRADB/accessO.html"))
        self.assertEqual(s["requests"],35);self.assertEqual(len(c.calls),20)
        c,s,t=self.make();c.code=429
        with self.assertRaises(HTTPError):t.open(Request("https://app.jra.jp/JRADB/accessO.html"))
        with self.assertRaisesRegex(ValueError,"aux_recovery_boundary"):t.open(Request(URL))
        self.assertTrue(s["refused"]);self.assertEqual(len(c.calls),1)
    def test_only_observed_link_binds_and_existing_hybrid_uses_same_transport(self):
        day="20261129"
        pc="https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde01082026050601"+day+"%2FAA"
        sp="https://app.jra.jp/JRADB/accessD.html?CNAME=sw01dde01082026050601"+day+"%2FAA"
        alt=sp.replace("app.jra.jp","sp.jra.jp")
        spec=ObservedRaceSpec(day,1,"2026-11-29_KYOTO_1R","\u4eac\u90fd",pc,"",normal_sales_open(date(2026,11,29)).isoformat())
        row={"race_spec":spec,"verified_start_utc":END,"active_runners":((1,1),(2,2)),"expected_named_runners":((1,1,"A"),(2,2,"B")),"primary_channel":"PC"}
        def bind(urls):return bind_observed_sp({1:row},{"sp_links":{"1":urls}},lambda:STAMP)[1]["race_spec"]
        for bad in ({},{sp:END},{sp:"2026-11-28T04:00:00Z"},{sp:STAMP,alt:STAMP},{sp.replace("50601","50602"):STAMP}):
            self.assertEqual(bind(bad).sp_racecard_url,"")
        bound=bind({sp:STAMP});self.assertEqual(bound.sp_racecard_url,sp);self.assertEqual(bound.pc_racecard_url,pc)
        self.assertEqual(row["race_spec"].sp_racecard_url,"")
        c,s,t=self.make()
        def stub(out,**kw):
            channel=kw["channel"];opener=kw["opener"]
            self.assertIs(opener,t)
            opener.open(Request(pc if channel=="PC" else sp))
            return {"channel":channel,"race_id":spec.race_id,"state":"CAPTURE_BLOCKED" if channel=="PC" else "SOURCE_FROZEN","pre_race_prices_accepted":channel=="SP","reason":"transient" if channel=="PC" else None}
        with tempfile.TemporaryDirectory() as d:
            result=capture_hybrid(d,primary_channel="PC",race_spec=bound,verified_start_utc=END,active_runners=row["active_runners"],expected_named_runners=row["expected_named_runners"],authorized_live_http=True,now_utc=STAMP,openers={"PC":t,"SP":t},shared_pacer=t.pacer,capture_fn=stub)
        self.assertEqual(result["selected_channel"],"SP");self.assertEqual(c.calls,[pc,sp]);self.assertEqual(s["requests"],17)
    def test_exact_prior_pair_skip_and_conflicts(self):
        item={"verified_start_utc":END}
        row={"roster_digest":"a","named_roster_digest":"b","start_utc":END}
        old={**row,"paired_same_slot":True,"markets":{m:{"cancelled_horses":[],"utc":STAMP} for m in ("quinella","bracket_quinella")}}
        roster={"1":{"runners":[{"number":1}]}}
        def run(prior,clock=STAMP):
            return missing_records({1:item},{"1":row},{"slots":[{"races":{"1":prior}}]},roster,lambda:clock)[1]
        self.assertIsNone(run(old))
        self.assertIs(run({**old,"paired_same_slot":False}),item)
        self.assertIs(run({**old,"roster_digest":"different"}),item)
        self.assertIsNone(run(old,END))
if __name__=="__main__":unittest.main()
