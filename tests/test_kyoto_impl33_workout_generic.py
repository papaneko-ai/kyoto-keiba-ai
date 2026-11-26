import unittest
from diagnostics.kyoto_impl33_workout_generic import discover,candidate_links,bridge
from diagnostics.kyoto_impl33_whitegreen_probe import HOST,PREVIEW
from test_kyoto_impl33_whitegreen_probe import table
DAY='20261128';URL=HOST+'/race/20261128-kyoto-09/'
def sample():
    return ('<h1>京都9R 1週前調教分析</h1><p>2026年11月28日</p>'+table(PREVIEW,[['A','A','栗東CW','6F 80.0','11.0'],['B','B','栗東CW','6F 82.0','12.0'],['C','A','栗東CW','6F 81.0','11.0']])+''.join('<h3>'+n+'</h3><h4>直近21日間</h4>'+table(('日','コース','本線','終い'),[['11/24','栗東CW','6F 80.0','11.0']]) for n in ('A','B','C'))).encode()
class Generic(unittest.TestCase):
    def test_day_links(self):
        a=discover(b'<a href="/race/20261128-kyoto-09/">x</a><a href="/race/20261129-kyoto-09/">y</a>',DAY);self.assertEqual(a,{9:URL})
    def test_secondary_link_selection(self):
        raw='<a href="/a">A 追い切り</a><a href="/b">B 追い切り</a><a href="https://bad.example/a">A 調教</a>'.encode()
        self.assertEqual(candidate_links(raw,'https://good.example/index',allowed_hosts={'good.example'},horse_names=['A'],race_name='R'),['https://good.example/a'])
    def test_preview_join_actual_number(self):
        r,_,records,_=bridge(sample(),DAY,9,URL,'2026-11-26T04:00:00Z',((DAY,9,URL),),{2:'A',5:'B'},'2026-11-28T04:00:00Z')
        self.assertEqual(r['canonical_valid_horses'],2);self.assertEqual(set(records),{2,5});self.assertFalse(r['production_coverage_authorized']);self.assertEqual(records[2][0]['last_1f_s'],11)
    def test_missing_starter(self):
        r,_,_,_=bridge(sample(),DAY,9,URL,'2026-11-26T04:00:00Z',((DAY,9,URL),),{2:'A',5:'D'},'2026-11-28T04:00:00Z')
        self.assertEqual(r['canonical_valid_horses'],1)
    def test_poststart_rejected(self):
        with self.assertRaises(ValueError):bridge(sample(),DAY,9,URL,'2026-11-28T04:01:00Z',((DAY,9,URL),),{2:'A',5:'B'},'2026-11-28T04:00:00Z')
if __name__=='__main__':unittest.main()
