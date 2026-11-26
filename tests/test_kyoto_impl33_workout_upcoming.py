import unittest
from diagnostics.kyoto_impl33_workout_upcoming import is_pre_day
class Upcoming(unittest.TestCase):
    def test_jst_boundary(self):
        self.assertTrue(is_pre_day('20261128','2026-11-27T14:59:59+00:00'))
        self.assertFalse(is_pre_day('20261128','2026-11-27T15:00:00+00:00'))
    def test_invalid_timezone(self):
        with self.assertRaises(ValueError):is_pre_day('20261128','2026-11-26T13:00:00+09:00')
if __name__=='__main__':unittest.main()
