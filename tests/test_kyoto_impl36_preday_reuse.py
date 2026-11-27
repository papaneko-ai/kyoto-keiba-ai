import unittest,json,tempfile,shutil
from pathlib import Path
from unittest.mock import Mock
from diagnostics.kyoto_impl33_workout_runtime import preday_saved,PREDAY_RUN,PREDAY_HEAD,PREDAY_WORKFLOW,REPO,append_snapshot
DAY='20261128'
KEY=b'a'*32
class Reuse(unittest.TestCase):
 def setUp(self):
    self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
    self.root=Path(self.tmp.name)
    self.report={'day':DAY,'run_id':PREDAY_RUN,'jra_requests':0,'production_coverage_authorized':False,'status':'SOURCE_ONLY_FINISHED','snapshots':[]}
    self.item={'race':9,'kind':'PRIMARY','url':'https://white-green.jp/race/20261128-kyoto-09/','stamp':'2026-11-27T05:46:10Z','raw':b'original'}
    append_snapshot(self.root,self.report,KEY,self.item)
    self.b=Mock()
    self.b.api.return_value={'id':PREDAY_RUN,'head_sha':PREDAY_HEAD,'path':PREDAY_WORKFLOW,'head_repository':{'full_name':REPO},'event':'push','status':'completed','conclusion':'success'}
    def copy(rid,name,dest):
        self.assertEqual(rid,PREDAY_RUN);self.assertEqual(name,f'impl36-preday-workout-{rid}-{DAY}')
        for p in self.root.iterdir():shutil.copy2(p,dest/p.name)
    self.b.download.side_effect=copy
 def test_original_reused(self):
    a=preday_saved(DAY,KEY,self.b);self.assertEqual(len(a),1);self.assertEqual(a[0]['raw'],b'original');self.assertEqual(a[0]['race'],9)
 def test_other_day_no_calls(self):
    self.assertEqual(preday_saved('20261129',KEY,self.b),[]);self.b.api.assert_not_called()
 def test_wrong_head_no_download(self):
    self.b.api.return_value['head_sha']='wrong';self.assertEqual(preday_saved(DAY,KEY,self.b),[]);self.b.download.assert_not_called()
 def test_bad_key(self):
    self.assertEqual(preday_saved(DAY,b'b'*32,self.b),[])
 def test_tamper(self):
    p=self.root/'source_000.aesgcm';p.write_bytes(p.read_bytes()+b'x');self.assertEqual(preday_saved(DAY,KEY,self.b),[])
 def test_download_failure(self):
    self.b.download.side_effect=TimeoutError();self.assertEqual(preday_saved(DAY,KEY,self.b),[])
if __name__=='__main__':unittest.main()
