"""Strict offline binding of all three source HTML originals, no JRA network."""
import copy
import hashlib
import unittest
from pathlib import Path
from test_p1_three_original_dual_intake import ThreeOriginalIntakeTests, NOW
from diagnostics.jra_p1_offline_handoff import export_bundle
from diagnostics.p1_three_original_dual_intake import (
    inspect_three_original_dual_intake, ThreeOriginalRejected)


def market_html(label, css, rows, *, final=False):
    tables = ''.join('<table class="basic narrow-xy ' + css + '">' + x + '</table>' for x in rows)
    suffix = '最終オッズ' if final else ''
    return ('<html><title>' + label + ' JRA</title><body>' + suffix + tables +
            '</body></html>').encode('cp932')


class StrictThreeOriginalContentTests(unittest.TestCase):
    def setUp(self):
        ThreeOriginalIntakeTests.setUp(self)
        self.set_original(0, ('''<html><body>2026年11月14日 1レース
        <table><tr><th class="horse"></th><th class="num"></th><th class="waku"></th></tr>
        <tr><td class="horse"><a href="/JRADB/accessU.html?CNAME=a">A</a></td>
        <td class="num">1</td><td class="waku"><img alt="枠1"></td></tr>
        <tr><td class="horse"><a href="/JRADB/accessU.html?CNAME=b">B</a></td>
        <td class="num">2</td><td class="waku"><img alt="枠2"></td></tr>
        </table></body></html>''').encode('cp932'))
        self.set_original(1, market_html('馬連オッズ','umaren',['1 2 3.1']))
        self.set_original(2, market_html('枠連オッズ','waku',['1 7.2 2 4.1','2 5.0']))

    def set_original(self, i, raw):
        path = self.root / self.manifest['sources'][i]['path']
        path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        self.manifest['sources'][i]['sha256'] = digest
        key = ('racecard','odds','bracket_odds')[i]
        self.snapshot['sources'][key]['sha256'] = digest

    def inspect(self, snapshot=None, **kwargs):
        bundle = export_bundle(self.manifest,self.root,observed_utc=NOW)
        return inspect_three_original_dual_intake(
            bundle,snapshot or self.snapshot,observed_utc=NOW,
            racecard_channel='PC',verify_market_originals=True,**kwargs)

    def test_all_three_originals_match(self):
        result=self.inspect()
        self.assertTrue(result['racecard_roster_original_verified'])
        self.assertTrue(result['market_prices_original_verified'])
        self.assertEqual(result['market_original_receipts']['odds']['pair_count'],1)
        self.assertEqual(result['market_original_receipts']['bracket_odds']['pair_count'],3)
        self.assertFalse(result['prediction_ready'])
        self.assertFalse(result['official_origin_authenticated'])

    def test_fake_quinella_price_blocked(self):
        altered=copy.deepcopy(self.snapshot)
        altered['odds'][0]['decimal']=8.8
        with self.assertRaisesRegex(ThreeOriginalRejected,'odds_original_prices_disagree'):
            self.inspect(altered)

    def test_fake_bracket_price_blocked(self):
        altered=copy.deepcopy(self.snapshot)
        altered['bracket_odds'][0]['decimal']=9.9
        with self.assertRaisesRegex(ThreeOriginalRejected,'bracket_odds_original_prices_disagree'):
            self.inspect(altered)

    def test_historical_final_never_accepted(self):
        self.set_original(1,market_html('馬連オッズ','umaren',['1 2 3.1'],final=True))
        with self.assertRaisesRegex(ThreeOriginalRejected,'odds_historical_final_forbidden'):
            self.inspect()

    def test_missing_market_matrix_rejected(self):
        self.set_original(2,'<html><title>枠連オッズ</title></html>'.encode('cp932'))
        with self.assertRaisesRegex(ThreeOriginalRejected,'bracket_odds_original_parse_failed'):
            self.inspect()

    def test_no_strict_market_without_roster_parser(self):
        bundle=export_bundle(self.manifest,self.root,observed_utc=NOW)
        with self.assertRaisesRegex(ThreeOriginalRejected,'strict_markets_require_original_roster'):
            inspect_three_original_dual_intake(
                bundle,self.snapshot,observed_utc=NOW,verify_market_originals=True)

    def test_repeatable_three_source_receipt(self):
        self.assertEqual(self.inspect(),self.inspect())

    def test_original_market_sha_tampering_blocked(self):
        self.manifest['sources'][1]['sha256']='0'*64
        with self.assertRaises(ValueError):
            self.inspect()

if __name__=='__main__':
    unittest.main()
