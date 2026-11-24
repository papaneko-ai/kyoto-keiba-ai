import tempfile,unittest
from pathlib import Path
from diagnostics.kyoto_impl30_final_reconcile import reconcile,append_revision,FinalEvidenceRejected
DAY='20261128';START='2026-11-28T05:00:00Z';STAMP='2026-11-28T12:00:00Z'
ROSTER=((1,1,'甲馬'),(2,2,'乙馬'),(3,2,'丙馬'))
def html(s):return ('<html>'+s+'</html>').encode('cp932')
def pages(places=('1','2','3'),q='1-2 400 円',b='1-2 300 円',extra='',status='結果 確定'):
    rows=''.join(f'<tr><td class="place">{place}</td><td class="waku"><img alt="枠{f}"></td><td class="num">{n}</td><td class="horse"><a href="/JRADB/accessU.html?CNAME=horse{n}">{name}</a></td></tr>' for (n,f,name),place in zip(ROSTER,places))
    block=f' {status} 払戻金 単勝 1 100 円 複勝 1 100 円 枠連 {b} ワイド 1-2 100 円 馬連 {q} 馬単 1-2 500 円 {extra} '
    result=html(f'<h1>2026年11月28日 京都 1R レース結果</h1><table><tr><th class="place">着順</th><th class="waku">枠</th><th class="num">馬番</th><th class="horse">馬名</th></tr>{rows}</table><p>{block}</p>')
    payout=html(f'<h1>2026年11月28日 京都 払戻金一覧</h1><h2>1R</h2><p>{block}</p><h2>2R</h2><p>その他</p>')
    return result,payout

def run(a,b,stamp=STAMP):
    return reconcile(result_raw=a,payout_raw=b,day=DAY,race=1,registered=ROSTER,result_url='https://jra.jp/JRADB/accessS.html',result_utc=stamp,payout_utc=stamp,start_utc=START)

class Tests(unittest.TestCase):
    def test_normal_and_preliminary(self):
        self.assertEqual(run(*pages())['state'],'DUAL_PAGE_EXPLICIT_FINAL')
        self.assertEqual(run(*pages(status='速報'))['state'],'DUAL_PAGE_MATCH_FINALITY_UNPROVEN')
    def test_dead_heat_second_and_first(self):
        r=run(*pages(places=('1','2','2'),q='1-2 400 円 1-3 500 円'))
        self.assertEqual(r['markets']['quinella']['payout_per_100'],{'1-2':400,'1-3':500})
        self.assertEqual(r['markets']['bracket_quinella']['payout_per_100'],{'1-2':300})
        self.assertEqual(run(*pages(places=('1','1','3')))['state'],'DUAL_PAGE_EXPLICIT_FINAL')
    def test_cancel_refund_and_unknown(self):
        self.assertEqual(run(*pages(places=('1','2','取消'),extra='返還 馬連: 1-3 2-3 '))['markets']['quinella']['refunded_pairs'],[[1,3],[2,3]])
        with self.assertRaises(FinalEvidenceRejected):run(*pages(places=('1','2','取消')))
        with self.assertRaises(FinalEvidenceRejected):run(*pages(extra='返還馬番 3'))
    def test_mismatch_and_duplicate(self):
        a,b=pages()
        with self.assertRaises(FinalEvidenceRejected):run(a,b.replace(b'400',b'500'))
        with self.assertRaises(FinalEvidenceRejected):run(a,a)
        with self.assertRaises(FinalEvidenceRejected):run(a,b.replace(b'2R',b'1R'))
        with self.assertRaises(FinalEvidenceRejected):run(a,b.replace('京都'.encode('cp932'),'東京'.encode('cp932')))
    def test_correction_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=run(*pages());p=Path(tmp)/'journal'
            self.assertEqual(append_revision(p,r)['version'],1)
            self.assertEqual(append_revision(p,r)['state'],'UNCHANGED')
            with self.assertRaises(FinalEvidenceRejected):append_revision(p,run(*pages(q='1-2 500 円'),stamp='2026-11-28T12:10:00Z'))
            updated=run(*pages(q='1-2 500 円',extra='訂正'),stamp='2026-11-28T12:10:00Z')
            self.assertEqual(append_revision(p,updated)['version'],2)
            self.assertEqual(append_revision(p,updated)['state'],'UNCHANGED')
            f=p/'revision-0001.json';f.write_bytes(f.read_bytes().replace(b'400',b'999'))
            with self.assertRaises(FinalEvidenceRejected):append_revision(p,updated)
if __name__=='__main__':unittest.main()
