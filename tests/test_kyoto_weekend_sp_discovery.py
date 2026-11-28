"""Zero-network independent SP discovery, byte integrity and no-guess guard."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from diagnostics.kyoto_weekend_sp_discovery import (
    SEED, discover, SPDiscoveryError, official_sp_anchors
)

DAY="20261121"
MEETING="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01meet20261121%2FAA"
RACE="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01race1220261121%2FBB"

def html(content):
    return ("<html><body>"+content+"</body></html>").encode("cp932")

class Response:
    status=200
    headers={"Content-Type":"text/html; charset=Shift_JIS"}
    def __init__(self, url, raw):
        self.url=url
        self.raw=raw
    def geturl(self):return self.url
    def read(self,n):return self.raw[:n]
    def __enter__(self):return self
    def __exit__(self,*args):return False

class Stub:
    def __init__(self, pages):
        self.pages=pages
        self.calls=[]
    def open(self,request,timeout=12):
        url=request.full_url
        self.calls.append(url)
        if url not in self.pages:
            raise AssertionError("unobserved_page_requested")
        return Response(url,self.pages[url])

class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)/"independent_sp"
        self.pacer=Mock()

    def test_sp_home_observed_meeting_to_exact_race(self):
        first=html('<a href="'+MEETING+'">京都 20261121 開催</a>')
        second=html('<a href="'+RACE+'">京都 12R</a>')
        stub=Stub({SEED:first,MEETING:second})
        r=discover(self.root,day=DAY,opener=stub,pacer=self.pacer)
        self.assertEqual(r["racecard_url"],RACE)
        self.assertEqual(stub.calls,[SEED,MEETING])
        self.assertEqual(r["network_requests_started"],2)
        self.assertEqual(self.pacer.before_request.call_count,2)
        self.assertEqual((self.root/"official_sp_discovery_1.html").read_bytes(),first)
        self.assertEqual(r["attempts"][0]["sha256"],hashlib.sha256(first).hexdigest())
        self.assertEqual(json.loads((self.root/"sp_discovery_receipt.json").read_text())["racecard_url"],RACE)
        self.assertFalse(r["prediction_ready"])

    def test_novel_form_and_action_auto_repair_at_runtime(self):
        from diagnostics.kyoto_adaptive_repair import recover_action
        day="20261129"
        endpoint="https://sp.jra.jp/JRADB/accessD.html"
        form='<form id="new" method="post" action="/JRADB/accessD.html"><input type="hidden" name="cname"></form>'
        home=html(form+'<button onclick="doAction (\'/JRADB/accessD.html\',\'sw01dli00/80\')">出馬表</button>')
        selection=html(form+'<a href="javascript:doAction (\'/JRADB/accessD.html\',\'sw01drl00082026050820261129/F8\')">京都</a>')
        urls={n:endpoint+f"?CNAME=sw01dde010820260508{n:02d}{day}/A1" for n in range(1,13)}
        meeting=html("".join(f'<a href="{u}">京都 {n}R</a>' for n,u in urls.items()))
        class Forms:
            def __init__(self):self.calls=[]
            def open(self,req,timeout=12):
                self.calls.append((req.full_url,req.get_method(),req.data))
                return Response(req.full_url,[home,selection,meeting][len(self.calls)-1])
        stub=Forms();result=discover(self.root,day=day,opener=stub,pacer=self.pacer)
        self.assertEqual(stub.calls,[(SEED,"GET",None),(endpoint,"POST",b"cname=sw01dli00%2F80"),(endpoint,"POST",b"cname=sw01drl00082026050820261129%2FF8")])
        self.assertEqual(result["attempts"][0]["adaptive_navigation_repair"],recover_action(home,day,"SP","entry")[3])
        self.assertEqual(result["attempts"][1]["adaptive_navigation_repair"],recover_action(selection,day,"SP","meeting")[3])
        self.assertTrue(all(x["candidate_count"]==1 for x in result["per_race_observed_navigation_candidates"].values()))
        self.assertFalse(result["prediction_ready"])

    def test_without_observed_anchor_never_invents_url(self):
        stub=Stub({SEED:html("<p>not published</p>")})
        r=discover(self.root,day=DAY,opener=stub,pacer=self.pacer)
        self.assertEqual(stub.calls,[SEED])
        self.assertEqual(r["racecard_url"],"")
        self.assertEqual(r["state"],"OFFICIAL_R12_LINK_NOT_OBSERVED")

    def test_adversarial_host_ignored(self):
        fake=RACE.replace("sp.jra.jp","sp.jra.jp.evil.invalid")
        raw=html('<a href="'+fake+'">京都 12R</a>')
        self.assertEqual(official_sp_anchors(raw,SEED,DAY),[])
        r=discover(self.root,day=DAY,opener=Stub({SEED:raw}),pacer=self.pacer)
        self.assertFalse(r["unique_observed_racecard"])

    def test_sunday_two_real_navigation_choices_recovers_link_without_guessing(self):
        sunday="20261122"
        a="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01meet20261122%2FA1"
        b="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01meet20261122%2FB1"
        c="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01meet20261122%2FC1"
        race="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01race1220261122%2FD1"
        home=html('<a href="'+a+'">京都 出馬表</a><a href="'+b+'">京都 開催</a>')
        pages={SEED:home,a:html("<p>未発表</p>"),b:html('<a href="'+c+'">京都 出馬表</a>'),
               c:html('<a href="'+race+'">京都 12R</a>')}
        stub=Stub(pages)
        found=discover(self.root,day=sunday,opener=stub,pacer=self.pacer)
        self.assertEqual(found["racecard_url"],race)
        self.assertEqual(stub.calls,[SEED,a,b,c])
        self.assertEqual(found["network_requests_started"],4)
        self.assertTrue((self.root/"official_sp_discovery_4.html").exists())
        # Sunday evidence sealing is verified independently in crypto tests.

    def test_weekend_transient_branch_failure_keeps_observed_alternative(self):
        from urllib.error import HTTPError, URLError
        day="20261128"
        a="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01meet20261128%2FA1"
        b="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01meet20261128%2FB1"
        race="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605061220261128%2FA1"
        home=html(f'<a href="{a}">京都 開催</a><a href="{b}">京都 出馬表</a>')
        target=html(f'<a href="{race}">京都 12R</a>')
        for error in (TimeoutError(),URLError(TimeoutError()),HTTPError(a,503,"temporary",{},None),HTTPError(a,404,"not found",{},None)):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as tmp:
                class Failing(Stub):
                    def open(self,request,timeout=12):
                        if request.full_url==a:
                            self.calls.append(a);raise error
                        return super().open(request,timeout)
                stub=Failing({SEED:home,b:target})
                r=discover(Path(tmp)/"raw",day=day,opener=stub,pacer=Mock())
                self.assertEqual(stub.calls[:3],[SEED,a,b])
                self.assertEqual(stub.calls.count(a),1)
                self.assertEqual(r["per_race_observed_navigation_candidates"]["12"]["candidate_count"],1)
                self.assertFalse(r["prediction_ready"])

    def test_weekend_refusal_never_uses_alternative_to_bypass(self):
        from urllib.error import HTTPError, URLError
        import ssl
        day="20261129"
        a="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01meet20261129%2FA1"
        b="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01meet20261129%2FB1"
        home=html(f'<a href="{a}">京都 開催</a><a href="{b}">京都 出馬表</a>')
        for error in (HTTPError(a,401,"refused",{},None),HTTPError(a,403,"refused",{},None),HTTPError(a,429,"limited",{},None),URLError(ssl.SSLError("TLS"))):
            with self.subTest(error=str(error)), tempfile.TemporaryDirectory() as tmp:
                class Failing(Stub):
                    def open(self,request,timeout=12):
                        if request.full_url==a:
                            self.calls.append(a);raise error
                        return super().open(request,timeout)
                stub=Failing({SEED:home})
                r=discover(Path(tmp)/"raw",day=day,opener=stub,pacer=Mock())
                self.assertEqual(stub.calls,[SEED,a]);self.assertFalse(r["prediction_ready"])
                self.assertTrue(r["stop_followup_http"])

    def test_unrelated_page_kyoto_text_does_not_authenticate_other_race(self):
        race="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01race1220261121%2FBB"
        page=html('<h2>京都</h2><p>東京</p><a href="'+race+'">東京 12R</a>')
        result=discover(self.root,day=DAY,opener=Stub({SEED:page}),pacer=self.pacer)
        self.assertFalse(result["unique_observed_racecard"])
        self.assertEqual(result["racecard_url"],"")

    def test_actual_nov28_homepage_post_navigation(self):
        day="20261129"
        endpoint="https://sp.jra.jp/JRADB/accessD.html"
        race=endpoint+"?CNAME=sw01dde0108202605061220261129%2FA1"
        home=html('<form method="POST" action=""><input name="cname"></form>'
                  '<a href="#" onclick="return doAction(\'/JRADB/accessD.html\',\'sw01dli00/80\')">出馬表</a>')
        class PostStub(Stub):
            def open(self,request,timeout=12):
                if request.full_url==endpoint:
                    self.assert_post(request)
                return super().open(request,timeout)
            def assert_post(self,request):
                assert request.get_method()=="POST"
                assert request.data==b"cname=sw01dli00%2F80"
        stub=PostStub({SEED:home,endpoint:html(f'<a href="{race}">京都 12R</a>'),race:html("<p>racecard</p>")})
        r=discover(self.root,day=day,opener=stub,pacer=self.pacer)
        self.assertEqual(stub.calls[:2],[SEED,endpoint])
        self.assertEqual(r["attempts"][1]["request_method"],"POST")
        self.assertEqual(r["attempts"][1]["url"],endpoint)
        self.assertEqual(r["per_race_observed_navigation_candidates"]["12"]["candidate_urls"],[race])
        self.assertFalse(r["prediction_ready"])

    def test_actual_sunday_meeting_form_yields_all_twelve(self):
        day="20261129"
        endpoint="https://sp.jra.jp/JRADB/accessD.html"
        form='<form id="commForm01" method="POST" action=""><input name="cname"></form>'
        home=html(form+'<a onclick="return doAction(\'/JRADB/accessD.html\',\'sw01dli00/80\')">出馬表</a>')
        urls={n:endpoint+f"?CNAME=sw01dde010820260508{n:02d}{day}/A1" for n in range(1,13)}
        selection=html(form+'<a onclick="return doAction(\'/JRADB/accessD.html\', \'sw01drl00082026050820261129/F8\');">京都</a>'+f'<a href="{urls[12]}">京都12R</a>')
        meeting=html("".join(f'<a href="{url}">{n}R 15:00</a>' for n,url in urls.items()))
        class Forms:
            def __init__(self):self.calls=[]
            def open(self,request,timeout=12):
                self.calls.append((request.full_url,request.get_method(),request.data))
                if len(self.calls)==1:return Response(SEED,home)
                if len(self.calls)==2:return Response(endpoint,selection)
                if len(self.calls)==3:return Response(endpoint,meeting)
                raise AssertionError("unneeded navigation")
        stub=Forms()
        r=discover(self.root,day=day,opener=stub,pacer=self.pacer)
        self.assertEqual(stub.calls,[(SEED,"GET",None),(endpoint,"POST",b"cname=sw01dli00%2F80"),(endpoint,"POST",b"cname=sw01drl00082026050820261129%2FF8")])
        self.assertEqual(r["network_requests_started"],3)
        self.assertEqual(r["racecard_url"],urls[12])
        self.assertEqual({int(n):v["candidate_urls"] for n,v in r["per_race_observed_navigation_candidates"].items()},{n:[u] for n,u in urls.items()})
        self.assertFalse(r["prediction_ready"])

    def test_untrusted_post_action_is_never_followed(self):
        day="20261129"
        home=html('<form method="POST" action=""><input name="cname"></form>'
                  '<a href="#" onclick="return doAction(\'https://evil.invalid/JRADB/accessD.html\',\'sw01dli00/80\')">出馬表</a>')
        stub=Stub({SEED:home})
        r=discover(self.root,day=day,opener=stub,pacer=self.pacer)
        self.assertEqual(stub.calls,[SEED])
        self.assertFalse(r["prediction_ready"])

    def test_wrong_day_rejected_without_requests(self):
        with self.assertRaisesRegex(SPDiscoveryError,"discovery_day_invalid"):
            discover(self.root,day="20261115",opener=Stub({}),pacer=self.pacer)
        self.assertFalse(self.root.exists())

    def test_unobserved_race_date_cannot_be_promoted(self):
        first=html('<a href="'+RACE.replace("20261121","20261122")+'">京都 12R</a>')
        r=discover(self.root,day=DAY,opener=Stub({SEED:first}),pacer=self.pacer)
        self.assertFalse(r["unique_observed_racecard"])

    def test_late_link_requires_actual_official_html_anchor(self):
        first=html('<a href="'+MEETING+'">京都 20261121 開催</a>')
        second=html("<p>京都 12R no href</p>")
        r=discover(self.root,day=DAY,opener=Stub({SEED:first,MEETING:second}),pacer=self.pacer)
        self.assertEqual(r["network_requests_started"],2)
        self.assertEqual(r["racecard_url"],"")

if __name__=="__main__":
    unittest.main()
