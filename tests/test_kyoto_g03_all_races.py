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
def card(count=8, time="発走 11:05"):
    body=''.join(f'<tr><td class="waku">1</td><td class="num">{n}</td><td class="horse"><a href="/JRADB/accessU.html?CNAME=horse{n}">競走馬{n}</a></td></tr>' for n in range(1,count+1))
    return (f'<html><p>{time}</p><table><tr><th class="waku">枠</th><th class="num">馬番</th><th class="horse">馬名</th></tr>{body}</table></html>').encode("cp932")

class G03AllRaces(unittest.TestCase):
    def test_all_twelve_link_observation(self):
        self.assertEqual(sorted(links(meeting(),PARENT,DAY)),list(range(1,13)))
    def test_no_guessed_missing_link(self):
        self.assertEqual(sorted(links(meeting(range(1,12)),PARENT,DAY)),list(range(1,12)))
    def test_duplicate_observed_anchor_rejected(self):
        with self.assertRaisesRegex(G03Error,"ambiguous"):
            links(meeting(ambiguous=4),PARENT,DAY)
    def test_unauthorized_host_does_not_supply_links(self):
        rogue=b'<a href="https://example.org/JRADB/accessD.html?CNAME=pw00test0120261121%2FAA">京都 1R</a>'
        self.assertFalse(links(rogue,PARENT,DAY))
    def test_twelve_saved_originals_and_all_rosters(self):
        with tempfile.TemporaryDirectory() as td:
            called=[]
            def fetch(url):
                called.append(url)
                return card(3+int(url.split("test")[1][:2]))
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
            result=audit(DAY,meeting(range(1,12)),PARENT,lambda _:card(),lambda:"2026-11-21T01:00:00Z",Path(td)/"new")
            self.assertFalse(result["complete"])
            self.assertEqual(result["missing"],[12])
    def test_missing_start_time_is_partial_not_success(self):
        with tempfile.TemporaryDirectory() as td:
            result=audit(DAY,meeting(),PARENT,lambda url:card(time="発走未定") if "test06" in url else card(),lambda:"2026-11-21T01:00:00Z",Path(td)/"new")
            self.assertFalse(result["complete"])
            self.assertEqual(result["missing"],[6])
    def test_duplicate_horse_number_rejected(self):
        raw=card().replace(b'>8</td>',b'>7</td>')
        with self.assertRaisesRegex(G03Error,"incomplete_roster"):
            parse(raw,DAY,1,PARENT,"2026-11-21T01:00:00Z")
    def test_no_naive_timestamp(self):
        with self.assertRaisesRegex(G03Error,"timestamp_not_utc"):
            parse(card(),DAY,1,PARENT,"2026-11-21T01:00:00")

if __name__=="__main__": unittest.main()
