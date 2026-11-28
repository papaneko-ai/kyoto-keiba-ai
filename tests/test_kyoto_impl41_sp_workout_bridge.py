import hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from diagnostics.kyoto_impl33_workout_runtime import read_sp_rosters,gather_official,Budget,REPO,SP_READER_SHA
DAY="20261129";STAMP="2026-11-29T01:00:00Z";KEY=b"a"*32
def seal(root,reader,rid):
    env={"PATH":os.environ.get("PATH",""),"PYTHONPATH":str(reader),"PYTHONUTF8":"1","KYOTO_TARGET_DAY":DAY,"ARCHIVE_KEY":KEY.hex()}
    cipher=root.parent/"cipher"
    script="import os,sys;from diagnostics.kyoto_nov15_encrypted_evidence import encrypt_evidence;encrypt_evidence(sys.argv[1],sys.argv[2],key_hex=os.environ['ARCHIVE_KEY'],repo='papaneko-ai/kyoto-keiba-ai',run_id=sys.argv[3])"
    subprocess.check_call([sys.executable,"-c",script,str(root),str(cipher),str(rid)],cwd=reader,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
    return cipher
def fixture(root,heading="2026年11月29日 京都 1R 出馬表 2頭 発走時刻：11時45分"):
    root.mkdir()
    url="https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde01082026050601"+DAY+"%2FAA"
    nav=f'<a href="{url}">京都 1R</a>'.encode("cp932")
    raw=('<html><h2>'+heading+'</h2><table><tr><td class="wban">1</td><td class="uban">1</td><td><a href="/JRADB/accessU.html">馬A</a></td></tr><tr><td class="wban">2</td><td class="uban">2</td><td><a href="/JRADB/accessU.html">馬B</a></td></tr></table></html>').encode("cp932")
    sha=lambda b:hashlib.sha256(b).hexdigest()
    (root/"official_sp_discovery_1.html").write_bytes(nav)
    (root/"sp_discovery_receipt.json").write_text(json.dumps({"day":DAY,"not_pc_derived":True,"attempts":[{"file":"official_sp_discovery_1.html","url":"https://sp.jra.jp/","sha256":sha(nav),"captured_at_utc":STAMP}]}))
    (root/"r01_official_sp_racecard.html").write_bytes(raw)
    (root/"r01_sp_receipt.json").write_text(json.dumps({"day":DAY,"channel":"SP","race_number":1,"local_target_race_key":f"KYOTO:{DAY}:01","observed_sp_source_url":url,"racecard_fetched":True,"racecard_sha256":sha(raw),"racecard_captured_at_utc":STAMP}))
    (root/"receipt.json").write_text(json.dumps({"day":DAY,"channel":"SP"}))
class SPWorkoutBridge(unittest.TestCase):
    def reader(self):
        return Path(os.environ["KYOTO_WORKOUT_SP_READER"]).resolve()
    def test_authenticated_prestart_and_reject_wrong_day_key_revision(self):
        reader=self.reader()
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/"raw";fixture(root);cipher=seal(root,reader,42)
            r=read_sp_rosters(cipher,DAY,42,KEY,Budget(35),reader)
            self.assertEqual(r[1]["roster"],{1:"馬A",2:"馬B"})
            self.assertEqual(r[1]["source_lane"],"sp")
            self.assertEqual(r[1]["start"],"2026-11-29T02:45:00+00:00")
            self.assertEqual(r,read_sp_rosters(cipher,DAY,42,KEY,Budget(35),reader))
            for day,rid,key in (("20261128",42,KEY),(DAY,43,KEY),(DAY,42,b"b"*32)):
                with self.assertRaises((ValueError,subprocess.CalledProcessError)):
                    read_sp_rosters(cipher,day,rid,key,Budget(35),reader)
            with patch("diagnostics.kyoto_impl33_workout_runtime.SP_READER_SHA","0"*40):
                with self.assertRaises(ValueError):read_sp_rosters(cipher,DAY,42,KEY,Budget(35),reader)
    def test_explicit_count_and_start_mandatory(self):
        reader=self.reader()
        for heading in ("2026年11月29日 京都 1R 出馬表 2頭","2026年11月29日 京都 1R 出馬表 3頭 発走時刻：11時45分","2026年11月29日 京都 1R 出馬表 2頭 発走時刻：10時00分","2026年11月29日 東京 1R 出馬表 2頭 発走時刻：11時45分"):
            with tempfile.TemporaryDirectory() as t:
                root=Path(t)/"raw";fixture(root,heading)
                self.assertEqual(read_sp_rosters(seal(root,reader,42),DAY,42,KEY,Budget(35),reader),{})
    def test_fills_only_missing_and_preserves_conflicts(self):
        primary=Mock();aux=Mock();factory=Mock(return_value=aux)
        pc={"roster":{1:"A"},"start":STAMP};conflict={"roster":{1:"B"},"start":STAMP}
        mobile={"roster":{1:"C"},"start":STAMP,"source_lane":"sp"}
        def dec(src,dst,**kw):dst.mkdir()
        with patch("diagnostics.kyoto_impl33_workout_runtime.eligible_runs",side_effect=[[{"id":101},{"id":102}],[]]),patch("diagnostics.kyoto_impl33_workout_runtime.decrypt_evidence",side_effect=dec),patch("diagnostics.kyoto_impl33_workout_runtime.official",side_effect=[{1:pc,2:pc},{2:conflict}]),patch("diagnostics.kyoto_impl33_workout_runtime.read_sp_rosters",side_effect=[{1:mobile,2:mobile,3:mobile,4:mobile},{3:{**mobile,"roster":{1:"D"}}}]) as r:
            found,conflicts,issues=gather_official(DAY,KEY,primary,aux_budget_factory=factory,sp_reader="reader")
        self.assertEqual(found,{1:pc,4:mobile});self.assertEqual(conflicts,[2,3]);self.assertFalse(issues)
        self.assertEqual(r.call_count,2)
        self.assertTrue(all(c.args[4] is aux for c in r.call_args_list))
        self.assertEqual(aux.download.call_count,2)
    def test_complete_pc_skips_sp_reader(self):
        p=Mock();f=Mock()
        with patch("diagnostics.kyoto_impl33_workout_runtime.eligible_runs",return_value=[{"id":101}]),patch("diagnostics.kyoto_impl33_workout_runtime.decrypt_evidence"),patch("diagnostics.kyoto_impl33_workout_runtime.official",return_value={n:{} for n in range(1,13)}),patch("diagnostics.kyoto_impl33_workout_runtime.read_sp_rosters") as r:
            found,_,_=gather_official(DAY,KEY,p,aux_budget_factory=f,sp_reader="reader")
        self.assertEqual(len(found),12);r.assert_not_called();f.assert_not_called()
