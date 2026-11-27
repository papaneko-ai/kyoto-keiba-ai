"""Synthetic HTML tests; do not claim real-source coverage."""
import unittest
from diagnostics.kyoto_impl35_cushion_candidate import INDEX, Rejected, observed_links, parse_detail

URL = "https://keiba-win-net.com/updates/" + "a"*64
DAY = "20261122"
CAPTURE = "2026-11-22T02:00:00Z"
HTML = """<h1>京都 11月22日（日曜）7時00分 クッション値 9.7</h1>
<p>公開：未掲載 ／ 初回取得：2026/11/22 10:30:46（日本時間）</p>
<dl><dt>競馬場</dt><dd>京都</dd><dt>クッション値</dt><dd>9.7</dd>
<dt>測定日時の原表記</dt><dd>11月22日（日曜）7時00分</dd></dl>
<a href="https://www.jra.go.jp/keiba/baba/">原文</a>"""
def raw(s=HTML):
    return s.encode("utf8")

class TestCandidate(unittest.TestCase):
    def parse(self, s=HTML, **kwargs):
        return parse_detail(raw(s), kwargs.pop("day", DAY), kwargs.pop("url", URL),
                            kwargs.pop("capture", CAPTURE), **kwargs)
    def test_valid(self):
        r = self.parse(cutoff_utc="2026-11-22T02:30:00Z")
        self.assertEqual(r["cushion_value"], "9.7")
        self.assertEqual(r["measurement_utc"], "2026-11-21T22:00:00+00:00")
        self.assertTrue(r["capture_before_cutoff"])
        self.assertFalse(r["prediction_ready"])
        self.assertFalse(r["official_publication_time_verified"])
    def test_late(self):
        self.assertFalse(self.parse(cutoff_utc="2026-11-22T01:00:00Z")["capture_before_cutoff"])
    def test_equal_cutoff(self):
        self.assertFalse(self.parse(cutoff_utc=CAPTURE)["capture_before_cutoff"])
    def test_wrong_day(self):
        with self.assertRaises(Rejected): self.parse(day="20261121")
    def test_wrong_venue(self):
        with self.assertRaises(Rejected): self.parse(HTML.replace("<dd>京都</dd>", "<dd>東京</dd>"))
    def test_conflicting_value(self):
        with self.assertRaises(Rejected): self.parse(HTML.replace("<dd>9.7</dd>", "<dd>10.0</dd>"))
    def test_wrong_measurement(self):
        with self.assertRaises(Rejected): self.parse(HTML.replace("7時00分</dd>", "8時00分</dd>"))
    def test_future_provider(self):
        with self.assertRaises(Rejected): self.parse(capture="2026-11-22T01:00:00Z")
    def test_missing_official(self):
        with self.assertRaises(Rejected): self.parse(HTML.replace("www.jra.go.jp", "example.com"))
    def test_wrong_host(self):
        with self.assertRaises(Rejected): self.parse(url=URL.replace("keiba-win-net.com", "example.com"))
    def test_discovery(self):
        title = "京都 11月22日（日曜）7時00分 クッション値 9.7"
        html = f'<a href="{URL}">{title}</a><a href="https://example.com/updates/x">{title}</a>'
        self.assertEqual(observed_links(raw(html), DAY), [URL])
        self.assertEqual(observed_links(raw(html), "20261121"), [])
    def test_no_implicit_url(self):
        self.assertEqual(observed_links(raw(HTML), DAY), [])
    def test_wrong_index(self):
        with self.assertRaises(Rejected): observed_links(raw(HTML), DAY, "https://example.com/")
    def test_scale_not_measurement(self):
        with self.assertRaises(Rejected): self.parse("<h1>京都競馬</h1><p>クッション値 12 10 8 7</p>")
    def test_deterministic(self):
        self.assertEqual(self.parse(), self.parse())

if __name__ == "__main__":
    unittest.main()
