import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone
from diagnostics.kyoto_impl33_workout_runtime import roster_union,unique_snapshots,combine_primary,collect_primary,source_record,secondary_record,race_labels,PRIMARY_INDEX,append_snapshot,read_snapshot,partial_fields
from test_kyoto_impl33_workout_generic import sample,DAY,URL
class Runtime(unittest.TestCase):
    def test_roster_conflict_isolated(self):
        a={'roster':{1:'A',2:'B'},'start':'s'};b={'roster':{1:'A',2:'C'},'start':'s'};found={1:a,2:a};conflicts=set()
        roster_union(found,{1:b,3:a},conflicts);roster_union(found,{1:a},conflicts)
        self.assertEqual(set(found),{2,3});self.assertEqual(conflicts,{1})
    def test_preview_reused_earliest_identical(self):
        a=source_record(sample(),'2026-11-26T04:00:00Z',URL,'PRIMARY',9);b=dict(a,stamp='2026-11-27T04:00:00+00:00')
        self.assertEqual(unique_snapshots([b,a]),[a])
    def test_join_preview_without_fake_numbers(self):
        a=source_record(sample(),'2026-11-26T04:00:00Z',URL,'PRIMARY',9)
        o={'roster':{2:'A',5:'B'},'start':'2026-11-28T04:00:00Z'}
        v,p,i=combine_primary(DAY,9,[a],o);self.assertEqual(set(v),{2,5});self.assertEqual(sum(map(len,v.values())),2);self.assertEqual(len(p[2]),1)
    def test_late_not_promoted(self):
        a=source_record(sample(),'2026-11-26T04:00:00Z',URL,'PRIMARY',9);a['stamp']='2026-11-28T04:01:00Z'
        o={'roster':{2:'A',5:'B'},'start':'2026-11-28T04:00:00Z'}
        v,_,_=combine_primary(DAY,9,[a],o);self.assertEqual(sum(map(len,v.values())),0)
    def test_capture_independent_of_roster(self):
        calls=[]
        def get(u):
            calls.append(u)
            if u==PRIMARY_INDEX:return '<a href="/race/20261128-kyoto-09/">京都9R 栂尾特別20頭</a>'.encode()
            return sample()
        clock=lambda:datetime(2026,11,26,4,tzinfo=timezone.utc)
        with patch('diagnostics.kyoto_impl33_workout_runtime.now',clock):
            items,labels,err=collect_primary(DAY,[],{},get,clock)
        self.assertEqual(len(items),1);self.assertEqual(labels,{9:'栂尾特別'});self.assertEqual(len(calls),2);self.assertFalse(err)
    def test_secondary_after_start_excluded(self):
        x={'stamp':'2026-11-28T04:01:00Z','url':'https://umasiru.com/a','raw':b'x'}
        self.assertIsNone(secondary_record(x,'A',DAY,'2026-11-28T04:00:00Z'))
    def test_checkpoint_recoverable_and_idempotent(self):
        a=source_record(sample(),'2026-11-26T04:00:00Z',URL,'PRIMARY',9)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);r={'day':DAY,'run_id':123,'snapshots':[]};key=b'a'*32
            append_snapshot(out,r,key,a);append_snapshot(out,r,key,a)
            stored=json.loads((out/'receipt.json').read_text());self.assertEqual(len(stored['snapshots']),1)
            m=stored['snapshots'][0];self.assertEqual(read_snapshot((out/'source_000.aesgcm').read_bytes(),m,key,m['archive_aad'].encode()),a['raw'])
    def test_secondary_bad_page_not_fatal(self):
        x={'stamp':'2026-11-26T04:00:00Z','url':'https://umasiru.com/a','raw':b'x'}
        with patch('diagnostics.kyoto_impl33_workout_runtime.parse_table_v3',side_effect=ValueError):
            self.assertIsNone(secondary_record(x,'A',DAY,'2026-11-28T04:00:00Z'))
if __name__=='__main__':unittest.main()
