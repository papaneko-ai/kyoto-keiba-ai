"""G05 independent JRA Kyoto track page source receipt tests."""
import tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_g05_official_track import (
    KYOTO_TRACK_PAGE,parse_kyoto_track,capture_kyoto_track,G05TrackRejected)

DAY="20261121"
def html(day=DAY,venue="京都"):
    iso=f"{int(day[:4])}年{int(day[4:6])}月{int(day[6:])}日"
    return (f'<html><main><h2>第5回{venue}競馬第5日（{iso}（土曜））</h2>'
        '<section><h3>馬場状態（11月21日（土曜）9時30分現在）</h3>'
        '<p>天候：晴</p><h4>芝</h4><p>良</p>'
        '<h4>ダート</h4><p>稍重</p></section>'
        '<h3>芝のクッション値</h3><p>10.1</p>'
        '<h3>週間情報</h3><p>11月15日は雨</p></main></html>').encode("utf8")

class KyotoTrackTests(unittest.TestCase):
    def test_verified_same_day_url_and_weather(self):
        r=parse_kyoto_track(html(),DAY,KYOTO_TRACK_PAGE,"2026-11-21T01:01:00Z")
        self.assertTrue(r["same_day_official_meeting_heading_verified"])
        self.assertEqual(r["weather"],"晴")
        self.assertFalse(r["data_asof_publication_time_utc_verified"])
        self.assertIsNone(r["cushion_value"])
        self.assertFalse(r["prediction_ready"])
    def test_official_cp932_track_original_decodes_without_replacement(self):
        source=html().decode("utf8").encode("cp932")
        r=parse_kyoto_track(source,DAY,KYOTO_TRACK_PAGE,"2026-11-21T01:01:00Z")
        self.assertTrue(r["same_day_official_meeting_heading_verified"])
        self.assertEqual(r["weather"],"晴")

    def test_previous_week_not_promoted(self):
        r=parse_kyoto_track(html("20261115"),DAY,KYOTO_TRACK_PAGE,"2026-11-21T01:01:00Z")
        self.assertFalse(r["same_day_official_meeting_heading_verified"])
        self.assertIsNone(r["weather"])
    def test_other_course_not_promoted(self):
        r=parse_kyoto_track(html(venue="東京"),DAY,KYOTO_TRACK_PAGE,"2026-11-21T01:01:00Z")
        self.assertFalse(r["same_day_official_meeting_heading_verified"])
    def test_unapproved_arbitrary_url_rejected(self):
        with self.assertRaisesRegex(G05TrackRejected,"nonofficial"):
            parse_kyoto_track(html(),DAY,"https://example.com/keiba/baba/index2.html","2026-11-21T01:01:00Z")
    def test_observer_saves_original_and_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            requests=[]
            def fetch(url):
                requests.append(url)
                return html()
            r=capture_kyoto_track(p,DAY,fetch,lambda:"2026-11-21T01:01:00Z",allowed=True)
            self.assertEqual(requests,[KYOTO_TRACK_PAGE])
            self.assertTrue((p/"g05_official_kyoto_track.html").is_file())
            self.assertEqual(r["weather"],"晴")
            with self.assertRaisesRegex(G05TrackRejected,"already_exists"):
                capture_kyoto_track(p,DAY,fetch,lambda:"2026-11-21T01:01:00Z",allowed=True)
            self.assertEqual(len(requests),1)
    def test_permission_blocks_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            called=[]
            with self.assertRaisesRegex(G05TrackRejected,"not_authorized"):
                capture_kyoto_track(tmp,DAY,lambda url:called.append(url),
                                    lambda:"2026-11-21T01:00:00Z",allowed=False)
            self.assertEqual(called,[])

if __name__=="__main__":unittest.main()
