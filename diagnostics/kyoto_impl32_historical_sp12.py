"""One isolated historical-only recovery of independently indexed official SP pages.
No synthetic CNAME, PC-derived URL, retry, odds request or live/prestart claim.
"""
import hashlib,json,os,re,tempfile,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import build_opener,HTTPCookieProcessor
from urllib.error import HTTPError,URLError
from http.cookiejar import CookieJar
from bs4 import BeautifulSoup
from diagnostics.kyoto_nov15_two_original_observer import _read,NoRedirect
from diagnostics.kyoto_nov15_encrypted_evidence import encrypt_evidence,decrypt_evidence,_key
from diagnostics.jra_pc_sp_benchmark import sp_rows
URLS=[
  "https://app.jra.jp/JRADB/accessD.html?CNAME=sw01dde1008202605060120261122%2F6F",
  "https://app.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605060220261122%2F45",
  "https://app.jra.jp/JRADB/accessD.html?CNAME=sw01dde1008202605060320261122%2FD9",
  "https://app.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605060420261122%2FAF",
  "https://app.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605060520261122%2F64",
  "https://app.jra.jp/JRADB/accessD.html?CNAME=sw01dde1008202605060620261122%2FF8",
  "https://app.jra.jp/JRADB/accessD.html?CNAME=sw01dde1008202605060720261122%2FAD",
  "https://app.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605060820261122%2F83",
  "https://app.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605060920261122%2F38",
  "https://app.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605061020261122%2F2D",
  "https://app.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605061120261122%2FE2",
  "https://app.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202605061220261122%2F97"
]
DAY='20261122'
def stamp():return datetime.now(timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,v):p.write_text(json.dumps(v,sort_keys=True,indent=2),encoding='utf8')
def inspect(raw,n):
    try:t=raw.decode('utf8')
    except UnicodeError:t=raw.decode('cp932')
    soup=BeautifulSoup(t,'html.parser')
    headings=[' '.join(h.stripped_strings) for h in soup.find_all(['h1','h2','h3','h4'])]
    date=any(re.search(r'2026\s*年\s*11\s*月\s*22\s*日',h) and '京都' in h for h in headings)
    race=any(re.search(r'(?<!\d)'+str(n)+r'\s*(?:R|レース)(?!\d)',h,re.I) for h in headings)
    if not date or not race:raise ValueError('heading_not_verified')
    result={'date_heading':True,'race_heading':True,'table_count':len(soup.find_all('table')),'legacy_roster_count':None}
    try:
        c=t.encode('cp932')
        if c.decode('cp932')!=t:raise ValueError('lossy')
        result['legacy_roster_count']=len(sp_rows(c))
    except (ValueError,UnicodeError):result['legacy_parser']='REJECTED'
    # No inference of registered counts or parity from a heading alone.
    return result
def collect(root,read,pace,clock=stamp):
    rows=[]
    for n,u in enumerate(URLS,1):
        x={'race':n,'url':u,'state':'NOT_ATTEMPTED'};rows.append(x)
        try:
            pace()
            x['requested_at_utc']=clock()
            raw=read(u)
            x['captured_at_utc']=clock()
            if not isinstance(raw,bytes) or not 0<len(raw)<=1500000:raise ValueError('bad_bytes')
            name=f'r{n:02d}_official_sp_racecard.html'
            (root/name).write_bytes(raw)
            x.update(state='RAW_SAVED',filename=name,sha256=sha(raw),bytes=len(raw))
            try:x.update(inspection=inspect(raw,n))
            except (ValueError,UnicodeError):x['inspection_error']='CONTENT_IDENTITY_UNVERIFIED'
        except HTTPError as e:
            x.update(state='HTTP_ERROR',code=e.code)
            if e.code in (401,403,429) or 300<=e.code<400:break
        except URLError as e:
            x.update(state='TRANSPORT_ERROR',error_class=type(e).__name__);break
        except (TimeoutError,OSError,ValueError) as e:
            x.update(state='REJECTED',error_class=type(e).__name__);break
    return {'day':DAY,'scope':'HISTORICAL_AFTER_RACE_ONLY','observed_url_count':12,'rows':rows,'prestart_certified':False,'live_acquisition_certified':False}
def main():
    if os.getenv('KYOTO_TARGET_DAY')!=DAY or datetime.now(timezone.utc).strftime('%Y%m%d')!='20261125' or os.getenv('GITHUB_EVENT_NAME')!='push' or os.getenv('GITHUB_REF')!='refs/heads/fix/impl32-historical-sp12-proof-20261125':raise ValueError('isolated_scope')
    key=os.environ.get('ARCHIVE_KEY','');_key(key)
    repo=os.environ['GITHUB_REPOSITORY'];rid=os.environ['GITHUB_RUN_ID']
    out=Path('impl32_historical_sp');out.mkdir()
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)/'raw';root.mkdir()
        opener=build_opener(NoRedirect(),HTTPCookieProcessor(CookieJar()))
        last=[None]
        def pace():
            if last[0] is not None:time.sleep(max(0,2-(time.monotonic()-last[0])))
            last[0]=time.monotonic()
        receipt=collect(root,lambda u:_read(opener,u),pace)
        write(root/'receipt.json',receipt)
        sealed=out/'encrypted';encrypt_evidence(root,sealed,key_hex=key,repo=repo,run_id=rid)
        decoded=Path(tmp)/'decoded';decrypt_evidence(sealed,decoded,key_hex=key,repo=repo,run_id=rid)
        saved=json.loads((decoded/'receipt.json').read_text())
        assert saved==receipt
        for r in saved['rows']:
            if r.get('filename'):assert sha((decoded/r['filename']).read_bytes())==r['sha256']
        summary={'scope':receipt['scope'],'race_day':DAY,'attempts':len(receipt['rows']),'originals_saved':sum(r['state']=='RAW_SAVED' for r in receipt['rows']),'verified_identity':sum('inspection' in r for r in receipt['rows']),'legacy_parser_success':sum(r.get('inspection',{}).get('legacy_roster_count') is not None for r in receipt['rows']),'rows':[{k:v for k,v in r.items() if k not in ('url','filename')} for r in receipt['rows']],'encrypted_readback_verified':True,'prestart_certified':False,'live_acquisition_certified':False}
        write(out/'summary.json',summary);print('HISTORICAL_SP_SUMMARY='+json.dumps(summary,sort_keys=True))
if __name__=='__main__':main()
