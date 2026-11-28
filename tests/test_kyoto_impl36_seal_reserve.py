import re,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
import yaml
PATH=Path('.github/workflows/kyoto-20261128-29-two-source-production-observer.yml')
class Reserve(unittest.TestCase):
 def setUp(self):
    self.s=PATH.read_text();self.y=yaml.safe_load(self.s)
 def test_capture_bounded_and_seal_always(self):
    for lane,limit,joblimit in [('pc',1200,20),('sp',720,12)]:
       j=self.y['jobs'][lane+'-originals-independent']
       self.assertEqual(j['timeout-minutes'],joblimit)
       self.assertIn('KYOTO_JOB_START_SECONDS',j['steps'][0]['run'])
       cap=next(s for s in j['steps'] if '--channel '+lane.upper()+' --source '+lane+'_raw --destination '+lane+'_sealed' in s.get('run','') and '--seal-only' not in s.get('run',''))
       self.assertIn(f'{limit} - 120 - elapsed',cap['run'])
       self.assertIn('timeout --signal=TERM --kill-after=5s',cap['run'])
       self.assertNotIn('continue-on-error',cap)
       seal=next(s for s in j['steps'] if '--seal-only' in s.get('run',''))
       self.assertEqual(seal['if'],'always()')
       self.assertTrue(any(s.get('if')=='always()' and s.get('id')=='upload_'+lane+'_primary' for s in j['steps']))
 def test_unchanged_slots(self):
    self.assertEqual(re.findall(r"- cron: '([^']+)'",self.s),[])
    from tests.test_kyoto_impl39_native_isolation import diagnostic_crons
    self.assertEqual(diagnostic_crons()[:8],['15 0 28 11 *','15 1 28 11 *','5 2 28 11 *','50 2 28 11 *','15 0 29 11 *','15 1 29 11 *','10 2 29 11 *','55 2 29 11 *'])
    self.assertIn('needs: [select-collector, pc-originals-independent]',self.s)
    self.assertIn('cancel-in-progress: false',self.s)
 def test_actual_timeout_leaves_original_and_exit(self):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
       p=Path(d)/'original'
       r=subprocess.run(['timeout','--signal=TERM','--kill-after=5s','1s','bash','-c','printf original > "$1"; sleep 20','bash',str(p)])
       self.assertEqual(r.returncode,124)
       self.assertEqual(p.read_bytes(),b'original')
 def test_budget_examples(self):
    for limit in (1200,720):
       for elapsed in (0,30,90,limit-120,limit):
          r=subprocess.check_output(['bash','-c',f'elapsed={elapsed}; remaining=$(( {limit} - 120 - elapsed )); if (( remaining < 1 )); then remaining=1; fi; echo "$remaining"'],text=True)
          self.assertEqual(int(r),max(1,limit-120-elapsed))
if __name__=='__main__':unittest.main()
