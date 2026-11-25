"""Offline cross-check of new SP twelve-original archive against prior PC twelve originals.
Historical data only; no JRA network, no production activation.
"""
import hashlib,io,json,os,re,tarfile,tempfile
from pathlib import Path
from datetime import datetime,timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from bs4 import BeautifulSoup
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
from diagnostics.kyoto_g03_all_races import parse
from diagnostics.kyoto_impl32_historical_sp12 import inspect,URLS,sha
from diagnostics.jra_pc_sp_benchmark import sp_rows
DAY='20261122'
def decode(raw):
    try:t=raw.decode('utf8')
    except UnicodeError:t=raw.decode('cp932')
    c=t.encode('cp932')
    if c.decode('cp932')!=t:raise ValueError('lossy')
    return c,t
def compare(raw,expected):
    c,t=decode(raw)
    try:rows=sp_rows(c)
    except ValueError:
        # A literal cancellation in the number cell is not a number. Retain
        # its name/frame and match a unique independently verified PC runner.
        # Do not guess a number by row position.
        soup=BeautifulSoup(t,'html.parser');table=soup.find('table')
        rows=[];frame=None;cancelled=[]
        for tr in table.select('tr'):
            a=tr.select('a[href*="/JRADB/accessU.html"]');ns=tr.select('.uban')
            if len(a)!=1 or len(ns)!=1:continue
            f=tr.select_one('.wban')
            if f and f.get_text(strip=True):
                v=f.get_text(strip=True)
                if not v.isascii() or not v.isdigit() or not 1<=int(v)<=8:raise ValueError('frame')
                frame=int(v)
            if frame is None:raise ValueError('frame_missing')
            name=a[0].get_text(' ',strip=True);v=ns[0].get_text(' ',strip=True)
            if v=='取消':
                choices=[n for n,fr,nm in expected if fr==frame and nm==name]
                if len(choices)!=1:raise ValueError('cancelled_identity_unverified')
                n=choices[0];cancelled.append(n)
            elif v.isascii() and v.isdigit() and 1<=int(v)<=18:n=int(v)
            else:raise ValueError('unexpected_number_cell')
            rows.append((n,frame,name))
        if not cancelled:raise ValueError('legacy_rejection_unexplained')
        if [r[0] for r in rows]!=list(range(1,len(rows)+1)):raise ValueError('sequence')
        return {'matched':tuple(rows)==tuple(expected),'sp_count':len(rows),'cancelled_pc_identity_matches':cancelled,'standalone_number_complete':False}
    return {'matched':rows==tuple(expected),'sp_count':len(rows),'cancelled_pc_identity_matches':[],'standalone_number_complete':True}
def main():
    repo=os.environ['GITHUB_REPOSITORY'];key=os.environ['ARCHIVE_KEY']
    pc=Path('pc_archive');blob=(pc/'originals_all12.tar.gz.aesgcm').read_bytes()
    assert sha(blob)==(pc/'ciphertext_sha256.txt').read_text().strip()
    tar=AESGCM(bytes.fromhex(key)).decrypt(blob[:12],blob[12:],b'kyoto-nov22-observed-official-all12-source-only')
    files={}
    with tarfile.open(fileobj=io.BytesIO(tar),mode='r:gz') as a:
        for m in a.getmembers():
            assert m.isfile() and m.name not in files and m.size<=1500000 and (m.name=='receipt.json' or re.fullmatch(r'r(0[1-9]|1[0-2])_(pc|sp)_official_racecard.html',m.name))
            files[m.name]=a.extractfile(m).read()
    old=json.loads(files['receipt.json'])
    rows={}
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)/'raw'
        decrypt_evidence(Path('sp_archive')/'encrypted',root,key_hex=key,repo=repo,run_id='45558381201')
        sp=json.loads((root/'receipt.json').read_text())
        assert sp['day']==DAY and sp['scope']=='HISTORICAL_AFTER_RACE_ONLY' and len(sp['rows'])==12
        for n,x in enumerate(sp['rows'],1):
            r={'race':n,'matched':False};rows[str(n)]=r
            try:
                assert x['race']==n and x['url']==URLS[n-1] and x['state']=='RAW_SAVED'
                s=(root/x['filename']).read_bytes();assert sha(s)==x['sha256'];inspect(s,n)
                now=datetime.fromisoformat(x['captured_at_utc']);assert now.utcoffset()==timezone.utc.utcoffset(None) and now.strftime('%Y%m%d')=='20261125'
                v=old['races'][str(n)]['PC'];p=files[f'r{n:02d}_pc_official_racecard.html'];assert sha(p)==v['sha256']
                parsed=parse(p,DAY,n,v['observed_official_url'],v['captured_at_utc'])
                expected=tuple((h['number'],h['frame'],h['name']) for h in parsed['runners'])
                r.update(pc_count=len(expected),pc_sha256=sha(p),sp_sha256=sha(s),sp_captured_at_utc=x['captured_at_utc'],**compare(s,expected))
            except Exception as exc:r['error_class']=type(exc).__name__;r['error_reason']=str(exc)[:100] if isinstance(exc,ValueError) else ''
    result={'day':DAY,'sp_originals':12,'pc_originals':sum('pc_sha256' in x for x in rows.values()),'matched_races':sum(x['matched'] for x in rows.values()),'matched_horses':sum(x.get('sp_count',0) for x in rows.values() if x['matched']),'rows':rows,'historical_only':True,'prestart_certified':False,'live_acquisition_certified':False,'network_jra_requests':0}
    out=Path('sp12_parity');out.mkdir();(out/'summary.json').write_text(json.dumps(result,sort_keys=True,indent=2))
    print('SP12_PARITY='+json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
