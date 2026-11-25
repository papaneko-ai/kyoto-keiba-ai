"""Impl32: P05 independent track opportunity under slow racecard traffic."""
import unittest
from urllib.error import HTTPError
from diagnostics.kyoto_impl30_auxiliary_refresh import bounded_auxiliary_fetch,KYOTO_TRACK_PAGE
CARD="https://jra.jp/JRADB/accessD.html"
class Clock:
    t=0
    def __call__(self):return self.t
class Pacer:
    def __init__(self,clock,advance=0):self.clock=clock;self.advance=advance
    def before_request(self):self.clock.t+=self.advance
class Reserve(unittest.TestCase):
    def setup_fetch(self,read=None,advance=0,within=lambda:True):
        c=Clock();calls=[]
        def default(_,url):calls.append(url);return b"fixture"
        f,s=bounded_auxiliary_fetch(None,within,monotonic=c,pacer=Pacer(c,advance),read=read or default)
        return c,calls,f,s
    def test_count_reserves_track(self):
        c,calls,f,s=self.setup_fetch()
        for _ in range(14):f(CARD)
        with self.assertRaisesRegex(ValueError,"track_reserve"):f(CARD)
        f(KYOTO_TRACK_PAGE)
        self.assertEqual(s["requests"],15)
        with self.assertRaises(ValueError):f(KYOTO_TRACK_PAGE)
        self.assertEqual(calls[-1],KYOTO_TRACK_PAGE)
    def test_slow_racecards_leave_track_margin(self):
        c,calls,f,s=self.setup_fetch();c.t=164
        with self.assertRaisesRegex(ValueError,"track_reserve"):f(CARD)
        f(KYOTO_TRACK_PAGE)
        self.assertEqual(calls,[KYOTO_TRACK_PAGE])
    def test_pacing_crosses_reserve(self):
        c,calls,f,s=self.setup_fetch(advance=2);c.t=163
        with self.assertRaisesRegex(ValueError,"track_reserve"):f(CARD)
        f(KYOTO_TRACK_PAGE);self.assertEqual(calls,[KYOTO_TRACK_PAGE])
    def test_pacing_crosses_total_deadline(self):
        c,calls,f,s=self.setup_fetch(advance=2);c.t=179
        with self.assertRaises(ValueError):f(KYOTO_TRACK_PAGE)
        self.assertEqual(calls,[])
    def test_terminal_refusals_not_bypassed(self):
        for code in (401,403,429):
            def refuse(_,url):raise HTTPError(url,code,"refused",{},None)
            c,calls,f,s=self.setup_fetch(read=refuse)
            with self.assertRaises(HTTPError):f(CARD)
            with self.assertRaises(ValueError):f(KYOTO_TRACK_PAGE)
            self.assertEqual(s["requests"],1)
    def test_live_window_not_bypassed(self):
        c,calls,f,s=self.setup_fetch(within=lambda:False)
        with self.assertRaises(ValueError):f(KYOTO_TRACK_PAGE)
        self.assertEqual(calls,[])
if __name__=="__main__":unittest.main()
