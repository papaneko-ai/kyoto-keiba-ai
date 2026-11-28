import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_weekend_capture import seal
from diagnostics import kyoto_nov15_encrypted_evidence as crypto
from diagnostics.kyoto_weekend_day21_artifact_triage import assess_lane
DAY="20261129";KEY="ab"*32;REPO="papaneko-ai/kyoto-keiba-ai"
class ArchiveSalvageTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);self.raw=self.root/"raw";self.raw.mkdir();self.out=self.root/"sealed"
  a=patch.dict(os.environ,{"KYOTO_TARGET_DAY":DAY});a.start();self.addCleanup(a.stop)
  a=patch.object(crypto,"DAY",DAY);a.start();self.addCleanup(a.stop)
 def put(self,name,raw):
  p=self.raw/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);return p
 def recover(self):
  r=seal(DAY,str(self.raw),str(self.out),key=KEY,repo=REPO,run_id="123",salvage_partial=True)
  self.assertTrue(r["roundtrip_verified"]);self.assertTrue(self.raw.is_dir())
  restored=self.root/"restore";crypto.decrypt_evidence(self.out,restored,key_hex=KEY,repo=REPO,run_id="123")
  return restored,json.loads((restored/"receipt.json").read_text())
 def test_unknown_file_no_longer_destroys_other_originals(self):
  self.put("official_meeting.html",b"actual meeting");self.put("receipt.json",b'{"day":"20261129"}')
  self.put("unseen-private.txt",b"secret not allowed")
  r,d=self.recover();self.assertEqual((r/"official_meeting.html").read_bytes(),b"actual meeting")
  self.assertEqual((r/"archive_pre_salvage_receipt.json").read_bytes(),b'{"day":"20261129"}')
  self.assertFalse((r/"unseen-private.txt").exists());self.assertFalse(d["prediction_ready"])
  self.assertEqual(len(d["rejected_members"]),1)
  a=assess_lane(self.out,day=DAY,channel="PC",key=KEY,repo=REPO,run_id="123")
  self.assertEqual(a["state"],"PARTIAL_ARCHIVE_SALVAGED_NOT_SOURCE_VERIFIED");self.assertFalse(a["source_original_sha_utc_checked"])
 def test_symlink_collision_and_independent_race(self):
  self.put("r01_official_sp_racecard.html",b"one")
  self.put("sp_stage_01/official_sp_racecard.html",b"conflicting")
  self.put("sp_stage_02/official_sp_racecard.html",b"two")
  (self.raw/"sp_stage_02"/"sp_receipt.json").symlink_to(self.raw/"r01_official_sp_racecard.html")
  r,d=self.recover();self.assertFalse((r/"r01_official_sp_racecard.html").exists())
  self.assertEqual((r/"r02_official_sp_racecard.html").read_bytes(),b"two")
  self.assertEqual(len(d["rejected_members"]),3)
 def test_nested_market_recovered_without_unknown_member(self):
  from diagnostics.kyoto_g06_nested_bundle import verify_bundle
  self.put("g06_unsealed/r01/pc/official_quinella_odds.html",b"odds")
  self.put("g06_unsealed/other/private.txt",b"not accepted")
  self.put("official_meeting.html",b"meeting")
  r,d=self.recover();self.assertEqual(verify_bundle(r/"g06_source_bundle.tar.gz")["verified_file_count"],2)
  self.assertEqual(len(d["rejected_members"]),1)
 def test_no_originals_is_not_success(self):
  self.put("unknown.txt",b"secret")
  with self.assertRaises(ValueError):self.recover()
  self.assertFalse(self.out.exists());self.assertTrue(self.raw.is_dir())
 def test_wrong_key_never_publish(self):
  self.put("official_meeting.html",b"meeting");self.put("unknown.txt",b"unknown")
  with self.assertRaises(ValueError):seal(DAY,str(self.raw),str(self.out),key="",repo=REPO,run_id="123",salvage_partial=True)
  self.assertFalse(self.out.exists())
if __name__=="__main__":unittest.main()
