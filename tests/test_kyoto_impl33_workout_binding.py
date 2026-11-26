import unittest
from diagnostics.kyoto_impl33_workout_binding import bind
from diagnostics.kyoto_impl33_whitegreen_probe import FINAL,SAMPLES
from test_kyoto_impl33_whitegreen_probe import table


def case(extra='', wrong_name=False, bad_date=False, result=True):
    d,r,u=SAMPLES[0];summary=table(FINAL,[['1','1','A','A','栗東CW','6F 80.0','11.0','単走'],['2','2','X' if wrong_name else 'B','B','栗東坂路','4F 55.0','12.0','単走']]); history=''
    for name in ['A','B']:
        history+='<h3>'+name+'</h3><h4>最終追い切りまでの21日間</h4>'+table(('日','コース','本線','終い'),[['11/30' if bad_date else '11/18','栗東CW','6F 80.0','11.0']])
    raw=('<h1>京都1R 最終追い切り分析</h1><p>2026年11月22日</p>'+('<h2>レース結果</h2>' if result else '')+summary+history+extra).encode()
    return raw,d,r,u,'2026-11-26T04:00:00Z',{1:'A',2:'B'},'2026-11-22T01:05:00Z'


class Binding(unittest.TestCase):
    def test_full_history_still_historical(self):
        r,records=bind(*case());self.assertEqual(r['history_horses_bound'],2);self.assertEqual(r['bound_dated_records'],2);self.assertTrue(r['historical_only']);self.assertFalse(r['prestart_candidate']);self.assertFalse(r['production_coverage_authorized']);self.assertEqual(records[1][0]['last_1f_s'],11)
    def test_wrong_roster(self):
        with self.assertRaisesRegex(ValueError,'source_official_roster_mismatch'):bind(*case(wrong_name=True))
    def test_future_workout_missing_not_zero(self):
        r,records=bind(*case(bad_date=True));self.assertEqual(r['bound_dated_records'],0);self.assertEqual(r['unbound_or_invalid_rows'],2);self.assertEqual(records[1],[])
    def test_duplicate_history_rejected(self):
        extra='<h3>A</h3><h4>最終追い切りまでの21日間</h4>'+table(('日','コース','本線','終い'),[['11/19','栗東CW','6F 80.0','11.0']])
        with self.assertRaisesRegex(ValueError,'ambiguous_horse_history'):bind(*case(extra=extra))
    def test_mismatched_start_date(self):
        args=list(case());args[-1]='2026-11-23T01:05:00Z'
        with self.assertRaisesRegex(ValueError,'official_start_identity'):bind(*args)
    def test_wrong_heading_no_false_binding(self):
        args=list(case());args[0]=args[0].replace('<h3>A</h3>'.encode(),'<h3>unknown</h3>'.encode());r,_=bind(*args);self.assertEqual(r['horses_with_dated_workout'],1);self.assertEqual(r['unbound_or_invalid_rows'],1)
    def test_deterministic(self):self.assertEqual(bind(*case()),bind(*case()))

if __name__=='__main__':unittest.main()
