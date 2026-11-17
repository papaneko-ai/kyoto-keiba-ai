"""G03 12R archived-original audit tests: synthetic pages are *not* JRA evidence."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from diagnostics.kyoto_g03_all_races import audit, links, parse, G03Error

DAY="20261121"
PARENT="https://jra.jp/JRADB/accessD.html?CNAME=pw01dli00%2FF3"
def source_race(url):
    token=parse_qs(urlsplit(url).query)["CNAME"][0]
    return int(token[-13:-11])

def meeting(races=range(1,13),ambiguous=None):
    entries=[f'<a href="/JRADB/accessD.html?CNAME=pw01dde010820260501{r:02d}{DAY}%2FAA"></a>' for r in races]
    if ambiguous:
        entries.append(f'<a href="/JRADB/accessD.html?CNAME=pw01dde010820260501{ambiguous:02d}{DAY}%2FBB"></a>')
    return ("<html>"+''.join(entries)+"</html>").encode("cp932")
def card(count=8, time="発走 11:05", race=1, day=DAY, venue="京都"):
    body=''.join(
        f'<tr><td class="waku"><img alt="{min(8,(n+1)//2)}枠"></td>'
        f'<td class="num">{n}</td>'
        f'<td class="horse"><a href="/JRADB/accessU.html?CNAME=horse{n}">競走馬{n}</a></td></tr>'
        for n in range(1,count+1))
    date=f"{int(day[:4])}年{int(day[4:6])}月{int(day[6:])}日"
    return (
        f'<html><p>{date} {venue} {race}R {time}</p>'
        f'<table><tr><th class="waku">枠</th><th class="num">馬番</th>'
        f'<th class="horse">馬名</th></tr>{body}</table></html>'
    ).encode("cp932")

class G03AllRaces(unittest.TestCase):
    def test_all_twelve_link_observation(self):
        self.assertEqual(sorted(links(meeting(),PARENT,DAY)),list(range(1,13)))
    def test_historical_real_jra_20261107_selector_links_with_empty_labels(self):
        # Official CNAMEs recorded in JRA_LIVE_NAV_DISCOVERY_20261106.json.
        suffixes=["C1","76","2B","E0","95","4A","FF","B4","69","5E","13","C8"]
        raw=("<html>"+''.join(
            f'<a href="/JRADB/accessD.html?CNAME=pw01dde010820260501{race:02d}20261107/{sig}"></a>'
            for race,sig in enumerate(suffixes,1))+"</html>").encode("cp932")
        discovered=links(raw,PARENT,"20261107")
        self.assertEqual(sorted(discovered),list(range(1,13)))
        for race,sig in enumerate(suffixes,1):
            self.assertIn(f"{race:02d}20261107/{sig}",discovered[race])
    def test_other_venue_and_wrong_day_never_selected(self):
        original=(
            '<a href="/JRADB/accessD.html?CNAME=pw01dde0105202605010120261121/AA"></a>'
            '<a href="/JRADB/accessD.html?CNAME=pw01dde0108202605010120261122/BB"></a>'
        ).encode("cp932")
        self.assertFalse(links(original,PARENT,DAY))
    def test_label_contradicting_token_rejected(self):
        raw='<a href="/JRADB/accessD.html?CNAME=pw01dde0108202605010120261121/AA">京都2R</a>'.encode("cp932")
        with self.assertRaisesRegex(G03Error,"contradictory_race_label"):
            links(raw,PARENT,DAY)
    def test_no_guessed_missing_link(self):
        self.assertEqual(sorted(links(meeting(range(1,12)),PARENT,DAY)),list(range(1,12)))
    def test_duplicate_observed_anchor_rejected(self):
        with self.assertRaisesRegex(G03Error,"ambiguous"):
            links(meeting(ambiguous=4),PARENT,DAY)
    def test_unauthorized_host_does_not_supply_links(self):
        rogue='<a href="https://example.org/JRADB/accessD.html?CNAME=pw00test0120261121%2FAA">京都 1R</a>'.encode("cp932")
        self.assertFalse(links(rogue,PARENT,DAY))
    def test_twelve_saved_originals_and_all_rosters(self):
        with tempfile.TemporaryDirectory() as td:
            called=[]
            def fetch(url):
                called.append(url)
                return card(3+source_race(url),race=source_race(url))
            result=audit(DAY,meeting(),PARENT,fetch,lambda:"2026-11-21T01:01:00Z",Path(td)/"new")
            self.assertTrue(result["complete"])
            self.assertEqual(len(called),12)
            self.assertEqual(result["races"]["12"]["runner_count"],15)
            self.assertEqual(result["races"]["1"]["runner_count"],4)
            for r in range(1,13):
                original=(Path(td)/"new"/f"official_racecard_{r:02d}.html").read_bytes()
                self.assertEqual(result["races"][str(r)]["sha256"],hashlib.sha256(original).hexdigest())
    def test_missing_race_is_partial_not_success(self):
        with tempfile.TemporaryDirectory() as td:
            result=audit(DAY,meeting(range(1,12)),PARENT,lambda url:card(race=source_race(url)),lambda:"2026-11-21T01:00:00Z",Path(td)/"new")
            self.assertFalse(result["complete"])
            self.assertEqual(result["missing"],[12])
    def test_missing_start_time_is_partial_not_success(self):
        with tempfile.TemporaryDirectory() as td:
            result=audit(DAY,meeting(),PARENT,lambda url:card(time="発走未定",race=6) if source_race(url)==6 else card(race=source_race(url)),lambda:"2026-11-21T01:00:00Z",Path(td)/"new")
            self.assertFalse(result["complete"])
            self.assertEqual(result["missing"],[6])
    def test_duplicate_horse_number_rejected(self):
        raw=card().replace(b'>8</td>',b'>7</td>')
        with self.assertRaisesRegex(G03Error,"non_contiguous_numbers"):
            parse(raw,DAY,1,PARENT,"2026-11-21T01:00:00Z")
    def test_wrong_official_race_identity_rejected(self):
        with self.assertRaisesRegex(G03Error,"race_number_not_confirmed"):
            parse(card(race=9),DAY,8,PARENT,"2026-11-21T01:00:00Z")
    def test_wrong_official_day_rejected(self):
        with self.assertRaisesRegex(G03Error,"date_not_confirmed"):
            parse(card(day="20261122"),DAY,1,PARENT,"2026-11-21T01:00:00Z")
    def test_wrong_venue_rejected(self):
        with self.assertRaisesRegex(G03Error,"kyoto_venue_not_in_original"):
            parse(card(venue="東京"),DAY,1,PARENT,"2026-11-21T01:00:00Z")
    def test_missing_frame_rejected(self):
        raw=card().replace('alt="1枠"'.encode("cp932"),b'alt="broken"')
        with self.assertRaisesRegex(G03Error,"frame_missing"):
            parse(raw,DAY,1,PARENT,"2026-11-21T01:00:00Z")
    def test_no_naive_timestamp(self):
        with self.assertRaisesRegex(G03Error,"timestamp_not_utc"):
            parse(card(),DAY,1,PARENT,"2026-11-21T01:00:00")

if __name__=="__main__": unittest.main()
