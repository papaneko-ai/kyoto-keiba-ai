import unittest
from datetime import datetime,timezone
from unittest.mock import Mock,patch
from diagnostics.kyoto_impl33_workout_runtime import refresh_missing_secondary

D='20261128';U='https://umasiru.com/archives/22515'
O={'roster':{1:'A',2:'B'},'start':'2026-11-28T04:00:00Z'}
NOW=datetime(2026,11,28,1,tzinfo=timezone.utc)
def item(raw):
    return {'kind':'SECONDARY','race':11,'url':U,'stamp':'2026-11-27T10:00:00Z','raw':raw}
class Refresh(unittest.TestCase):
    def run_case(self,items,missing,attempted,clock=lambda:NOW,fail=False):
        fetch=Mock(side_effect=TimeoutError() if fail else None,return_value=b'new')
        save=Mock()
        def parse(x,name,day,start):
            return {'training_date':'2026-11-25','course':'X','distance_m':800,'clock':1} if x['raw']==b'new' or name=='A' else None
        with patch('diagnostics.kyoto_impl33_workout_runtime.secondary_record',side_effect=parse),patch('diagnostics.kyoto_impl33_workout_runtime.source_record',side_effect=lambda raw,stamp,url,kind,race:{**item(raw),'stamp':stamp}):
            r=refresh_missing_secondary(D,11,missing,O,[U],items,fetch,save,attempted,clock=clock)
        return r,fetch,save
    def test_cached_missing_refreshed(self):
        items=[item(b'old')];r,f,s=self.run_case(items,[1,2],set())
        f.assert_called_once_with(U);s.assert_called_once();self.assertTrue(r[1] and r[2]);self.assertEqual(len(items),2);self.assertEqual(items[0]['raw'],b'old')
    def test_cached_complete_no_http(self):
        r,f,s=self.run_case([item(b'old')],[1],set())
        f.assert_not_called();s.assert_not_called();self.assertTrue(r[1])
    def test_attempted_no_duplicate(self):
        r,f,s=self.run_case([item(b'old')],[2],{(11,U)})
        f.assert_not_called();self.assertFalse(r[2])
    def test_poststart_no_http(self):
        r,f,s=self.run_case([item(b'old')],[2],set(),clock=lambda:datetime(2026,11,28,4,tzinfo=timezone.utc))
        f.assert_not_called();self.assertFalse(r[2])
    def test_failure_retains_old(self):
        items=[item(b'old')];attempt=set();r,f,s=self.run_case(items,[1,2],attempt,fail=True)
        f.assert_called_once();s.assert_not_called();self.assertEqual(len(items),1);self.assertTrue(r[1]);self.assertFalse(r[2]);self.assertIn((11,U),attempt)
if __name__=='__main__':unittest.main()
