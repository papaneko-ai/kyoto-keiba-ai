import json,shutil,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch,Mock
from urllib.error import HTTPError
from diagnostics.kyoto_impl30_postrace_runtime import recover_inputs,official_fetcher,auxiliary_inputs
from diagnostics.kyoto_impl30_postrace_day import collect_day
from diagnostics.kyoto_nov15_encrypted_evidence import encrypt_evidence,decrypt_evidence
import diagnostics.kyoto_nov15_encrypted_evidence as crypto
from diagnostics.kyoto_g03_all_races import acquire_all
from tests.test_kyoto_g03_all_races import meeting,source_race,PARENT,card
from tests.test_kyoto_impl30_postrace_day import SEED,RESULT_MENU,PAYOUT_MENU,MEETING,result,h
from hashlib import sha256
DAY='20261128';STAMP='2026-11-28T12:00:00Z';KEY='a'*64;REPO='papaneko-ai/kyoto-keiba-ai'
def inputs(root,day):
    root.mkdir();raw=root/'g03';saved=root/'saved';saved.mkdir()
    def fetch(url):
        return card(count=3,race=source_race(url),day=day).replace(b'</html>',SEED.replace(b'<html>',b''))
    report=acquire_all(day=day,root=raw,meeting_raw=meeting().replace(b'20261121',day.encode()),
        meeting_url=PARENT,fetch=fetch,captured_at_utc=lambda:day[:4]+'-'+day[4:6]+'-'+day[6:]+'T00:00:00Z',allowed=True)
    assert report['complete'], report
    for f in raw.iterdir():f.rename(saved/('g03_'+f.name))
    shutil.copyfile(saved/'g03_official_meeting.html',saved/'official_meeting.html')
    (saved/'g03_receipt.json').write_text(json.dumps(report))
    (saved/'receipt.json').write_text(json.dumps({'day':day}))
    return saved
