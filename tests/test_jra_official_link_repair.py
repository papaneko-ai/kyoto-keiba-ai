"""Offline tests for the bounded official PC-only broken-link recovery."""
import unittest
from dataclasses import replace
from unittest.mock import patch
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from diagnostics.jra_one_shot_market_capture import (
    DEFAULT_RACE_SPEC, capture, PC_RACECARD_URL)
from diagnostics.jra_official_link_repair import (
    OFFICIAL_ENTRY, LinkRepairRejected, observed_links, repair_pc_racecard)

OLD=PC_RACECARD_URL
MEETING="https://jra.jp/JRADB/accessD.html?CNAME=pw01meet20261107%2FA1"
NEW="https://jra.jp/JRADB/accessD.html?CNAME=pw01race1120261107%2FA2"

def html(body):
    return ("<html><title>JRA</title><body>"+body+"</body></html>").encode("cp932")

def page(raw, url):
    import hashlib
    return dict(raw=raw, sha256=hashlib.sha256(raw).hexdigest(),
                bytes=len(raw),captured_at_utc="2026-11-06T10:00:00+00:00",
                requested_url=url, response_url=url, http_status=200)

def sources(*,duplicate=False,wrong_race=False,hostile=False):
    a=html('<a href="'+MEETING.replace("https://jra.jp","")+'">京都 11月7日</a>')
    href=NEW.replace("https://jra.jp","")
    if wrong_race:
        label="京都 10R"
    else:
        label="京都 11R"
    b=html('<a href="'+href+'">'+label+'</a>'+
           ('<a href="/JRADB/accessD.html?CNAME=pw01race1120261107%2FA3">京都 11R</a>' if duplicate else "")+
           ('<a href="https://jra.jp.evil.test/JRADB/accessD.html?CNAME=pw01race1120261107%2FA4">京都 11R</a>' if hostile else ""))
    return a,b,html("京都 11R 出馬表")

class OfflineRepairTests(unittest.TestCase):
    def perform(self, a,b,c):
        urls=[];saved=[]
        originals=[a,b,c]
        def fetch(url):
            urls.append(url)
            if len(urls)>3:raise AssertionError("unexpected further GET")
            return page(originals.pop(0),url)
        def retain(name,source):saved.append((name,source["sha256"]))
        def verify(raw,changed,captured):
            self.assertEqual(changed.pc_racecard_url,NEW)
            return dict(race_id=changed.race_id,count=2)
        return repair_pc_racecard(DEFAULT_RACE_SPEC,
                fetch=fetch,retain=retain,verify=verify),urls,saved

    def test_unique_observed_candidate_repaired_and_preserved(self):
        (changed,raw,receipt),urls,saved=self.perform(*sources())
        self.assertEqual(changed.pc_racecard_url,NEW)
        self.assertEqual(urls,[OFFICIAL_ENTRY,MEETING,NEW])
        self.assertEqual(len(saved),3)
        self.assertEqual(receipt["status"],"REPAIRED_VERIFIED_PC_ONLY")
        self.assertEqual(receipt["request_count"],3)
        self.assertTrue(receipt["no_guessed_urls"])

    def test_ambiguous_candidate_safe_stop_before_third_get(self):
        a,b,c=sources(duplicate=True)
        with self.assertRaisesRegex(LinkRepairRejected,"ambiguous"):
            self.perform(a,b,c)

    def test_wrong_race_safe_stop(self):
        with self.assertRaises(LinkRepairRejected):
            self.perform(*sources(wrong_race=True))

    def test_official_host_lookalike_ignored(self):
        (changed,_,_),urls,_=self.perform(*sources(hostile=True))
        self.assertEqual(changed.pc_racecard_url,NEW)
        self.assertEqual(len(urls),3)

    def test_no_unofficial_url_accepted(self):
        self.assertEqual(observed_links(
            html('<a href="https://jra.jp.evil.test/JRADB/accessD.html?CNAME=pwabc/AA">京都</a>'),
            OFFICIAL_ENTRY),[])

    def test_original_link_still_offered_refused(self):
        a,b,c=sources()
        b=b.replace(NEW.replace("https://jra.jp","").encode(),OLD.replace("https://jra.jp","").encode())
        # CNAME tokens appear encoded in the HTML bytes as %2F.
        with self.assertRaises(LinkRepairRejected):
            self.perform(a,b,c)

    def test_roster_proof_required(self):
        a,b,c=sources()
        originals=[a,b,c]
        with self.assertRaisesRegex(LinkRepairRejected,"candidate_roster_not_verified"):
            repair_pc_racecard(DEFAULT_RACE_SPEC,
                fetch=lambda url:page(originals.pop(0),url),
                retain=lambda n,p:None,
                verify=lambda raw,spec,when:{"race_id":"different_race"})

    def test_no_auto_repair_on_403_or_timeout(self):
        from diagnostics.jra_one_shot_market_capture import SourceChainError
        class Broken:
            def __init__(self,error):self.error=error;self.calls=0
            def open(self,request,timeout=None):
                self.calls+=1
                raise self.error
        for error in [HTTPError(OLD,403,"Forbidden",None,None),TimeoutError("offline")]:
            with self.subTest(error=str(error)),TemporaryDirectory() as directory:
                opener=Broken(error)
                result=capture(directory,channel="PC",
                    verified_start_utc="2026-11-07T06:45:00Z",
                    active_runners=((1,1),(2,2)),
                    now_utc="2026-11-06T10:00:00Z",opener=opener,
                    authorized_live_http=True,
                    auto_repair_broken_pc_link=True)
                self.assertEqual(result["state"],"CAPTURE_BLOCKED")
                self.assertEqual(opener.calls,1)

    def test_404_attempts_repair_then_blocks_if_unverified(self):
        class Broken:
            def __init__(self):self.calls=0
            def open(self,request,timeout=None):
                self.calls+=1
                if self.calls==1:
                    raise HTTPError(OLD,404,"Not Found",None,None)
                raise HTTPError(OFFICIAL_ENTRY,404,"Not Found",None,None)
        with TemporaryDirectory() as directory:
            opener=Broken()
            future=replace(DEFAULT_RACE_SPEC,race_day="20261114",
                race_id="2026-11-14_KYOTO_11R",
                pc_racecard_url="https://jra.jp/JRADB/accessD.html?CNAME=pw01race1120261114%2F11",
                sp_racecard_url="",
                normal_sales_open_utc="2026-11-13T09:30:00Z")
            result=capture(directory,channel="PC",
                verified_start_utc="2026-11-14T06:45:00Z",
                active_runners=((1,1),(2,2)),
                now_utc="2026-11-13T10:00:00Z",opener=opener,
                race_spec=future,
                authorized_live_http=True,auto_repair_broken_pc_link=True)
            self.assertEqual(opener.calls,2)
            self.assertEqual(result["state"],"CAPTURE_BLOCKED")
            self.assertEqual(result["link_repair"]["state"],"FAILED_CLOSED")
            self.assertFalse(result["pre_race_prices_accepted"])

if __name__=="__main__":
    unittest.main()
