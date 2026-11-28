import unittest,tempfile
from pathlib import Path
from hashlib import sha256
from diagnostics.kyoto_impl30_postrace_day import collect_day,parse_result,PostraceRejected
DAY='20261128';STAMP='2026-11-28T12:00:00Z';ROSTER=((1,1,'甲馬'),(2,2,'乙馬'))
def h(s):return ('<html>'+s+'</html>').encode('cp932')
def a(p,t,l):return f'<a onclick="return doAction(\'{p}\',\'{t}\')">{l}</a>'
S='/JRADB/accessS.html';H='/JRADB/accessH.html'
SEED=h(a(S,'pw01sli00/AF','レース結果')+a(H,'pw01hli00/03','払戻金'))
RESULT_MENU=h(a(S,'pw01srl00082026050720261128/AA','5回京都7日'))
PAYOUT_MENU=h(a(H,'pw01hde00082026050720261128/AB','5回京都7日'))
MEETING=h(''.join(a(S,f'pw01sde100820260507{r:02d}{DAY}/AA',str(r)+'R') for r in range(1,13)))
def result(r):
 rows=''.join(f'<tr><td class="place">{n}</td><td class="waku"><img alt="枠{f}"></td><td class="num">{n}</td><td class="horse"><a href="/JRADB/accessU.html?CNAME=horse{n}">{name}</a></td></tr>' for n,f,name in ROSTER)
 return h(f'<h1>2026年11月28日 5回京都7日 {r}レース レース結果</h1><table><tr><th class="place">着順</th><th class="waku">枠</th><th class="num">馬番</th><th class="horse">馬名</th></tr>{rows}</table><p>払戻金 単勝 1 100 円 複勝 1 100 円 枠連 1-2 300 円 1 番人気 ワイド 1-2 100 円 馬連 1-2 400 円 1 番人気 馬単 1-2 500 円</p>')
class Tests(unittest.TestCase):
 def test_full_day_and_failed_race_isolated(self):
  for failed in (None,5):
   with tempfile.TemporaryDirectory() as tmp:
    calls=[]
    def fetch(method,url,token):
     calls.append(token)
     if token=='pw01sli00/AF':raw=RESULT_MENU
     elif token=='pw01hli00/03':raw=PAYOUT_MENU
     elif 'srl' in token:raw=MEETING
     elif 'hde' in token:raw=h('払戻金一覧')
     else:
      r=int(token[-13:-11]);raw=result(r)
      if r==failed:raw=h('not published')
     return dict(raw=raw,captured_at_utc=STAMP,requested_url=url,method=method,observed_action_token=token)
    root=Path(tmp)/'new';out=collect_day(root,day=DAY,seed_raw=SEED,seed_sha256=sha256(SEED).hexdigest(),registered={r:ROSTER for r in range(1,13)},fetch=fetch,clock=lambda:STAMP,not_before_utc='2026-11-28T10:00:00Z')
    self.assertEqual(out['structured_result_payout_races'],12-(failed is not None));self.assertEqual(len(calls),16);self.assertEqual(out['confirmed_final_races'],0);self.assertFalse(out['settlement_authorized'])
    if failed:self.assertTrue((root/'r05_result.html').exists())
    self.assertTrue(all(x['race_number']==12 for x in out['races']['12']['rows']))
 def test_wrong_race_and_roster_rejected(self):
  with self.assertRaises(PostraceRejected):parse_result(result(11),day=DAY,race=1,url='https://jra.jp/JRADB/accessS.html',registered=ROSTER)
  with self.assertRaises(PostraceRejected):parse_result(result(1),day=DAY,race=1,url='https://jra.jp/JRADB/accessS.html',registered=((1,1,'違う馬'),ROSTER[1]))
 def test_conflicting_payout_not_certified(self):
  raw=result(1).replace(b'1-2 400',b'1-3 400');p=parse_result(raw,day=DAY,race=1,url='https://jra.jp/JRADB/accessS.html',registered=ROSTER)
  self.assertEqual(p['reason'],'PAYOUT_VS_PLACING_CONFLICT');self.assertFalse(p['settlement_authorized'])

 def test_public_origin_keeps_all_raw_results_without_registered_roster(self):
  with tempfile.TemporaryDirectory() as tmp:
   calls=[]
   def fetch(method,url,token):
    self.assertTrue(url.startswith('https://www.jra.go.jp/'))
    calls.append((method,url,token))
    if token=='pw01sli00/AF':raw=RESULT_MENU
    elif token=='pw01hli00/03':raw=PAYOUT_MENU
    elif 'srl' in token:raw=MEETING
    elif 'hde' in token:raw=h('払戻金一覧')
    else:raw=result(int(token[-13:-11]))
    return dict(raw=raw,captured_at_utc=STAMP,requested_url=url,method=method,observed_action_token=token)
   root=Path(tmp)/'source';out=collect_day(root,day=DAY,seed_raw=SEED,seed_sha256=sha256(SEED).hexdigest(),registered={r:None for r in range(1,13)},fetch=fetch,clock=lambda:STAMP,not_before_utc='2026-11-28T10:00:00Z',seed_origin='https://www.jra.go.jp')
   self.assertEqual(len(calls),16)
   self.assertEqual(out['seed_origin'],'https://www.jra.go.jp')
   self.assertEqual(out['structured_result_payout_races'],0)
   self.assertFalse(out['settlement_authorized'])
   self.assertTrue(all((root/f'r{r:02d}_result.html').is_file() for r in range(1,13)))
   self.assertTrue((root/'payout_meeting.html').is_file())

