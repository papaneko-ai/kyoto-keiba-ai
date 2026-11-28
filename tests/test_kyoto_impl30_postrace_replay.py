"""Offline cross-run correction replay from two independent saved original pages."""
import json,tempfile,unittest
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
from diagnostics.kyoto_impl30_postrace_day import collect_day
from diagnostics.kyoto_impl30_postrace_replay import saved_observations,replay_history
from tests.test_kyoto_impl30_final_reconcile import pages,ROSTER,DAY,START,STAMP
from tests.test_kyoto_impl30_postrace_day import SEED,RESULT_MENU,PAYOUT_MENU,MEETING

def captured(root,*,price=400,stamp=STAMP,correction=False):
    a,b=pages(q=f'1-2 {price} 円',extra='訂正' if correction else '')
    def fetch(method,url,token):
        if token=='pw01sli00/AF':raw=RESULT_MENU
        elif token=='pw01hli00/03':raw=PAYOUT_MENU
        elif 'srl' in token:raw=MEETING
        elif 'hde' in token:raw=b
        else:
            race=int(token[-13:-11]);raw=a if race==1 else b'<html>not available</html>'
        return dict(raw=raw,captured_at_utc=stamp,requested_url=url,method=method,observed_action_token=token)
    roster={r:ROSTER for r in range(1,13)};starts={r:START for r in roster}
    out=collect_day(root,day=DAY,seed_raw=SEED,seed_sha256=sha256(SEED).hexdigest(),registered=roster,
        verified_starts=starts,fetch=fetch,clock=lambda:stamp,not_before_utc='2026-11-28T10:00:00Z')
    (root/'postrace_seed.html').write_bytes(SEED)
    return roster,starts,out

class ReplayTests(unittest.TestCase):
    def test_recompute_from_originals_and_reject_tampered_payload(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'first';roster,starts,out=captured(root)
            self.assertEqual(out['dual_page_explicit_final_races'],1)
            self.assertEqual(saved_observations(root,DAY,roster,starts)[1]['state'],'DUAL_PAGE_EXPLICIT_FINAL')
            path=root/'r01_result.html';path.write_bytes(path.read_bytes().replace(b'400',b'999'))
            self.assertEqual(saved_observations(root,DAY,roster,starts)[1]['state'],'PENDING')
    def test_two_run_correction_is_new_revision_but_prior_stays_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);first=root/'first';later=root/'later'
            roster,starts,_=captured(first)
            captured(later,price=500,stamp='2026-11-28T13:00:00Z',correction=True)
            before={f.name:sha256(f.read_bytes()).hexdigest() for f in first.iterdir()}
            with patch('diagnostics.kyoto_impl30_postrace_replay.prior_archives',return_value=iter([(101,first,None)])):
                report=replay_history(later,day=DAY,repo='papaneko-ai/kyoto-keiba-ai',key='a'*64,current_run='102',roster=roster,starts=starts)
            rows=report['races']['1']['revisions']
            self.assertEqual([r['version'] for r in rows],[1,2])
            self.assertEqual(rows[-1]['observation']['markets']['quinella']['payout_per_100'],{'1-2':500})
            self.assertFalse(report['settlement_authorized'])
            self.assertEqual(before,{f.name:sha256(f.read_bytes()).hexdigest() for f in first.iterdir()})
    def test_missing_prior_index_is_not_certified_complete(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'current';roster,starts,_=captured(root)
            with patch('diagnostics.kyoto_impl30_postrace_replay.prior_archives',side_effect=OSError):
                result=replay_history(root,day=DAY,repo='papaneko-ai/kyoto-keiba-ai',key='a'*64,current_run='102',roster=roster,starts=starts)
            self.assertFalse(result['prior_artifact_index_complete'])
            self.assertEqual(result['races']['1']['state'],'SOURCE_REVISION_CHAIN')
if __name__=='__main__':unittest.main()

class PriorNavigationFeedbackTests(unittest.TestCase):
    def test_authenticated_partial_navigation_is_replayable_without_result_credit(self):
        from tests.test_kyoto_impl30_postrace_day import a,h,S,H
        from diagnostics.kyoto_impl30_postrace_replay import saved_navigation_recovery
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'prior'
            # Reproduce the exact observed mode-01 layout with the old stop receipt.
            pm=h(a(H,'pw01hde01082026050720261128/AB','5回京都7日'))
            rm=RESULT_MENU
            meeting=h(''.join(a(S,f'pw01sde010820260507{n:02d}20261128/AA',f'{n}R') for n in range(1,13)))
            def fetch(method,url,token):
                data=rm if token=='pw01sli00/AF' else pm if token=='pw01hli00/03' else meeting
                return dict(raw=data,captured_at_utc=STAMP,requested_url=url,method=method,observed_action_token=token)
            from diagnostics.kyoto_impl30_postrace_day import select_navigation,PostraceRejected
            def legacy(raw,day,stage,**kw):
                action,proof=select_navigation(raw,day,stage,**kw)
                if proof['mode']=='01':raise PostraceRejected('missing_or_ambiguous_observed_navigation')
                return action,proof
            with patch('diagnostics.kyoto_impl30_postrace_day.select_navigation',side_effect=legacy):
                collect_day(root,day=DAY,seed_raw=SEED,seed_sha256=sha256(SEED).hexdigest(),registered={r:None for r in range(1,13)},fetch=fetch,clock=lambda:STAMP,not_before_utc='2026-11-28T10:00:00Z')
            (root/'postrace_seed.html').write_bytes(SEED)
            proof=saved_navigation_recovery(root,DAY)
            self.assertEqual(len(proof['recovery_candidates']),13)
            self.assertEqual(proof,saved_navigation_recovery(root,DAY))
            self.assertEqual(len(proof['missing_originals']),13)
            roster={r:ROSTER for r in range(1,13)};starts={r:START for r in roster}
            self.assertTrue(all(v['state']=='PENDING' for v in saved_observations(root,DAY,roster,starts).values()))
            current=Path(d)/'current';captured(current)
            with patch('diagnostics.kyoto_impl30_postrace_replay.prior_archives',return_value=iter([(101,root,None)])):
                history=replay_history(current,day=DAY,repo='papaneko-ai/kyoto-keiba-ai',key='a'*64,current_run='102',roster=roster,starts=starts)
            self.assertTrue(history['prior_artifact_index_complete'])
            self.assertEqual(len(history['races']['1']['revisions']),1)
            (root/'payout_menu.html').write_bytes(pm+b'x')
            with self.assertRaises(ValueError):saved_navigation_recovery(root,DAY)
