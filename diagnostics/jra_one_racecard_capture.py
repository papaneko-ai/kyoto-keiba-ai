"""One GET of a known official JRA racecard; manual use only, never a pre-race certificate."""
import argparse,json
from datetime import datetime,timezone
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from urllib.request import Request,urlopen
MAX_BYTES=2_000_000

class PageSummary(HTMLParser):
    def __init__(self):
        super().__init__();self.title_depth=0;self.title='';self.tables=0
    def handle_starttag(self,tag,attrs):
        if tag=='title':self.title_depth+=1
        if tag=='table':self.tables+=1
    def handle_endtag(self,tag):
        if tag=='title':self.title_depth=max(0,self.title_depth-1)
    def handle_data(self,data):
        if self.title_depth:self.title+=data

def validate_url(url):
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname not in ('www.jra.go.jp','jra.go.jp') or p.username or p.password:
        raise ValueError('nonofficial_url')
    if p.path!='/JRADB/accessD.html' or len(parse_qs(p.query).get('CNAME',[]))!=1:
        raise ValueError('not_individual_racecard_url')
    return url

def capture(url,output,*,opener=urlopen,at=None):
    validate_url(url)
    at=at or (lambda: datetime.now(timezone.utc))
    req=Request(url,headers={'User-Agent':'KyotoRaceAI-Research/0.1','Accept':'text/html'},method='GET')
    with opener(req,timeout=15) as response:
        status=getattr(response,'status',200)
        final_url=response.geturl()
        if status!=200 or urlsplit(final_url).hostname not in ('www.jra.go.jp','jra.go.jp'):
            raise ValueError('http_or_redirect_error')
        raw=response.read(MAX_BYTES+1)
        ct=response.headers.get('Content-Type','')
    if not raw or len(raw)>MAX_BYTES or 'html' not in ct.lower():raise ValueError('not_bounded_html')
    p=PageSummary();p.feed(raw.decode('cp932',errors='replace'))
    if not p.title.strip() or p.tables<1:raise ValueError('missing_html_structure')
    stamp=at()
    if stamp.tzinfo is None:raise ValueError('clock_missing_timezone')
    folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
    (folder/'jra_racecard_response.html').write_bytes(raw)
    result={'schema_version':'jra_single_racecard_capture.v1',
            'source_url':url,'response_url':final_url,
            'fetched_at_utc':stamp.astimezone(timezone.utc).isoformat(),
            'source_sha256':sha256(raw).hexdigest(),'bytes':len(raw),'http_status':status,
            'html_title':p.title.strip(),'html_tables':p.tables,
            'raw_html_path':'jra_racecard_response.html',
            'official_racecard_roster_verified':False,
            'was_fetched_before_historical_race':False,
            'permanent_horse_ids_verified':False,
            'ready_for_prediction':False,'ready_for_training':False,
            'warning':'Current historical page cannot certify the prior cutoff snapshot.'}
    (folder/'capture_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--url',required=True);ap.add_argument('--out',default='jra_single_racecard_diagnostic')
    a=ap.parse_args()
    print(json.dumps(capture(a.url,a.out),ensure_ascii=False,indent=2))
