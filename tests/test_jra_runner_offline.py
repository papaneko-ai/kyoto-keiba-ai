import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from diagnostics.jra_runner_offline import inspect_html, safe_write_report
NOW = datetime(2026, 11, 6, 2, 0, tzinfo=timezone.utc)
URL = 'https://www.jra.go.jp/JRADB/accessR.html'
HTML = """<html><table><tr><th>着順</th><th>馬名</th></tr>
<tr><td>1</td><td><a onclick="doAction('/JRADB/accessR.html','CNAME001')">馬Ａ</a></td></tr>
<tr><td>2</td><td><a onclick="doAction('/JRADB/accessR.html','CNAME002')">馬Ｂ</a></td></tr>
</table></html>""".encode('cp932')
class OfflineRunnerTests(unittest.TestCase):
    def test_candidates_are_not_verified(self):
        r=inspect_html(HTML,source_url=URL,fetched_at_utc=NOW)
        self.assertEqual(r['candidate_count'],2)
        self.assertEqual(r['candidates'][0]['action_token'],'CNAME001')
        self.assertIsNone(r['candidates'][0]['explicit_horse_id'])
        self.assertFalse(r['full_race_verified'])
        self.assertFalse(r['ready_for_model'])
    def test_determinism(self):
        self.assertEqual(inspect_html(HTML,source_url=URL,fetched_at_utc=NOW),
                         inspect_html(HTML,source_url=URL,fetched_at_utc=NOW))
    def test_duplicate(self):
        row='<tr><td><a onclick="doAction(\'/JRADB/accessR.html\',\'CNAME001\')">馬Ａ</a></td></tr>'.encode('cp932')
        r=inspect_html(HTML.replace(b'</table>',row+b'</table>'),source_url=URL,fetched_at_utc=NOW)
        self.assertEqual(r['candidate_count'],2)
    def test_untrusted_host(self):
        with self.assertRaises(ValueError): inspect_html(HTML,source_url='https://evil.example',fetched_at_utc=NOW)
    def test_no_naive_timestamp(self):
        with self.assertRaises(ValueError): inspect_html(HTML,source_url=URL,fetched_at_utc=datetime(2026,11,6))
    def test_no_unrelated_links(self):
        self.assertEqual(inspect_html(b'<table><tr><td><a href="/faq/">HELP</a></td></tr></table>',source_url=URL,fetched_at_utc=NOW)['candidate_count'],0)
    def test_explicit_id_still_unverified(self):
        r=inspect_html(b'<table><tr><td><a href="/horse?horse_id=1234567890">Runner</a></td></tr></table>',source_url=URL,fetched_at_utc=NOW)
        self.assertEqual(r['candidates'][0]['explicit_horse_id'],'1234567890')
        self.assertFalse(r['ready_for_model'])
    def test_report_gate_and_empty(self):
        r=inspect_html(HTML,source_url=URL,fetched_at_utc=NOW)
        with TemporaryDirectory() as d:
            p=Path(d)/'report.json'
            safe_write_report(p,r)
            self.assertTrue(p.exists())
            r['ready_for_model']=True
            with self.assertRaises(ValueError):safe_write_report(p,r)
        with self.assertRaises(ValueError):inspect_html(b'',source_url=URL,fetched_at_utc=NOW)
if __name__=='__main__':unittest.main()