class ObservedModeRecoveryTests(unittest.TestCase):
 def test_actual_observed_token_shape_repairs_all12_on_both_days(self):
  from diagnostics.kyoto_impl30_postrace_day import select_navigation
  from urllib.parse import quote
  for day in ('20261128','20261129'):
   date=day[:4]+'-'+day[4:6]+'-'+day[6:];stamp=date+'T12:00:00Z';key='0507' if day.endswith('28') else '0508'
   label='5回京都7日' if day.endswith('28') else '5回京都8日'
   rm=h(a(S,'pw01srl00082026'+key+day+'/AA',label))
   pm=h(a(H,'pw01hde01082026'+key+day+'/AB',label))
   tokens={r:'pw01sde01082026'+key+f'{r:02d}'+day+'/AA' for r in range(1,13)}
   meeting=h(''.join(f'<a href="{S}?CNAME={quote(t,safe="")}">{r}R</a>' for r,t in tokens.items()))
   prior=[select_navigation(pm,day,'payout_meeting')[1],select_navigation(meeting,day,'result_race',race=1,meeting=key)[1]]
   with tempfile.TemporaryDirectory() as tmp:
    calls=[]
    def fetch(method,url,token):
     calls.append((method,url,token))
     if token=='pw01sli00/AF':raw=rm
     elif token=='pw01hli00/03':raw=pm
     elif 'srl' in token:raw=meeting
     elif 'hde' in token:raw=h('払戻金一覧')
     else:raw=h('raw result')
     return dict(raw=raw,captured_at_utc=stamp,requested_url=url,method=method,observed_action_token=token)
    out=collect_day(Path(tmp)/'new',day=day,seed_raw=SEED,seed_sha256=sha256(SEED).hexdigest(),registered={r:None for r in range(1,13)},fetch=fetch,clock=lambda:stamp,not_before_utc=date+'T10:00:00Z',prior_navigation=prior)
    self.assertEqual(len(calls),16);self.assertEqual(out['raw_result_races'],12);self.assertTrue(out['raw_payout_meeting_saved'])
    self.assertEqual(sum(p['rule']=='OBSERVED_MODE_01_RECOVERY' for p in out['navigation_recovery']),13)
    self.assertEqual(sum(p['prior_failure_revalidated'] for p in out['navigation_recovery']),13)
    self.assertEqual(out['confirmed_final_races'],0);self.assertFalse(out['settlement_authorized'])
    self.assertEqual([x[2] for x in calls if 'sde' in x[2]],list(tokens.values()))
 def test_adaptive_selector_rejects_wrong_day_venue_meeting_and_ambiguity(self):
  from diagnostics.kyoto_impl30_postrace_day import select_navigation
  token='pw01hde01082026050720261128/AB';label='5回京都7日'
  for raw in (h(a(H,token.replace('0108','0105'),label)),h(a(H,token.replace('20261128','20261129'),label)),h(a(H,token,'5回京都8日')),h(a(H,token.replace('0108','1108'),label)),h(a(H,token,label)+a(H,token.replace('0108','0008'),label))):
   with self.assertRaises(PostraceRejected):select_navigation(raw,DAY,'payout_meeting')
  for raw in (h(a(S,'pw01sde0108202605071120261128/AA','11R')),h(a(S,'pw01sde0108202605080120261128/AA','1R'))):
   with self.assertRaises(PostraceRejected):select_navigation(raw,DAY,'result_race',race=1,meeting='0507')
