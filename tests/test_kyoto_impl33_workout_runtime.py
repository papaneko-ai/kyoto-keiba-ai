import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch, Mock
import shutil
from diagnostics.kyoto_impl33_workout_runtime import gather_official,eligible_runs,OBSERVER,AUXILIARY,WORKFLOW,REPO
from tests.test_kyoto_impl30_postrace_runtime import inputs
from diagnostics.kyoto_nov15_encrypted_evidence import encrypt_evidence
import diagnostics.kyoto_nov15_encrypted_evidence as crypto
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
    def test_authenticated_auxiliary_roster_when_pc_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=inputs(root/'fixture',DAY);cipher=root/'cipher';key=b'a'*32
            (raw/'receipt.json').write_text(json.dumps({'day':DAY,'schema':'kyoto_impl30_auxiliary_refresh.v1'}))
            with patch.object(crypto,'DAY',DAY):encrypt_evidence(raw,cipher,key_hex=key.hex(),repo=REPO,run_id='201')
            def api(endpoint):
                self.assertIn('created=2026-11-28',endpoint)
                rows=[{'id':201,'status':'completed','head_branch':'main','head_repository':{'full_name':REPO},'path':'.github/workflows/'+AUXILIARY,'event':'workflow_dispatch','created_at':'2026-11-28T03:30:00Z'}] if AUXILIARY in endpoint else []
                return {'total_count':len(rows),'workflow_runs':rows}
            def download(rid,name,dest):
                self.assertEqual((rid,name),(201,'kyoto-auxiliary-201-20261128'))
                for f in cipher.iterdir():shutil.copyfile(f,dest/f.name)
            b=Mock();b.api.side_effect=api;b.download.side_effect=download
            with patch.object(crypto,'DAY',DAY):
                got,conflicts,issues=gather_official(DAY,key,b,aux_budget_factory=lambda:b)
                self.assertEqual(len(got),12);self.assertFalse(conflicts);self.assertFalse(issues)
                self.assertEqual(got[1]['source_lane'],'auxiliary');self.assertEqual(got[1]['run_id'],201)
                bad,_,issues=gather_official(DAY,b'b'*32,b,aux_budget_factory=lambda:b)
                self.assertEqual(bad,{});self.assertTrue(issues)
    def test_auxiliary_never_overwrites_pc_or_resolves_pc_conflict(self):
        b=Mock();b.download.return_value=None
        pc={'roster':{1:'A'},'start':'2026-11-28T01:00:00Z'};bad={'roster':{1:'B'},'start':pc['start']}
        r={'day':DAY,'schema':'kyoto_impl30_auxiliary_refresh.v1'}
        def dec(src,dst,**kw):dst.mkdir();(dst/'receipt.json').write_text(json.dumps(r))
        with patch('diagnostics.kyoto_impl33_workout_runtime.eligible_runs',side_effect=[[{'id':101},{'id':102}],[{'id':201}]]),patch('diagnostics.kyoto_impl33_workout_runtime.decrypt_evidence',side_effect=dec),patch('diagnostics.kyoto_impl33_workout_runtime.official',side_effect=[{1:pc,2:pc},{2:bad},{1:bad,2:bad,3:pc}]):
            found,conflicts,issues=gather_official(DAY,b'a'*32,b,aux_budget_factory=lambda:b)
            self.assertEqual(found[1],pc);self.assertNotIn(2,found);self.assertEqual(conflicts,[2]);self.assertEqual(found[3]['source_lane'],'auxiliary')
    def test_complete_pc_skips_auxiliary(self):
        b=Mock();factory=Mock()
        with patch('diagnostics.kyoto_impl33_workout_runtime.eligible_runs',return_value=[{'id':101}]),patch('diagnostics.kyoto_impl33_workout_runtime.decrypt_evidence'),patch('diagnostics.kyoto_impl33_workout_runtime.official',return_value={n:{} for n in range(1,13)}):
            found,_,_=gather_official(DAY,b'a'*32,b,aux_budget_factory=factory)
            self.assertEqual(len(found),12);factory.assert_not_called()
    def test_previous_workout_index_includes_pre_day(self):
        b=Mock();b.api.return_value={'total_count':0,'workflow_runs':[]};eligible_runs(b,DAY,WORKFLOW)
        self.assertIn('created=2026-11-27..2026-11-28',b.api.call_args.args[0])
    def test_index_checkpoint_precedes_discovery_no_extra_http(self):
        from diagnostics.kyoto_impl33_workout_runtime import append_primary_index,record_primary_discovery
        raw=b'<a href="/race/20261128-kyoto-09/">Kyoto 9R</a>'
        clock=lambda:datetime(2026,11,26,4,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp,patch('diagnostics.kyoto_impl33_workout_runtime.now',clock):
            out=Path(tmp);r={'day':DAY,'run_id':123,'snapshots':[]};key=b'a'*32;calls=[]
            def get(u):
                calls.append(u)
                return raw if u==PRIMARY_INDEX else sample()
            def discover_observer(races):
                self.assertTrue((out/'primary_index.aesgcm').exists())
                self.assertEqual(r['primary_index']['discovery_state'],'NOT_EVALUATED')
                record_primary_discovery(out,r,races)
            items,_,err=collect_primary(DAY,[],{},get,clock,
                on_index=lambda data,stamp:append_primary_index(out,r,key,data,stamp),
                on_discovery=discover_observer)
            self.assertEqual(len(calls),2);self.assertEqual(len(items),1);self.assertFalse(err)
            self.assertEqual(r['primary_index']['discovered_races'],[9])
            self.assertEqual(r['primary_index']['not_discovered_races'],[1,2,3,4,5,6,7,8,10,11,12])
            m=json.loads((out/'receipt.json').read_bytes())['primary_index']
            self.assertEqual(read_snapshot((out/m['filename']).read_bytes(),m,key,m['archive_aad'].encode()),raw)
            with self.assertRaises(ValueError):
                read_snapshot((out/m['filename']).read_bytes(),m,key,b'other-run')
    def test_index_original_survives_parser_exception(self):
        from diagnostics.kyoto_impl33_workout_runtime import append_primary_index
        clock=lambda:datetime(2026,11,26,4,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp,patch('diagnostics.kyoto_impl33_workout_runtime.now',clock),patch('diagnostics.kyoto_impl33_workout_runtime.discover',side_effect=ValueError):
            out=Path(tmp);r={'day':DAY,'run_id':123};key=b'a'*32;calls=[]
            def get(url):calls.append(url);return b'<html>new layout</html>'
            items,_,err=collect_primary(DAY,[],{},get,clock,on_index=lambda raw,stamp:append_primary_index(out,r,key,raw,stamp))
            self.assertEqual(calls,[PRIMARY_INDEX]);self.assertEqual(items,[])
            self.assertEqual(err,['INDEX_DISCOVERY:ValueError'])
            self.assertEqual(r['primary_index']['discovery_state'],'NOT_EVALUATED')
            self.assertTrue((out/'primary_index.aesgcm').exists())
    def test_index_seal_failure_does_not_stop_race_capture(self):
        clock=lambda:datetime(2026,11,26,4,tzinfo=timezone.utc)
        def get(url):return b'<a href="/race/20261128-kyoto-09/">Kyoto 9R</a>' if url==PRIMARY_INDEX else sample()
        def broken(*args):raise OSError()
        with patch('diagnostics.kyoto_impl33_workout_runtime.now',clock):
            items,_,err=collect_primary(DAY,[],{},get,clock,on_index=broken)
        self.assertEqual(len(items),1);self.assertIn('INDEX_ARCHIVE:OSError',err)
if __name__=='__main__':unittest.main()
