"""G05 independent JRA Kyoto track page source receipt tests."""
import tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_g05_official_track import (
    KYOTO_TRACK_PAGE,parse_kyoto_track,capture_kyoto_track,G05TrackRejected)

DAY="20261121"
def html(day=DAY,venue="京都"):
    iso=f"{int(day[:4])}年{int(day[4:6])}月{int(day[6:])}日"
    return (f'<html><main><h2>第5回{venue}競馬第5日（{iso}（土曜））</h2>'
        f'<section><h3>馬場状態（{int(day[4:6])}月{int(day[6:])}日9時30分現在）</h3>'
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

    def test_current_canonical_url_single_request_and_four_moisture_fields(self):
        day="20261129";stamp="2026-11-29T01:05:00Z"
        self.assertEqual(KYOTO_TRACK_PAGE,"https://www.jra.go.jp/keiba/baba/index2.html")
        table='<table><caption>ゴール前と4コーナーの含水率</caption><tr><th></th><th>ゴール前</th><th>4コーナー</th></tr><tr><th>芝</th><td>10.1</td><td>9.2</td></tr><tr><th>ダート</th><td>7.4</td><td>7.1</td></tr></table>'
        measurement=f'<div class="line moist"><div class="grid">測定時刻 {int(day[4:6])}月{int(day[6:])}日9時30分</div>{table}</div>'
        raw=html(day).replace(b'</main>',measurement.encode("utf8")+b'</main>')
        from diagnostics.kyoto_impl30_day_coverage import independent_track
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);calls=[]
            def fetch(url):calls.append(url);return raw
            result=capture_kyoto_track(root,day,fetch,lambda:stamp,allowed=True)
            self.assertEqual(calls,[KYOTO_TRACK_PAGE])
            self.assertEqual(result["turf_moisture_finish_pct"],10.1)
            self.assertEqual(result["turf_moisture_turn4_pct"],9.2)
            self.assertEqual(result["dirt_moisture_finish_pct"],7.4)
            self.assertEqual(result["dirt_moisture_turn4_pct"],7.1)
            self.assertIn("turf_moisture_finish_pct",independent_track(root,day))
    def test_legacy_receipt_replay_and_wrong_origin_rejection(self):
        import json
        from diagnostics.kyoto_g05_official_track import LEGACY_KYOTO_TRACK_PAGE
        from diagnostics.kyoto_impl30_day_coverage import independent_track
        day="20261129";stamp="2026-11-29T01:05:00+00:00"
        raw=html(day)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"g05_official_kyoto_track.html").write_bytes(raw)
            receipt=parse_kyoto_track(raw,day,LEGACY_KYOTO_TRACK_PAGE,stamp)
            receipt["requested_at_utc"]=stamp
            p=root/"g05_track_receipt.json";p.write_text(json.dumps(receipt))
            self.assertIn("weather",independent_track(root,day))
            for bad in ("https://www.jra.go.jp.evil.test/keiba/baba/index2.html","https://www.jra.go.jp/keiba/baba/index.html","https://www.jra.go.jp/keiba/baba/index2.html?x=1"):
                receipt["source_url"]=bad;p.write_text(json.dumps(receipt))
                self.assertEqual(independent_track(root,day),{})
    def test_http_failure_receipt_preserves_status_without_retry_or_data_credit(self):
        import json
        from urllib.error import HTTPError
        from diagnostics.kyoto_impl30_day_coverage import independent_track
        day="20261129";stamp="2026-11-29T01:05:00Z"
        for status in (301,403,404,429,503):
            with self.subTest(status=status),tempfile.TemporaryDirectory() as td:
                root=Path(td);calls=[]
                def fetch(url):
                    calls.append(url);raise HTTPError(url,status,"DO_NOT_PERSIST_EXCEPTION_TEXT",{},None)
                with self.assertRaises(HTTPError):capture_kyoto_track(root,day,fetch,lambda:stamp,allowed=True)
                self.assertEqual(calls,[KYOTO_TRACK_PAGE])
                p=root/"g05_track_receipt.json";result=json.loads(p.read_text())
                self.assertEqual(result["http_status"],status)
                self.assertEqual(result["error_code"],"HTTP_STATUS_"+str(status))
                self.assertEqual(result["state"],"TRACK_FETCH_FAILED")
                self.assertNotIn("DO_NOT_PERSIST_EXCEPTION_TEXT",p.read_text())
                self.assertFalse((root/"g05_official_kyoto_track.html").exists())
                self.assertEqual(independent_track(root,day),{})
    def test_parse_rejection_preserves_original_and_failure_receipt(self):
        import json,hashlib
        from diagnostics.kyoto_impl30_day_coverage import independent_track
        day="20261129";stamp="2026-11-29T01:05:00Z";raw=b"\x81"
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with self.assertRaises(G05TrackRejected):capture_kyoto_track(root,day,lambda _:raw,lambda:stamp,allowed=True)
            result=json.loads((root/"g05_track_receipt.json").read_text())
            self.assertEqual(result["state"],"TRACK_PARSE_FAILED")
            self.assertEqual(result["source_sha256"],hashlib.sha256(raw).hexdigest())
            self.assertEqual((root/"g05_official_kyoto_track.html").read_bytes(),raw)
            self.assertEqual(independent_track(root,day),{})
    def test_same_calendar_day_but_next_meeting_eve_is_not_current_measurement(self):
        raw=html("20261129").replace("第5日".encode("utf8"),"第6日前日".encode("utf8"))
        r=parse_kyoto_track(raw,"20261129",KYOTO_TRACK_PAGE,"2026-11-29T01:05:00Z")
        self.assertFalse(r["same_day_official_meeting_heading_verified"])
        self.assertIsNone(r["weather"])

    def test_actual_stale_header_and_undated_measurements(self):
        day="20261128";stamp="2026-11-28T06:33:00Z"
        meeting='<h2>第5回京都競馬第5日（2026年11月28日）</h2>'
        condition='<div class="line condition"><div class="block_header"><h3>馬場状態（11月27日（金曜）正午現在）</h3></div><div class="grid">天候： 晴 芝 良 ダート 稍重</div></div>'
        table='<div class="line moist"><div class="grid">測定時刻 変更</div><table><caption>ゴール前と4コーナーの含水率</caption><tr><th></th><th>ゴール前</th><th>4コーナー</th></tr><tr><th>芝</th><td>10.1</td><td>9.2</td></tr><tr><th>ダート</th><td>7.4</td><td>7.1</td></tr></table></div>'
        raw=(meeting+condition+table).encode("utf8")
        stale=parse_kyoto_track(raw,day,KYOTO_TRACK_PAGE,stamp)
        self.assertTrue(stale["same_day_official_meeting_heading_verified"])
        for k in ("weather","turf_going","dirt_going","condition_observation_utc","moisture_observation_utc","turf_moisture_finish_pct"):
            self.assertIsNone(stale[k])
        self.assertEqual(len(stale["undated_moisture_observations"]),4)
        fresh=raw.decode("utf8").replace("11月27日（金曜）正午","11月28日（土曜）正午").replace("測定時刻 変更","測定時刻 11月28日9時")
        r=parse_kyoto_track(fresh.encode(),day,KYOTO_TRACK_PAGE,stamp)
        self.assertEqual((r["weather"],r["turf_going"],r["dirt_going"]),("晴","良","稍重"))
        self.assertEqual(r["condition_observation_utc"],"2026-11-28T03:00:00+00:00")
        self.assertEqual(r["turf_moisture_finish_pct"],10.1)
        self.assertEqual(r["undated_moisture_observations"],{})
        for bad in (fresh.replace("正午","18時"),fresh.replace("11月28日（土曜）正午","時刻未定"),fresh+condition):
            self.assertIsNone(parse_kyoto_track(bad.encode(),day,KYOTO_TRACK_PAGE,stamp)["turf_going"])
        future=fresh.replace("11月28日9時","11月28日18時")
        self.assertIsNone(parse_kyoto_track(future.encode(),day,KYOTO_TRACK_PAGE,stamp)["turf_moisture_finish_pct"])
        detached=fresh.replace("<table>","</div><table>").replace("</table></div>","</table>")
        self.assertIsNone(parse_kyoto_track(detached.encode(),day,KYOTO_TRACK_PAGE,stamp)["turf_moisture_finish_pct"])
        ambiguous=fresh.replace("11月28日9時","11月28日9時 11月27日9時")
        self.assertIsNone(parse_kyoto_track(ambiguous.encode(),day,KYOTO_TRACK_PAGE,stamp)["turf_moisture_finish_pct"])

if __name__=="__main__":unittest.main()
