"""Protect actual JRA horse name from suffix status misclassification."""
import unittest
from datetime import datetime,date,timezone
from diagnostics.jra_prior_form_offline import parse_horse_history
def raw(name):
    return ('<html><span class="txt"><span class="opt">競走馬情報</span>'
            +name+'</span><p>出走履歴</p></html>').encode('utf8')
def run(name,expected):
    return parse_horse_history(raw(name),
        source_url='https://jra.jp/JRADB/accessU.html?CNAME=pw0100000000/10',
        fetched_at_utc=datetime(2026,11,22,4,tzinfo=timezone.utc),
        prediction_cutoff_utc=datetime(2026,11,23,0,tzinfo=timezone.utc),
        target_date=date(2026,11,22),expected_horse_name=expected,
        allow_verified_no_history=True)
class Tests(unittest.TestCase):
    def test_one_approved_suffix(self):
        x=run('アメリカンステージ 放牧','アメリカンステージ')
        self.assertEqual(x['profile_horse_name'],'アメリカンステージ')
        self.assertEqual(x['official_status_annotation'],'放牧')
        self.assertFalse(x['prediction_ready'])
    def test_normal_name_kept(self):
        x=run('グランアレグリア','グランアレグリア')
        self.assertIsNone(x['official_status_annotation'])
    def test_unrelated_suffix_rejected(self):
        with self.assertRaisesRegex(ValueError,'profile_horse_name_mismatch'):
            run('アメリカンステージ 抹消','アメリカンステージ')
    def test_other_horse_cannot_impersonate(self):
        with self.assertRaisesRegex(ValueError,'profile_horse_name_mismatch'):
            run('別の馬 放牧','アメリカンステージ')
if __name__=='__main__':unittest.main()
