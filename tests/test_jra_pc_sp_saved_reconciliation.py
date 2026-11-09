"""Exercise existing PC and SP parsing paths with no network requests."""
import copy
import hashlib
import unittest
from diagnostics.jra_multi_capture_20261106 import parse
from diagnostics.jra_pc_sp_benchmark import reconcile_saved_racecards

DAY='2026-11-14'
BEFORE='2026-11-13T04:00:00Z'
NOW='2026-11-13T05:00:00Z'
CUTOFF='2026-11-14T04:50:00Z'


def pc_html(day='2026年11月14日', name2='B'):
    return f"""<html><body>{day} 1レース
    <table><tr><th class="horse"></th><th class="num"></th><th class="waku"></th></tr>
    <tr><td class="horse"><a href="/JRADB/accessU.html?CNAME=a">A</a></td>
    <td class="num">1</td><td class="waku"><img alt="枠1"></td>
    <td class="past">2026年11月1日</td></tr>
    <tr><td class="horse"><a href="/JRADB/accessU.html?CNAME=b">{name2}</a></td>
    <td class="num">2</td><td class="waku"><img alt="枠2"></td>
    <td class="past">2026年11月2日</td></tr>
    </table></body></html>""".encode('cp932')


def sp_html(name2='B'):
    return f"""<html><table>
    <tr><td class="uban">1</td><td class="wban">1</td>
    <td><a href="/JRADB/accessU.html?CNAME=a">A</a></td></tr>
    <tr><td class="uban">2</td><td class="wban">2</td>
    <td><a href="/JRADB/accessU.html?CNAME=b">{name2}</a></td></tr>
    </table></html>""".encode('cp932')


def source(raw):
    return {'raw':raw,'sha256':hashlib.sha256(raw).hexdigest(),
            'captured_utc':BEFORE}


def snapshot():
    return {'race_number':1,'race_date':DAY,'roster_verified':True,
            'runners':[{'horse_number':1,'frame_number':1,'horse_name':'A'},
                       {'horse_number':2,'frame_number':2,'horse_name':'B'}]}


def run(channels, *, reference=None, cutoff=CUTOFF, now=NOW):
    return reconcile_saved_racecards(channels,reference or snapshot(),
                                      meeting_date=DAY,race=1,
                                      cutoff_utc=cutoff,observed_utc=now)


class ExistingPCSPReuseTests(unittest.TestCase):
    def test_existing_pc_parser_dynamic_date(self):
        rows,errors=parse(pc_html(),1,meeting_date=DAY)
        self.assertEqual(errors,[])
        self.assertEqual([(x['horse_number'],x['frame_number'],x['horse_name']) for x in rows],
                         [(1,1,'A'),(2,2,'B')])

    def test_existing_pc_parser_old_fixed_date_still_works(self):
        rows,errors=parse(pc_html('2026年11月7日'),1)
        self.assertEqual(errors,[])
        self.assertEqual(len(rows),2)

    def test_future_date_not_accepted_as_historic(self):
        _,errors=parse(pc_html(),1)
        self.assertIn('date_not_confirmed',errors)

    def test_both_channels_match(self):
        r=run({'PC':source(pc_html()),'SP':source(sp_html())})
        self.assertEqual(r['selected_channel'],'PC')
        self.assertFalse(r['fallback_to_sp'])
        self.assertEqual(r['sources']['SP']['status'],'MATCH')
        self.assertFalse(r['predictions_authorized'])

    def test_pc_unavailable_sp_fallback(self):
        r=run({'SP':source(sp_html())})
        self.assertEqual(r['selected_channel'],'SP')
        self.assertTrue(r['fallback_to_sp'])
        self.assertEqual(r['sources']['PC']['status'],'UNAVAILABLE')

    def test_pc_parser_invalid_sp_fallback(self):
        r=run({'PC':source(b'broken html'),'SP':source(sp_html())})
        self.assertEqual(r['sources']['PC']['status'],'PARSER_FAILED')
        self.assertEqual(r['selected_channel'],'SP')

    def test_sp_mismatch_pc_valid(self):
        r=run({'PC':source(pc_html()),'SP':source(sp_html('WRONG'))})
        self.assertEqual(r['selected_channel'],'PC')
        self.assertEqual(r['sources']['SP']['status'],'ROSTER_MISMATCH')

    def test_both_invalid_no_selection(self):
        r=run({'PC':source(pc_html(name2='WRONG')),'SP':source(sp_html('WRONG'))})
        self.assertEqual(r['state'],'BLOCKED')
        self.assertIsNone(r['selected_channel'])

    def test_sha_mismatch_blocked(self):
        wrong=source(sp_html());wrong['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'source_sha_mismatch'):
            run({'SP':wrong})

    def test_cutoff_blocked(self):
        with self.assertRaisesRegex(ValueError,'cutoff_elapsed'):
            run({'SP':source(sp_html())},now='2026-11-14T04:51:00Z')

    def test_false_snapshot_identity_blocks(self):
        old=snapshot();old['race_date']='2026-11-07'
        with self.assertRaisesRegex(ValueError,'frozen_reference_mismatch'):
            run({'SP':source(sp_html())},reference=old)

    def test_source_after_observation_blocked(self):
        item=source(sp_html());item['captured_utc']='2026-11-13T06:00:00Z'
        with self.assertRaisesRegex(ValueError,'source_not_before_cutoff'):
            run({'SP':item})

    def test_three_replays_identical(self):
        first=run({'PC':source(pc_html()),'SP':source(sp_html())})
        for _ in range(3):
            self.assertEqual(run({'PC':source(pc_html()),'SP':source(sp_html())}),first)


if __name__=='__main__':
    unittest.main()
