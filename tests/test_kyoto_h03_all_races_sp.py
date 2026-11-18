"""H03 12-race offline regression; no HTTP calls to a real network."""
import tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_h03_all_races_sp import plan_all_races,collect_all_races,H03Error
DAY='20261121'
SRC='https://sp.jra.jp/JRADB/accessD.html?CNAME=sw00meeting%2F20261121'
def nav(numbers):
    return ('<html>'+''.join(f'<a href="/JRADB/accessD.html?CNAME=sw020aaa{n:02d}%2F{n:02d}{DAY}">京都 {n}R</a>' for n in numbers)+'</html>').encode('cp932')
class Reply:
    status=200
    headers={'Content-Type':'text/html'}
    def __init__(self,url):self.url=url
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def geturl(self):return self.url
    def read(self,n):
        return ('<table><tr><td class="wban">1</td><td class="uban">1</td><td><a href="/JRADB/accessU.html?CNAME=real">馬名</a></td></tr></table>').encode('cp932')
class Opener:
    def __init__(self):self.calls=[]
    def open(self,request,timeout):
        self.calls.append(request.full_url)
        return Reply(request.full_url)
class Pacer:
    def before_request(self):pass
class TestH03(unittest.TestCase):
    def test_all_twelve_independently_observed(self):
        x=plan_all_races(nav(range(1,13)),nav_url=SRC,day=DAY,captured_utc='2026-11-21T01:00:00Z')
        self.assertTrue(x['complete_navigation']);self.assertEqual(len(x['observed']),12)
    def test_missing_anchor_not_guessed(self):
        x=plan_all_races(nav([12]),nav_url=SRC,day=DAY,captured_utc='2026-11-21T01:00:00Z')
        self.assertEqual(x['missing_races'],list(range(1,12)))
    def test_all_twelve_capture_one_per_race(self):
        with tempfile.TemporaryDirectory() as d:
            client=Opener()
            x=collect_all_races(Path(d)/'originals',nav_original=nav(range(1,13)),
                  nav_url=SRC,day=DAY,captured_utc='2026-11-21T01:00:00Z',opener=client,pacer=Pacer())
            self.assertEqual(x['captured_races'],12)
            self.assertEqual(x['parsed_rosters'],12)
            self.assertEqual(len(client.calls),12)
            self.assertFalse(x['h03_certified'])
            self.assertTrue((Path(d)/'originals'/'h03_summary.json').is_file())
    def test_missing_link_never_requested(self):
        with tempfile.TemporaryDirectory() as d:
            client=Opener()
            x=collect_all_races(Path(d)/'originals',nav_original=nav([12]),
                  nav_url=SRC,day=DAY,captured_utc='2026-11-21T01:00:00Z',opener=client,pacer=Pacer())
            self.assertEqual(len(client.calls),1)
            self.assertEqual(x['receipts'][0]['state'],'UNOBSERVED_LINK')
    def test_invalid_provenance_and_preexisting_output(self):
        with self.assertRaises(H03Error):
            plan_all_races(nav([1]),nav_url=SRC.replace('sp.jra.jp','www.jra.go.jp'),day=DAY,captured_utc='2026-11-21T01:00:00Z')
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(H03Error):
                collect_all_races(d,nav_original=nav([1]),nav_url=SRC,
                  day=DAY,captured_utc='2026-11-21T01:00:00Z',opener=Opener())
if __name__=='__main__':unittest.main()
