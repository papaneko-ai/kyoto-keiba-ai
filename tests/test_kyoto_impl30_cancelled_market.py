import unittest
from tests.test_jra_market_source_chain import html,Q,B,RUNNERS
from tests.test_kyoto_g03_all_races import card
from diagnostics.kyoto_impl30_cancelled_market import parse_current_market
from diagnostics.jra_odds_matrix_parser import OddsMatrixError

class Tests(unittest.TestCase):
 def test_cancelled_horse_and_same_frame_not_priced(self):
  roster=card(count=6,race=11,day='20261107').replace(b'>2</td>',b'>2</td>'+ '<td class="status">取消</td>'.encode('cp932'))
  q=''.join('<table class="basic narrow-xy umaren">'+str(i)+' '+ ' '.join(f'{j} '+('取消' if 2 in (i,j) else '3.0') for j in range(i+1,7))+'</table>' for i in range(1,6))
  kwargs=dict(racecard=roster,racecard_utc='2026-11-07T00:00:00Z',market_utc='2026-11-07T00:01:00Z',start_utc='2026-11-07T06:45:00Z',day='20261107',race=11)
  result,active=parse_current_market(html('馬連オッズ',q),'quinella',RUNNERS,**kwargs)
  self.assertEqual(result['pair_count'],10); self.assertEqual(result['cancelled_horses'],[2]);self.assertEqual(len(active),5)
  result,_=parse_current_market(html('枠連オッズ',B.replace('1 2.0','1 ---')),'bracket_quinella',RUNNERS,**kwargs)
  self.assertEqual(result['pair_count'],5)
  for wrong in (q.replace('2 取消','2 3.0',1),q.replace('3 3.0','3 取消',1)):
   with self.assertRaises(OddsMatrixError):parse_current_market(html('馬連オッズ',wrong),'quinella',RUNNERS,**kwargs)
  with self.assertRaises(OddsMatrixError):parse_current_market(html('馬連オッズ',q),'quinella',RUNNERS)
  with self.assertRaises(OddsMatrixError):parse_current_market(html('馬連オッズ',q),'quinella',RUNNERS,**{**kwargs,'racecard_utc':'2026-11-07T00:02:00Z'})

 def test_saved_market_and_downstream_cancellation_conflict(self):
  import json,tempfile
  from pathlib import Path
  from hashlib import sha256
  from tests.test_kyoto_g06_item_level_recovery import setup,SPEC,START
  from diagnostics.kyoto_g06_item_level_recovery import recover_saved_markets
  from diagnostics.kyoto_g06_downstream_intake import prepare_intake
  roster=card(count=6,race=11,day='20261107').replace(b'11R','11レース'.encode('cp932')).replace(b'>2</td>',b'>2</td>'+ '<td class="status">取消</td>'.encode('cp932'))
  q=''.join('<table class="basic narrow-xy umaren">'+str(i)+' '+ ' '.join(f'{j} '+('取消' if 2 in (i,j) else '3.0') for j in range(i+1,7))+'</table>' for i in range(1,6))
  def replace(directory,name,step,raw):
   (directory/name).write_bytes(raw);p=directory/'receipt.json';r=json.loads(p.read_text());meta=next(x for x in r['request_receipts'] if x['step']==step);meta.update(bytes=len(raw),sha256=sha256(raw).hexdigest());p.write_text(json.dumps(r))
  for conflict in (False,True):
   with tempfile.TemporaryDirectory() as d:
    root=Path(d);racedir=root/'r11';racedir.mkdir();setup(racedir,'PC',['quinella']);setup(racedir,'SP',['bracket_quinella'])
    replace(racedir/'pc','official_racecard.html','racecard',roster)
    replace(racedir/'pc','quinella_original.html','quinella',html('馬連オッズ',q))
    if not conflict:
     replace(racedir/'sp','official_racecard.html','racecard',roster)
     replace(racedir/'sp','bracket_quinella_original.html','bracket_quinella',html('枠連オッズ',B.replace('1 2.0','1 ---')))
    report=recover_saved_markets(racedir,race_spec=SPEC,active_runners=RUNNERS,verified_start_utc=START)
    self.assertEqual(report['both_markets_verified'],not conflict);self.assertEqual(report['cancellation_conflict'],conflict)
    records={r:None for r in range(1,13)};records[11]=dict(race_spec=SPEC,verified_start_utc=START,active_runners=RUNNERS,expected_named_runners=tuple((n,f,'競走馬'+str(n)) for n,f in RUNNERS),primary_channel='PC')
    (root/'g06_batch_receipt.json').write_text(json.dumps(dict(schema='kyoto_g06_all12_source_capture.v1',total_races=12,records=[dict(race=r) for r in range(1,13)])))
    intake=prepare_intake(root,records=records)
    self.assertEqual(intake['paired_source_races'],int(not conflict))
    self.assertEqual(intake['races'][10]['P4']['markets']['quinella']['cancelled_horses'],[2])

 def test_observed_number_replaced_by_cancellation_marker(self):
  from diagnostics.jra_multi_capture_20261106 import parse
  from diagnostics.jra_pc_sp_benchmark import sp_rows
  raw=card(count=6,race=11,day='20261129').replace(b'<td class="num">2</td>','<td class="num"><span class="cap">取消</span></td>'.encode('cp932'))
  rows,errors=parse(raw,11,meeting_date='2026-11-29')
  self.assertEqual(errors,[])
  self.assertEqual([r['horse_number'] for r in rows],list(range(1,7)))
  self.assertEqual(rows[1]['number_evidence'],'ORDERED_REGISTERED_ROW_POSITION')
  self.assertTrue(rows[1]['cancelled'])
  malformed=raw.replace(b'<td class="num">3</td>',b'<td class="num">4</td>')
  self.assertIn('cancellation_position_not_verified',parse(malformed,11,meeting_date='2026-11-29')[1])
  mobile=('<table>'+''.join('<tr><td class="wban">'+str((n+1)//2)+'</td><td class="uban'+(' keshi' if n==2 else '')+'">'+('取消' if n==2 else str(n))+'</td><td><a href="/JRADB/accessU.html?CNAME=x">競走馬'+str(n)+'</a></td></tr>' for n in range(1,7))+'</table>').encode('cp932')
  self.assertEqual(sp_rows(mobile),tuple((r['horse_number'],r['frame_number'],r['horse_name']) for r in rows))
  with self.assertRaises(ValueError):sp_rows(mobile.replace(b'uban keshi',b'uban'))
  q=''.join('<table class="basic narrow-xy umaren">'+str(i)+' '+' '.join(f'{j} '+('取消' if 2 in (i,j) else '3.0') for j in range(i+1,7))+'</table>' for i in range(1,6))
  result,active=parse_current_market(html('馬連オッズ',q),'quinella',RUNNERS,racecard=raw,racecard_utc='2026-11-29T00:00:00Z',market_utc='2026-11-29T00:01:00Z',start_utc='2026-11-29T06:45:00Z',day='20261129',race=11)
  self.assertEqual(result['cancelled_horses'],[2])
  self.assertEqual(len(active),5)
