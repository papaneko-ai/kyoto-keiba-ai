import unittest
from diagnostics.kyoto_impl33_workout_missing import merge
def prior():
    return [{'race':n,'official_horses':12,'status':'UNVERIFIED' if n in (3,8,9,10) else 'HISTORICAL_BINDING_VERIFIED'} for n in range(1,13)]
class Missing(unittest.TestCase):
    def test_only_missing_replaced(self):
        p=prior();r={'race':3,'official_horses':12,'status':'HISTORICAL_BINDING_VERIFIED'}
        a=merge(p,[r]);self.assertEqual(a[2],r);self.assertEqual(a[0],p[0]);self.assertEqual(len(a),12)
    def test_no_replace_verified(self):
        p=prior()
        with self.assertRaises(ValueError):merge(p,[p[0]])
    def test_no_denominator_change(self):
        p=prior()
        with self.assertRaises(ValueError):merge(p,[dict(p[2],official_horses=11)])
    def test_no_duplicate_race(self):
        p=prior()
        with self.assertRaises(ValueError):merge(p,[p[2],p[2]])
if __name__=='__main__':unittest.main()
