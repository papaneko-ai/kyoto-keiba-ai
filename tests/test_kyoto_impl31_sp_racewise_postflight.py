"""Regression for the live all12 prefix boundary, including encrypted replay."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_weekend_postflight import check_originals
from diagnostics.kyoto_weekend_day21_artifact_triage import assess_lane
from diagnostics import kyoto_nov15_encrypted_evidence as crypto
from diagnostics.kyoto_impl25_c12_all_runs_handoff import summarize,WEEKENDS
DAY='20261129'; STAMP='2026-11-29T02:00:00+00:00'; REPO='papaneko-ai/kyoto-keiba-ai'; KEY='ab'*32
class Racewise(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'raw';self.root.mkdir()
        raw=b'discovery'; name='official_sp_discovery_1.html';(self.root/name).write_bytes(raw)
        (self.root/'sp_discovery_receipt.json').write_text(json.dumps(dict(day=DAY,not_pc_derived=True,attempts=[dict(file=name,sha256=hashlib.sha256(raw).hexdigest(),captured_at_utc=STAMP)])))
        (self.root/'receipt.json').write_text(json.dumps(dict(day=DAY,channel='SP')))
    def race(self,n):
        prefix=f'r{n:02d}_';r=dict(day=DAY,channel='SP',race_number=n,local_target_race_key=f'KYOTO:{DAY}:{n:02d}',racecard_fetched=True)
        for name,key in [('racecard','racecard'),('quinella_odds','sp_quinella'),('bracket_quinella_odds','sp_bracket_quinella')]:
            raw=f'{n}:{name}'.encode();(self.root/(prefix+'official_sp_'+name+'.html')).write_bytes(raw)
            r[key+'_sha256']=hashlib.sha256(raw).hexdigest();r[key+'_captured_at_utc']=STAMP
        (self.root/(prefix+'sp_receipt.json')).write_text(json.dumps(r))
    def check(self):return check_originals(self.root,day=DAY,channel='SP')
    def test_all_12_originals_audited_without_market_or_prediction_claim(self):
        for n in range(1,13):self.race(n)
        result=self.check()
        self.assertEqual(len(result['source_rows']),37)
        self.assertEqual(sum(x['both_market_originals_verified_bytes'] for x in result['sp_race_integrity'].values()),12)
        self.assertTrue(result['source_verified']);self.assertFalse(result['both_markets_verified']);self.assertFalse(result['prediction_ready'])
    def test_bad_race_does_not_discard_other_originals(self):
        self.race(1);self.race(2);self.race(3)
        (self.root/'r02_official_sp_quinella_odds.html').write_bytes(b'tampered')
        result=self.check();self.assertEqual(result['state'],'SP_RACEWISE_PARTIAL_INTEGRITY');self.assertFalse(result['source_verified'])
        self.assertEqual(result['sp_race_integrity']['2']['state'],'RACE_ORIGINAL_REJECTED')
        self.assertEqual(result['sp_race_integrity']['1']['verified_files'],3);self.assertEqual(result['sp_race_integrity']['3']['verified_files'],3)
        self.assertEqual((self.root/'r02_official_sp_quinella_odds.html').read_bytes(),b'tampered')
        self.assertFalse(any(x['filename'].startswith('r02_') for x in result['source_rows']))
    def test_receipt_identity_timestamp_and_missing_original_rejected(self):
        for n in range(1,5):self.race(n)
        for n,key,val in [(1,'race_number',2),(2,'racecard_captured_at_utc','2026-11-28T02:00:00Z')]:
            p=self.root/f'r{n:02d}_sp_receipt.json';d=json.loads(p.read_text());d[key]=val;p.write_text(json.dumps(d))
        (self.root/'r03_sp_receipt.json').unlink();(self.root/'r04_official_sp_bracket_quinella_odds.html').unlink()
        r=self.check();self.assertFalse(r['source_verified']);self.assertTrue(all(r['sp_race_integrity'][str(n)]['state']=='RACE_ORIGINAL_REJECTED' for n in range(1,5)))
    def test_encrypted_reopen_and_handoff_keep_partial_result(self):
        self.race(1);self.race(2);(self.root/'r02_official_sp_quinella_odds.html').write_bytes(b'tampered')
        post=self.check();(self.root/'source_verification.json').write_text(json.dumps(post));out=self.root.parent/'sealed'
        with patch.object(crypto,'DAY',DAY):
            crypto.encrypt_evidence(self.root,out,key_hex=KEY,repo=REPO,run_id='42')
            result=assess_lane(out,day=DAY,channel='SP',key=KEY,repo=REPO,run_id='42')
        self.assertTrue(result['ciphertext_authenticated']);self.assertTrue(result['sp_racewise_partial_integrity']);self.assertEqual(result['sp_race_integrity']['1']['verified_files'],3)
        run=dict(id=42,name=WEEKENDS[DAY][0],created_at=STAMP,event='schedule',status='completed',conclusion='success')
        jobs=[dict(name='pc-originals-independent',conclusion='success',steps=[]),dict(name='sp-originals-independent',conclusion='success',steps=[])]
        report=summarize(DAY,[dict(run=run,jobs=jobs,artifacts=[],source_assessment={'SP':result})])
        self.assertEqual(report['scheduled_runs'][0]['lanes']['SP']['sp_race_integrity'],result['sp_race_integrity'])
        self.assertFalse(report['full_live_jra_coverage_proved'])
    def test_old_discovery_only_receipt_cannot_claim_new_race_bytes(self):
        legacy=self.check();self.race(1)
        (self.root/'source_verification.json').write_text(json.dumps(legacy));out=self.root.parent/'sealed'
        with patch.object(crypto,'DAY',DAY):
            crypto.encrypt_evidence(self.root,out,key_hex=KEY,repo=REPO,run_id='42')
            result=assess_lane(out,day=DAY,channel='SP',key=KEY,repo=REPO,run_id='42')
        self.assertEqual(result['state'],'SP_RACEWISE_POSTFLIGHT_MISMATCH');self.assertFalse(result['source_original_sha_utc_checked'])
from tests.test_kyoto_impl31_sp_saved_roster_audit import SPProof

if __name__=='__main__':unittest.main()
