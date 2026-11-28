import unittest
from datetime import datetime,timezone
from urllib.request import Request
from urllib.error import HTTPError
from diagnostics.kyoto_impl39_aux_gap_recovery import RecoveryTransport,missing_records,MAX_EXTRA
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
