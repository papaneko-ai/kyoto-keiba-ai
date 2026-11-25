import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_weekend_capture import seal
from diagnostics import kyoto_nov15_encrypted_evidence as crypto
from diagnostics.kyoto_g06_nested_bundle import verify_bundle
DAY='20261128';KEY='ab'*32;REPO='papaneko-ai/kyoto-keiba-ai'
class NestedSalvage(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup);self.base=Path(d.name)
        self.src=self.base/'raw';self.src.mkdir();self.dst=self.base/'sealed'
        p=patch.dict(os.environ,{'KYOTO_TARGET_DAY':DAY});p.start();self.addCleanup(p.stop)
        p=patch.object(crypto,'DAY',DAY);p.start();self.addCleanup(p.stop)
    def put(self,name,raw):
        p=self.src/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);return p
    def recover(self):
        seal(DAY,str(self.src),str(self.dst),key=KEY,repo=REPO,run_id='123')
        d=self.base/'decoded';crypto.decrypt_evidence(self.dst,d,key_hex=KEY,repo=REPO,run_id='123')
        return d
    def test_discovery_and_two_sp_stages(self):
        self.put('sp_discovery/official_sp_discovery_1.html',b'discovery')
        self.put('sp_stage_01/official_sp_racecard.html',b'one')
        self.put('sp_stage_12/official_sp_quinella_odds.html',b'twelve')
        d=self.recover()
        self.assertEqual((d/'official_sp_discovery_1.html').read_bytes(),b'discovery')
        self.assertEqual((d/'r01_official_sp_racecard.html').read_bytes(),b'one')
        self.assertEqual((d/'r12_official_sp_quinella_odds.html').read_bytes(),b'twelve')
        self.assertEqual(json.loads((d/'receipt.json').read_text())['actual_http_attempts'],'UNKNOWN')
    def test_interrupted_g06_and_pc_survive(self):
        self.put('g06_unsealed/r01/pc/official_quinella_odds.html',b'odds')
        self.put('pc_originals/official_meeting.html',b'meeting')
        d=self.recover()
        self.assertEqual(verify_bundle(d/'g06_source_bundle.tar.gz')['verified_file_count'],2)
        self.assertEqual((d/'official_meeting.html').read_bytes(),b'meeting')
        self.assertFalse(json.loads((d/'receipt.json').read_text())['prediction_ready'])
    def test_collision_detected_before_moving_any_stage(self):
        one=self.put('sp_stage_01/official_sp_racecard.html',b'one')
        two=self.put('sp_stage_02/official_sp_racecard.html',b'two')
        self.put('r02_official_sp_racecard.html',b'earlier')
        with self.assertRaisesRegex(ValueError,'collision'):self.recover()
        self.assertTrue(one.is_file());self.assertTrue(two.is_file());self.assertFalse(self.dst.exists())
    def test_unknown_nested_file_fail_closed(self):
        one=self.put('sp_stage_01/official_sp_racecard.html',b'one')
        self.put('sp_stage_02/private.txt',b'private')
        with self.assertRaises(ValueError):self.recover()
        self.assertTrue(one.is_file());self.assertFalse(self.dst.exists())
    def test_nested_symlink_rejected(self):
        one=self.put('sp_stage_01/official_sp_racecard.html',b'one')
        (one.parent/'sp_receipt.json').symlink_to(one)
        with self.assertRaises(ValueError):self.recover()
        self.assertTrue(one.is_file());self.assertFalse(self.dst.exists())
    def test_empty_stages_do_not_veto_existing_original(self):
        (self.src/'g06_unsealed').mkdir();(self.src/'sp_stage_01').mkdir()
        self.put('official_meeting.html',b'meeting')
        d=self.recover();self.assertEqual((d/'official_meeting.html').read_bytes(),b'meeting')
if __name__=='__main__':unittest.main()