class RuntimeTests(unittest.TestCase):
    def test_authenticated_seed_recovery_and_wrong_archive_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);saved=inputs(root/'fixture',DAY);cipher=root/'cipher'
            with patch.object(crypto,'DAY',DAY):
                encrypt_evidence(saved,cipher,key_hex=KEY,repo=REPO,run_id='101')
                run={'id':101,'name':'Kyoto Nov28-29 independent encrypted original collection','created_at':'2026-11-28T00:15:00Z','status':'completed','event':'schedule'}
                def api(endpoint):
                    if '/runs?' in endpoint:return {'total_count':1,'workflow_runs':[run]}
                    return {'total_count':1,'artifacts':[{'name':'kyoto-pc-101-20261128','expired':False}]}
                def download(rid,name,target,repo):
                    for f in cipher.iterdir():shutil.copyfile(f,target/f.name)
                with patch('diagnostics.kyoto_impl30_postrace_runtime._gh',side_effect=api),patch('diagnostics.kyoto_impl30_postrace_runtime._download',side_effect=download):
                    roster,starts,seed,proof=recover_inputs(DAY,REPO,KEY)
                    self.assertEqual(len(starts),12);self.assertEqual(len(roster[1]),3)
                    self.assertEqual(proof['sources']['1']['run_id'],101)
                    self.assertIn(b'doAction',seed)
                    roster2,starts2,seed2,proof2=recover_inputs(DAY,REPO,KEY,include_coverage=True)
                    self.assertEqual((roster,starts,seed),(roster2,starts2,seed2))
                    self.assertEqual(proof2["day_source_coverage"]["totals"]["racecards"],12)
                    self.assertEqual(proof2["day_source_coverage"]["totals"]["registered_horses_known"],36)
                    self.assertEqual(proof2["day_source_coverage"]["authenticated_pc_slots"],1)
                    self.assertFalse(proof2["day_source_coverage"]["full_data_acquisition_certified"])
                    with patch("diagnostics.kyoto_impl30_day_coverage.combine",side_effect=ValueError("diagnostic unavailable")):
                        rr,ss,seed3,proof3=recover_inputs(DAY,REPO,KEY,include_coverage=True)
                    self.assertEqual((rr,ss,seed3),(roster,starts,seed))
                    self.assertEqual(proof3["day_source_coverage_error"],"ValueError")
                    with patch('diagnostics.kyoto_impl30_postrace_runtime.auxiliary_inputs',return_value=({},None,{})):
                        with self.assertRaisesRegex(ValueError,'no_verified'):recover_inputs(DAY,REPO,'b'*64)
    def test_auxiliary_authenticated_originals_recover_postrace_when_pc_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);saved=inputs(root/'fixture',DAY);cipher=root/'cipher'
            (saved/'receipt.json').write_text(json.dumps({'day':DAY,'schema':'kyoto_impl30_auxiliary_refresh.v1'}))
            with patch.object(crypto,'DAY',DAY):
                encrypt_evidence(saved,cipher,key_hex=KEY,repo=REPO,run_id='201')
                run={'id':201,'name':'Kyoto Nov28-29 afternoon auxiliary refresh','created_at':'2026-11-28T03:30:00Z','status':'completed','event':'workflow_dispatch','head_branch':'main','head_repository':{'full_name':REPO},'path':'.github/workflows/kyoto-20261128-29-auxiliary-refresh.yml'}
                def api(endpoint):
                    if '/runs?' in endpoint:return {'total_count':1,'workflow_runs':[run]}
                    return {'total_count':1,'artifacts':[{'name':'kyoto-auxiliary-201-20261128','expired':False}]}
                def download(rid,name,target,repo):
                    self.assertEqual((rid,name,repo),(201,'kyoto-auxiliary-201-20261128',REPO))
                    for f in cipher.iterdir():shutil.copyfile(f,target/f.name)
                found,seed,proof=auxiliary_inputs(DAY,REPO,KEY,api=api,download=download)
                self.assertEqual(len(found),12);self.assertIn(b'doAction',seed)
                self.assertEqual(found[1]['source_lane'],'auxiliary');self.assertEqual(proof['examined_runs'],[201])
                with patch('diagnostics.kyoto_impl30_postrace_runtime._gh',side_effect=TimeoutError),patch('diagnostics.kyoto_impl30_postrace_runtime.auxiliary_inputs',return_value=(found,seed,proof)):
                    roster,starts,actual,report=recover_inputs(DAY,REPO,KEY)
                    self.assertEqual(len(starts),12);self.assertEqual(actual,seed)
                    self.assertEqual(report['sources']['1']['source_lane'],'auxiliary')
                    self.assertTrue(report['auxiliary_fallback']['attempted'])
                bad,none,_=auxiliary_inputs(DAY,REPO,'b'*64,api=api,download=download)
                self.assertEqual(bad,{});self.assertIsNone(none)
                for field,value in [('head_branch','not-main'),('created_at','2026-11-29T03:30:00Z'),('event','pull_request'),('head_repository',{'full_name':'other/repo'})]:
                    with self.subTest(field=field):
                        old=run[field];run[field]=value
                        mock=Mock();bad,none,_=auxiliary_inputs(DAY,REPO,KEY,api=api,download=mock)
                        self.assertEqual(bad,{});self.assertIsNone(none);mock.assert_not_called();run[field]=old
                bad,none,_=auxiliary_inputs(DAY,REPO,KEY,api=api,download=download,monotonic=Mock(side_effect=[0,91,91,91]))
                self.assertEqual(bad,{});self.assertIsNone(none)
    def test_auxiliary_fallback_never_overwrites_verified_pc(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);saved=inputs(root/'fixture',DAY);cipher=root/'cipher'
            receipt=json.loads((saved/'g03_receipt.json').read_text());receipt['races']['12']['state']='MISSING'
            (saved/'g03_receipt.json').write_text(json.dumps(receipt))
            with patch.object(crypto,'DAY',DAY):
                encrypt_evidence(saved,cipher,key_hex=KEY,repo=REPO,run_id='101')
                run={'id':101,'name':'Kyoto Nov28-29 independent encrypted original collection','created_at':'2026-11-28T00:15:00Z','status':'completed','event':'schedule'}
                def api(endpoint):
                    if '/runs?' in endpoint:return {'total_count':1,'workflow_runs':[run]}
                    return {'total_count':1,'artifacts':[{'name':'kyoto-pc-101-20261128','expired':False}]}
                def download(rid,name,target,repo):
                    for f in cipher.iterdir():shutil.copyfile(f,target/f.name)
                wrong={'named':((1,1,'WRONG'),),'start':'2026-11-28T04:00:00+00:00','run_id':201,'sha256':'a'*64,'source_lane':'auxiliary'}
                with patch('diagnostics.kyoto_impl30_postrace_runtime._gh',side_effect=api),patch('diagnostics.kyoto_impl30_postrace_runtime._download',side_effect=download),patch('diagnostics.kyoto_impl30_postrace_runtime.auxiliary_inputs',return_value=({1:wrong,12:wrong},b'aux seed',{})):
                    roster,starts,seed,proof=recover_inputs(DAY,REPO,KEY)
                    self.assertNotEqual(roster[1],wrong['named']);self.assertEqual(proof['sources']['1']['run_id'],101)
                    self.assertEqual(proof['sources']['12']['source_lane'],'auxiliary');self.assertIn(b'doAction',seed)
    def test_transport_refusal_stops_next_request_and_bad_targets_never_called(self):
        opener=Mock();pacer=Mock()
        fetch=official_fetcher(DAY,clock=lambda:datetime.fromisoformat(STAMP.replace('Z','+00:00')),opener=opener,pacer=pacer)
        with self.assertRaises(ValueError):fetch('POST','https://example.org/JRADB/accessS.html','pw01sli00/AF')
        opener.open.assert_not_called()
        opener.open.side_effect=HTTPError('https://jra.jp/JRADB/accessS.html',429,'refused',{},None)
        with self.assertRaises(HTTPError):fetch('POST','https://jra.jp/JRADB/accessS.html','pw01sli00/AF')
        with self.assertRaisesRegex(ValueError,'prior_access_refusal'):fetch('POST','https://jra.jp/JRADB/accessH.html','pw01hli00/03')
        self.assertEqual(opener.open.call_count,1)
    def test_exact_postrace_allowlist_and_authentication(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);raw=root/'raw';raw.mkdir()
            for name in ('receipt.json','results_menu.html','results_meeting.html','payout_menu.html','payout_meeting.html','postrace_seed.html','postrace_input_proof.json','r01_result.html','r12_result.html'):
                (raw/name).write_bytes(name.encode())
            with patch.object(crypto,'DAY',DAY):
                encrypt_evidence(raw,root/'sealed',key_hex=KEY,repo=REPO,run_id='102')
                decrypt_evidence(root/'sealed',root/'restored',key_hex=KEY,repo=REPO,run_id='102')
                self.assertEqual({f.name:f.read_bytes() for f in raw.iterdir()},{f.name:f.read_bytes() for f in (root/'restored').iterdir()})
                self.assertEqual({f.name for f in (root/'sealed').iterdir()},{'manifest.json','originals.tar.gz.aesgcm'})
                (raw/'r13_result.html').write_bytes(b'bad')
                with self.assertRaises(ValueError):encrypt_evidence(raw,root/'bad',key_hex=KEY,repo=REPO,run_id='103')
if __name__=='__main__':unittest.main()
