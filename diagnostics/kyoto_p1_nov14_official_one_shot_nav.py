"""Single bounded official *current* JRA entry selection discovery for Nov14.

Only one GET, no guessed per-race or SP CNAME, no odds, no real tickets.
If the currently observed official page does not publish a Kyoto Nov14 link,
record NOT_YET_VISIBLE rather than synthesize a racecard URL.
"""
from __future__ import annotations
import hashlib,json,re
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs,urlsplit
from urllib.request import Request,build_opener,HTTPRedirectHandler

SOURCE="https://jra.jp/JRADB/accessD.html?CNAME=pw01dli00%2FF3"
LIMIT=1_500_000
EXPECTED_DAY="20261114"
class DiscoveryRejected(ValueError):pass
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        raise DiscoveryRejected("any_redirect_disallowed")

class Selector(HTMLParser):
    def __init__(self):
        super().__init__();self.anchors=[];self.active=None;self.text=[];self.title=""
        self.in_title=False
    def handle_starttag(self,tag,attrs):
        if tag=="title":self.in_title=True
        if tag=="a":self.active={"attrs":dict(attrs),"text":""}
    def handle_data(self,data):
        if self.active is not None:self.active["text"]+=data
        if self.in_title:self.title+=data
    def handle_endtag(self,tag):
        if tag=="a" and self.active is not None:
            self.anchors.append(self.active);self.active=None
        if tag=="title":self.in_title=False

def strict_link_from_official(raw):
    if type(raw) is not bytes or not 0<len(raw)<=LIMIT:
        raise DiscoveryRejected("invalid_original_source")
    try:p=Selector();p.feed(raw.decode("cp932",errors="strict"))
    except UnicodeError as e:raise DiscoveryRejected("source_encoding_invalid") from e
    links=[]
    for a in p.anchors:
        href=a["attrs"].get("href","")
        text=" ".join(a["text"].split())
        if EXPECTED_DAY not in href or "京都" not in text:continue
        u=urlsplit(href)
        if (u.scheme or u.netloc or u.path!="/JRADB/accessD.html"
            or u.fragment or len(parse_qs(u.query).get("CNAME",[]))!=1
            or set(parse_qs(u.query))!={"CNAME"}):
            raise DiscoveryRejected("unofficial_meeting_link")
        cname=parse_qs(u.query)["CNAME"][0]
        if not re.fullmatch(r"pw[A-Za-z0-9]+/[A-Za-z0-9]+",cname):
            raise DiscoveryRejected("invalid_observed_meeting_token")
        links.append({"label":text,"href":href,
                     "source_observed_token_sha256":hashlib.sha256(cname.encode()).hexdigest()})
    if len(links)>1:raise DiscoveryRejected("ambiguous_current_kyoto_link")
    return {"status":"OFFICIAL_NOV14_KYOTO_MEETING_LINK_OBSERVED" if links else "NOT_YET_VISIBLE",
            "observed_links":links,"specific_racecard_url_verified":False,
            "smartphone_link_verified":False,"actual_prerace_odds_verified":False}

def inspect_once(directory,*,opener=None,clock=None):
    now=clock or (lambda:datetime.now(timezone.utc))
    destination=Path(directory)
    destination.mkdir(parents=True,exist_ok=True)
    started=now()
    receipt={"schema":"kyoto_jra_20261114_kyoto_navigation_one_off.v1",
             "origin":"JRA_OFFICIAL_PC_SELECTION","source_url":SOURCE,
             "started_utc":started.isoformat(),"attempted_GET":1,
             "no_repeat_polling":True,"status":"UNKNOWN_STOP",
             "current_meeting_racecards_verified":False,
             "current_prerace_market_verified":False,
             "paper_trade_authorized":False}
    try:
        client=opener if opener is not None else build_opener(NoRedirect())
        request=Request(SOURCE,method="GET",
                 headers={"User-Agent":"KyotoRaceAI-Private-ReadOnly/0.1",
                          "Accept":"text/html"})
        with client.open(request,timeout=12) as response:
            status=response.status
            ct=response.headers.get("Content-Type","")
            final=response.geturl()
            raw=response.read(LIMIT+1)
        if status!=200 or final!=SOURCE or "html" not in ct.lower() or not 0<len(raw)<=LIMIT:
            raise DiscoveryRejected("unverified_original_http_response")
        summary=strict_link_from_official(raw)
        (destination/"official_selection.html").write_bytes(raw)
        receipt.update(summary)
        receipt["source_sha256"]=hashlib.sha256(raw).hexdigest()
        receipt["source_bytes"]=len(raw)
        receipt["completed_utc"]=now().isoformat()
    except Exception as exc:
        receipt["status"]="FAILED_CLOSED"
        receipt["error_class"]=type(exc).__name__
        receipt["completed_utc"]=now().isoformat()
    (destination/"receipt.json").write_text(json.dumps(receipt,sort_keys=True,
            ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    return receipt
