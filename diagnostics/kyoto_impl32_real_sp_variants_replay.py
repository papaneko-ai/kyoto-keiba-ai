"""Read authenticated historical SP bytes only, no JRA HTTP or prediction promotion."""
import hashlib,json,os,tempfile,re
from pathlib import Path
from bs4 import BeautifulSoup
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence
from diagnostics.kyoto_impl31_sp_saved_roster_audit import exact_mobile_race,inspect_heading,inspect_observed_layout
from diagnostics.kyoto_weekend_sp_discovery import observed_kyoto_race_candidates
from urllib.parse import parse_qs,urlsplit
def main():
    day='20261122';out=Path('sp_real_variant_evidence');out.mkdir()
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)/'raw'
        decrypt_evidence(Path('sp_archive')/'encrypted',root,key_hex=os.environ['ARCHIVE_KEY'],repo=os.environ['GITHUB_REPOSITORY'],run_id='45558381201')
        receipt=json.loads((root/'receipt.json').read_text())
        assert receipt['day']==day and receipt['scope']=='HISTORICAL_AFTER_RACE_ONLY' and len(receipt['rows'])==12
        rows=[]
        for n,x in enumerate(receipt['rows'],1):
            assert x['race']==n and x['filename']==f'r{n:02d}_official_sp_racecard.html'
            raw=(root/x['filename']).read_bytes();assert hashlib.sha256(raw).hexdigest()==x['sha256']
            url=x['url'];assert exact_mobile_race(url,day,n)
            token=parse_qs(urlsplit(url).query)['CNAME'][0]
            try:t=raw.decode('utf8')
            except UnicodeError:t=raw.decode('cp932')
            soup=BeautifulSoup(t,'html.parser');table=soup.find('table')
            headings=[]
            for h in soup.find_all(['h1','h2','h3','h4','caption']):
                v=' '.join(h.stripped_strings)
                if not any(k in v for k in ('京都','出馬表','2026','頭')):continue
                # Only coarse flags; no raw page text or horse names published.
                headings.append({'tag':h.name,'classes':h.get('class',[]),'before_table':bool(table and any(e is h for e in table.previous_elements)),'date':bool(re.search(r'2026\s*年\s*11\s*月\s*22\s*日',v)),'kyoto':'京都' in v,'card':'出馬表' in v,'race':bool(re.search(r'(?<!\d)'+str(n)+r'\s*(?:R|レース)(?!\d)',v,re.I)),'counts':[int(y) for y in re.findall(r'(\d{1,2})\s*頭',v)]})
            nums=[];row_shapes={}
            if table:
                for tr in table.select('tr'):
                    a=tr.select('a[href*="/JRADB/accessU.html"]');ns=tr.select('.uban')
                    shape=f'links={len(a)};number={len(ns)};number_tags={sorted(x.name for x in ns)};direct_td_uban={sum(1 for c in tr.find_all("td",recursive=False) if "uban" in c.get("class",[]))}'
                    row_shapes[shape]=row_shapes.get(shape,0)+1
                    if len(a)==1 and len(ns)==1:
                        v=ns[0].get_text(' ',strip=True)
                        nums.append(v if v.isascii() and v.isdigit() or v=='取消' else 'OTHER')
            found=observed_kyoto_race_candidates(raw,url,day)
            row={'race':n,'prefix':token[7:9],'source_sha256':x['sha256'],'exact_url_accepted':True,'observed_anchor_counts':{k:len(v) for k,v in found.items()},'number_cells':nums,'row_shapes':row_shapes,'headings':headings}
            try:row['strict_roster_count']=len(inspect_heading(raw,day,n))
            except (ValueError,UnicodeError) as exc:row['strict_roster_error']=type(exc).__name__+':'+str(exc)[:80]
            try:row['split_layout']=inspect_observed_layout(raw,day,n)
            except (ValueError,UnicodeError) as exc:row['split_layout_error']=type(exc).__name__+':'+str(exc)[:80]
            rows.append(row)
        report={'day':day,'scope':'HISTORICAL_ONLY','exact_urls_accepted':len(rows),'source_archive_run_id':'45558381201','jra_http_requests':0,'live_acquisition_certified':False,'rows':rows}
        (out/'summary.json').write_text(json.dumps(report,sort_keys=True,indent=2));print('SP_REAL_VARIANTS='+json.dumps(report,sort_keys=True))
if __name__=='__main__':main()
