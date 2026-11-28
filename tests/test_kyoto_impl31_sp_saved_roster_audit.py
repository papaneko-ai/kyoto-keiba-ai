import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from diagnostics.kyoto_impl31_sp_saved_roster_audit import assess,inspect_heading
DAY='20261128';STAMP='2026-11-28T01:00:00Z';SEED='https://sp.jra.jp/'
def link(n):return f'https://sp.jra.jp/JRADB/accessD.html?CNAME=sw01dde010820260506{n:02d}{DAY}%2FAA'
def raw(n,count=2,heading=None):
    h=heading or f'2026年11月28日 京都 {n}R 出馬表 {count}頭'
    return ('<html><h2>'+h+'</h2><table><tr><td class="wban">1</td><td class="uban">1</td><td><a href="/JRADB/accessU.html">馬A</a></td></tr><tr><td class="wban">2</td><td class="uban">2</td><td><a href="/JRADB/accessU.html">馬B</a></td></tr></table></html>').encode('cp932')
def sha(v):return hashlib.sha256(v).hexdigest()
class SPProof(unittest.TestCase):
    def setUp(self):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup);self.root=Path(td.name)
    def setup_sources(self,numbers=range(1,13)):
        b=(''.join(f'<a href="{link(n)}">京都 {n}R</a>' for n in numbers)).encode('cp932')
        f='official_sp_discovery_1.html';(self.root/f).write_bytes(b)
        (self.root/'sp_discovery_receipt.json').write_text(json.dumps({'day':DAY,'not_pc_derived':True,'attempts':[{'file':f,'url':SEED,'sha256':sha(b),'captured_at_utc':STAMP}]}))
        for n in numbers:
            b=raw(n);prefix=f'r{n:02d}_';(self.root/(prefix+'official_sp_racecard.html')).write_bytes(b)
            (self.root/(prefix+'sp_receipt.json')).write_text(json.dumps({'day':DAY,'channel':'SP','race_number':n,'local_target_race_key':f'KYOTO:{DAY}:{n:02d}','observed_sp_source_url':link(n),'racecard_fetched':True,'racecard_sha256':sha(b),'racecard_captured_at_utc':STAMP}))
    def test_full_structural_not_live_proof(self):
        self.setup_sources()
        with patch('socket.socket.connect',side_effect=AssertionError('no network')):
            a=assess(self.root,DAY)
        self.assertEqual(a['structural_roster_races'],12);self.assertTrue(a['all12_structural_rosters_observed']);self.assertFalse(a['live_acquisition_certified']);self.assertEqual(a,assess(self.root,DAY))
    def test_optional_discovery_links_are_byte_verified_not_pc_derived(self):
        from diagnostics.kyoto_weekend_postflight import check_originals
        from diagnostics.kyoto_impl31_sp_saved_roster_audit import assess_checked
        self.setup_sources([1,2]);links={}
        post=check_originals(self.root,day=DAY,channel="SP")
        normal=assess_checked(self.root,DAY,post,observed_links=links)
        self.assertEqual(normal,assess(self.root,DAY))
        self.assertEqual(set(links),{"1","2"});self.assertEqual(set(links["1"]),{link(1)})
        p=self.root/"official_sp_discovery_1.html";p.write_bytes(p.read_bytes()+b"x")
        invalid={};assess_checked(self.root,DAY,check_originals(self.root,day=DAY,channel="SP"),observed_links=invalid)
        self.assertEqual(invalid,{})
    def test_partial_and_hash_mismatch(self):
        self.setup_sources([1,2]);p=self.root/'r02_official_sp_racecard.html';p.write_bytes(p.read_bytes()+b'x');a=assess(self.root,DAY);self.assertEqual(a['structural_roster_races'],1)
    def test_encrypted_reopen_preserves_independent_structural_audit(self):
        from diagnostics.kyoto_weekend_postflight import check_originals
        from diagnostics.kyoto_weekend_day21_artifact_triage import assess_lane
        from diagnostics import kyoto_nov15_encrypted_evidence as crypto
        self.setup_sources([1,2]);(self.root/'receipt.json').write_text(json.dumps({'day':DAY,'channel':'SP'}))
        (self.root/'source_verification.json').write_text(json.dumps(check_originals(self.root,day=DAY,channel='SP')))
        with tempfile.TemporaryDirectory() as td,patch.object(crypto,'DAY',DAY):
            out=Path(td)/'sealed';key='ab'*32;repo='papaneko-ai/kyoto-keiba-ai'
            crypto.encrypt_evidence(self.root,out,key_hex=key,repo=repo,run_id='42')
            r=assess_lane(out,day=DAY,channel='SP',key=key,repo=repo,run_id='42')
        self.assertTrue(r['ciphertext_authenticated']);self.assertEqual(r['sp_saved_roster_audit']['structural_roster_races'],2);self.assertFalse(r['official_live_market_accepted'])
    def test_wrong_anchor(self):
        self.setup_sources([1]);p=self.root/'r01_sp_receipt.json';d=json.loads(p.read_text());d['observed_sp_source_url']=link(2);p.write_text(json.dumps(d));self.assertEqual(assess(self.root,DAY)['structural_roster_races'],0)
    def test_later_anchor_cannot_prove_earlier_card(self):
        self.setup_sources([1]);p=self.root/'sp_discovery_receipt.json';d=json.loads(p.read_text());d['attempts'][0]['captured_at_utc']='2026-11-28T01:02:00Z';p.write_text(json.dumps(d));self.assertEqual(assess(self.root,DAY)['structural_roster_races'],0)
    def test_identity_and_count(self):
        for h in ('2026年11月28日 東京 1R 出馬表 2頭','2026年11月29日 京都 1R 出馬表 2頭','2026年11月28日 京都 2R 出馬表 2頭','2026年11月28日 京都 1R 出馬表 3頭'):
            with self.subTest(h=h),self.assertRaises(ValueError):inspect_heading(raw(1,heading=h),DAY,1)
    def test_no_title_inferred_from_body(self):
        b=raw(1).replace(b'<h2>',b'<div>').replace(b'</h2>',b'</div>')
        with self.assertRaises(ValueError):inspect_heading(b,DAY,1)
if __name__=='__main__':unittest.main()
