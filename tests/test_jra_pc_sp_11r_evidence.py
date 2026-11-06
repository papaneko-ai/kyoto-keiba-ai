"""Regression on independently captured JRA PC/SP Kyoto 11R evidence."""
from pathlib import Path
import json,unittest
ROOT=Path(__file__).resolve().parents[1]/'docs'/'diagnostics'
def sp():return json.loads((ROOT/'JRA_SP_RUNNER_PARITY_FIXED_20261106.json').read_text(encoding='utf8'))
def pc():return json.loads((ROOT/'remaining8_20261106'/'kyoto_11_snapshot.json').read_text(encoding='utf8'))
def carry_frames(rows):
 frames=[];last=None
 for r in rows:
  raw=r['frame_cell_text']
  if raw is not None:
   if not isinstance(raw,str) or not raw.isascii() or not raw.isdigit() or not 1<=int(raw)<=8:
    raise ValueError('invalid_frame')
   last=int(raw)
  if last is None:raise ValueError('first_frame_missing')
  frames.append(last)
 return frames
class TestOfficialSPvsPC(unittest.TestCase):
 def test_sixteen_runner_names(self):
  s=sp();p=pc()
  self.assertEqual(s['pc_runner_count'],16)
  self.assertEqual(s['sp_runner_candidate_count'],16)
  self.assertEqual(s['number_match_count'],16)
  self.assertEqual([r['name'] for r in s['sp_extracted_rows']],[r['horse_name'] for r in p['runners']])
 def test_frame_parity(self):
  self.assertEqual(carry_frames(sp()['sp_extracted_rows']),[r['frame_number'] for r in pc()['runners']])
 def test_profile_navigation_is_different(self):
  mobile=[r['profile_path'] for r in sp()['sp_extracted_rows']]
  desktop=[r['horse_profile_href'] for r in pc()['runners']]
  self.assertTrue(all(x.startswith('/JRADB/accessU.html?CNAME=') for x in mobile))
  self.assertTrue(all(a!=b for a,b in zip(mobile,desktop)))
 def test_frame_first_missing_fails_closed(self):
  x=[dict(sp()['sp_extracted_rows'][0])];x[0]['frame_cell_text']=None
  with self.assertRaises(ValueError):carry_frames(x)
 def test_repeated_frame_is_inherited(self):
  self.assertEqual(carry_frames([{'frame_cell_text':'2'},{'frame_cell_text':None}]),[2,2])
 def test_no_model_release(self):
  self.assertFalse(sp()['training_ready'])
  receipt=json.loads((ROOT/'JRA_SP_RUNNER_PARITY_FIXED_RECEIPT_20261106.json').read_text(encoding='utf8'))
  self.assertFalse(receipt['ready_for_prediction'])
if __name__=='__main__':unittest.main()
