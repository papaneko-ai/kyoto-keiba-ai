import unittest
from unittest.mock import patch
from diagnostics.kyoto_impl33_whitegreen_probe import inspect, probe, SAMPLES, FINAL, PREVIEW, timing


def table(header, rows):
    return '<table><tr>'+''.join('<th>'+c+'</th>' for c in header)+'</tr>'+''.join('<tr>'+''.join('<td>'+c+'</td>' for c in row)+'</tr>' for row in rows)+'</table>'


def sample(final=True, duplicate=False, wrong=False, result=False):
    d,r,u=SAMPLES[0 if final else 1]
    title=f'<h1>京都{r if not wrong else 2}R 最終追い切り分析</h1><p>2026年11月{d[-2:]}日</p>'
    rows=[['1','1','A','A','栗東CW','6F 83.5','12.3','単走'],['2','1' if duplicate else '2','B','C','栗東坂路','—','—','単走']] if final else [['A','A','美浦W','6F 86.2','11.6'],['B','C','—','—','—']]
    hist=table(('日','コース','本線','終い'),[['11/18','栗東CW','6F 83.5','12.3'],['11/30','栗東CW','6F 80.0','11.0']])
    raw=(title+('<h2>レース結果</h2>' if result else '')+table(FINAL if final else PREVIEW,rows)+hist).encode()
    return raw,d,r,u,'2026-11-26T04:00:00Z'


class Probe(unittest.TestCase):
    def test_final_historical_not_prerace(self):
        r=inspect(*sample(result=True));self.assertEqual((r['summary_rows'],r['rows_with_numeric_times'],r['dated_numeric_history_rows']),(2,1,1));self.assertTrue(r['result_section_present']);self.assertFalse(r['observed_before_race_day']);self.assertFalse(r['production_coverage_authorized'])
    def test_preview_not_official_roster(self):
        r=inspect(*sample(False));self.assertEqual(r['summary_kind'],'SPECIAL_REGISTRATION_PREVIEW');self.assertTrue(r['observed_before_race_day']);self.assertFalse(r['independent_roster_verified']);self.assertFalse(r['horse_history_binding_verified'])
    def test_duplicate_and_wrong_identity(self):
        for raw in (sample(duplicate=True),sample(wrong=True)):
            with self.assertRaises(ValueError):inspect(*raw)
    def test_unknown_url(self):
        raw,d,r,u,s=sample()
        with self.assertRaisesRegex(ValueError,'unobserved_sample_identity'):inspect(raw,d,r,u+'x',s)
    def test_invalid_times(self):
        for args in [('栗東CW','6F 0','12.0'),('栗東CW','6F 90.0','99.0'),('unknown','6F 90.0','12.0'),('栗東CW','6F nan','12.0')]:self.assertIsNone(timing(*args))
    def test_robots_denied_no_sample_requests(self):
        with patch('diagnostics.kyoto_impl33_whitegreen_probe.get',return_value=b'User-agent: *\nDisallow: /race/') as g:
            r=probe();self.assertEqual(g.call_count,1);self.assertTrue(all(x['status']=='ROBOTS_DISALLOW' for x in r['samples']))
    def test_network_failure_separate_from_no_workouts(self):
        with patch('diagnostics.kyoto_impl33_whitegreen_probe.get',side_effect=[b'User-agent: *\nDisallow:',OSError(),sample(False)[0]]),patch('diagnostics.kyoto_impl33_whitegreen_probe.time.sleep'):
            r=probe();self.assertEqual(r['samples'][0]['status'],'UNVERIFIED');self.assertEqual(r['samples'][1]['status'],'PARSED_RESEARCH_SAMPLE')
    def test_deterministic(self):
        self.assertEqual(inspect(*sample()),inspect(*sample()))

if __name__=='__main__':unittest.main()
