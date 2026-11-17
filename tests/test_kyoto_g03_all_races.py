"""G03 12R archived-original audit tests: synthetic pages are *not* JRA evidence."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from diagnostics.kyoto_g03_all_races import audit, links, parse, G03Error

DAY="20261121"
PARENT="https://jra.jp/JRADB/accessD.html?CNAME=pw01dli00%2FF3"
def meeting(races=range(1,13),ambiguous=None):
    entries=[f'<a href="/JRADB/accessD.html?CNAME=pw00test{r:02d}{DAY}%2FAA">京都 {r}R</a>' for r in races]
    if ambiguous: entries.append(f'<a href="/JRADB/accessD.html?CNAME=pw99test{ambiguous:02d}{DAY}%2FBB">京都 {ambiguous}R</a>')
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
                return card(3+int(url.split("test")[1][:2]),race=int(url.split("test")[1][:2]))
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
            result=audit(DAY,meeting(range(1,12)),PARENT,lambda url:card(race=int(url.split("test")[1][:2])),lambda:"2026-11-21T01:00:00Z",Path(td)/"new")
            self.assertFalse(result["complete"])
            self.assertEqual(result["missing"],[12])
    def test_missing_start_time_is_partial_not_success(self):
        with tempfile.TemporaryDirectory() as td:
            result=audit(DAY,meeting(),PARENT,lambda url:card(time="発走未定",race=6) if "test06" in url else card(race=int(url.split("test")[1][:2])),lambda:"2026-11-21T01:00:00Z",Path(td)/"new")
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
