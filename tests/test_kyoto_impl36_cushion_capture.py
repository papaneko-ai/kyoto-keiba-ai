import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from diagnostics.kyoto_impl36_cushion_capture import capture,replay,ORIGINAL,URL
from diagnostics.kyoto_nov15_encrypted_evidence import encrypt_evidence,decrypt_evidence

DAY="20261128"
BEFORE="2026-11-28T00:31:00+00:00"
AFTER="2026-11-28T00:31:01+00:00"
REPO="papaneko-ai/kyoto-keiba-ai"
KEY="11"*32
RAW='<div id="cushion_data_list"><div id="rcZ" title="京都"><div class="unit"><div class="time">11月28日（土曜）7時00分</div><div class="cushion">9.5</div></div></div></div>'.encode("cp932")

class Runtime(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/"raw"
    def cap(self,raw=RAW):
        f=Mock(return_value=raw)
        r=capture(self.root,DAY,f,Mock(side_effect=[BEFORE,AFTER]))
        f.assert_called_once_with(URL)
        return r
    def test_capture_and_replay(self):
        r=self.cap()
        self.assertEqual(r["state"],"OFFICIAL_ORIGINAL_PARSED")
        self.assertEqual(replay(self.root,DAY)["cushion_value"],"9.5")
        self.assertFalse(replay(self.root,DAY)["prediction_ready"])
    def test_cutoff(self):
        self.cap();self.assertIsNone(replay(self.root,DAY,AFTER))
        self.assertIsNone(replay(self.root,DAY,BEFORE))
        self.assertIsNotNone(replay(self.root,DAY,"2026-11-28T00:31:02Z"))
    def test_raw_saved_when_unparseable(self):
        r=self.cap(b"<html>no measurement</html>")
        self.assertEqual(r["state"],"RAW_SAVED_NOT_PARSED")
        self.assertTrue((self.root/ORIGINAL).is_file());self.assertIsNone(replay(self.root,DAY))
    def test_request_failure(self):
        f=Mock(side_effect=TimeoutError())
        r=capture(self.root,DAY,f,Mock(return_value=BEFORE))
        self.assertEqual(r["state"],"REQUEST_FAILED");f.assert_called_once_with(URL)
        self.assertFalse((self.root/ORIGINAL).exists())
    def test_wrong_day_no_request(self):
        f=Mock()
        with self.assertRaises(ValueError):capture(self.root,"20261129",f,Mock(return_value=BEFORE))
        f.assert_not_called()
    def test_tamper_original(self):
        self.cap();(self.root/ORIGINAL).write_bytes(RAW.replace(b"9.5",b"9.6"))
        self.assertIsNone(replay(self.root,DAY))
    def test_tamper_receipt(self):
        self.cap();p=self.root/"receipt.json";r=json.loads(p.read_text());r["observation"]["cushion_value"]="99";p.write_text(json.dumps(r))
        self.assertIsNone(replay(self.root,DAY))
    def test_mismatch_day(self):
        self.cap();self.assertIsNone(replay(self.root,"20261129"))
    def test_no_overwrite(self):
        self.cap();f=Mock()
        with self.assertRaises(ValueError):capture(self.root,DAY,f,Mock(return_value=BEFORE))
        f.assert_not_called()
    def test_clock_backwards_keeps_raw(self):
        r=capture(self.root,DAY,Mock(return_value=RAW),Mock(side_effect=[AFTER,BEFORE]))
        self.assertEqual(r["state"],"RAW_SAVED_NOT_PARSED");self.assertIsNone(replay(self.root,DAY))
    def test_encrypt_readback(self):
        self.cap()
        with patch("diagnostics.kyoto_nov15_encrypted_evidence.DAY",DAY):
            dest=self.base/"encrypted";out=self.base/"decoded"
            encrypt_evidence(self.root,dest,key_hex=KEY,repo=REPO,run_id="123")
            self.assertEqual({p.name for p in dest.iterdir()},{"manifest.json","originals.tar.gz.aesgcm"})
            decrypt_evidence(dest,out,key_hex=KEY,repo=REPO,run_id="123")
            self.assertEqual((out/ORIGINAL).read_bytes(),RAW)
            self.assertEqual(replay(out,DAY),replay(self.root,DAY))
            with self.assertRaises(ValueError):decrypt_evidence(dest,self.base/"wrong",key_hex=KEY,repo=REPO,run_id="124")
if __name__=="__main__":unittest.main()
