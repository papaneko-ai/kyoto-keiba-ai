import unittest
from unittest.mock import patch
from diagnostics.kyoto_impl33_workout_runtime import combine_primary,clock_variant_receipt
DAY='20261128';URL='https://white-green.jp/race/20261128-kyoto-09/'
R={'training_date':'2026-11-25','course':'RITTO_HILL','distance_m':800,'elapsed_s':54.0,'last_1f_s':12.0}
S=dict(R,elapsed_s=55.0)
O={'roster':{1:'A'},'start':'2026-11-28T05:30:00Z'}
def item(raw,stamp):return {'raw':raw,'stamp':stamp,'url':URL,'kind':'PRIMARY','race':9}
A=item(b'a','2026-11-26T01:00:00Z');B=item(b'b','2026-11-27T01:00:00Z')
class TestVariants(unittest.TestCase):
 def run_case(self,a,b,reverse=False):
    def bridge(raw,*args):
        return {'horses':{'1':{'state':'CANONICAL_RECORD_VALID'}}},b'',{1:a if raw==b'a' else b},[]
    with patch('diagnostics.kyoto_impl33_workout_runtime.bridge',side_effect=bridge):
        x={};items=[B,A] if reverse else [A,B]
        old=combine_primary(DAY,9,items,O)
        new=combine_primary(DAY,9,items,O,clock_observations=x)
        self.assertEqual(old,new)
        return new,clock_variant_receipt(x)
 def test_identical_capture_sets(self):
    result,groups=self.run_case([R,S],[R,S])
    self.assertEqual(len(result[0][1]),1);self.assertEqual(len(groups),1)
    self.assertFalse(groups[0]['capture_sets_differ'])
    self.assertEqual(len(groups[0]['variants']),2)
    self.assertEqual([len(v['source_proofs']) for v in groups[0]['variants']],[2,2])
 def test_differing_capture_sets(self):
    _,g=self.run_case([R],[S]);self.assertTrue(g[0]['capture_sets_differ'])
 def test_identical_record_no_variant(self):
    _,g=self.run_case([R],[R]);self.assertEqual(g,[])
 def test_determinism(self):
    self.assertEqual(self.run_case([R,S],[R,S]),self.run_case([R,S],[R,S],True))
 def test_new_group_without_same_key_not_variant(self):
    _,g=self.run_case([R],[R,dict(S,training_date='2026-11-26')]);self.assertEqual(g,[])
if __name__=='__main__':unittest.main()
