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
# JRA FAQ: ordinary unnumbered entries announced Thursday after 16:00 JST.
# Allow an additional 15 minutes for the official site to update.
MIN_DISCOVERY_UTC=datetime(2026,11,12,7,15,tzinfo=timezone.utc)
# Must agree with the race-day HTTP gate's exclusive upper bound.
# Prior recorded Nov14 attempt stays independently blocked by workflow guard.
MAX_DISCOVERY_UTC=datetime(2026,11,14,9,0,tzinfo=timezone.utc)
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

def inspect_once(directory,*,opener=None,clock=None,authorized_live_http=False):
    now=clock or (lambda:datetime.now(timezone.utc))
    destination=Path(directory)
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise DiscoveryRejected("evidence_folder_invalid")
    if destination.exists() and any(destination.iterdir()):
        raise DiscoveryRejected("one_shot_existing_evidence_must_not_be_overwritten")
    destination.mkdir(parents=True,exist_ok=True)
    started=now()
    if started.tzinfo is None or started.utcoffset() is None:
        raise DiscoveryRejected("utc_clock_required")
    started=started.astimezone(timezone.utc)
    receipt={"schema":"kyoto_jra_20261114_kyoto_navigation_one_off.v1",
             "origin":"JRA_OFFICIAL_PC_SELECTION","source_url":SOURCE,
             "started_utc":started.isoformat(),"attempted_GET":0,
             "no_repeat_polling":True,"status":"UNKNOWN_STOP",
             "current_meeting_racecards_verified":False,
             "current_prerace_market_verified":False,
             "paper_trade_authorized":False}
    if started<MIN_DISCOVERY_UTC:
        receipt["status"]="WAIT_FOR_JRA_OFFICIAL_PUBLICATION_NO_HTTP"
        receipt["publication_gate"]="JRA_THURSDAY_16_00_JST_PLUS_15MIN"
    elif started>=MAX_DISCOVERY_UTC:
        receipt["status"]="STALE_MEETING_DISCOVERY_NO_HTTP"
    elif opener is None and authorized_live_http is not True:
        receipt["status"]="LIVE_HTTP_NOT_EXPLICITLY_AUTHORIZED"
    else:
        receipt["attempted_GET"]=1
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
            # Preserve exact original before charset, HTML parser and anchor checks.
            # Never discard a real valid-response original merely because parsing fails.
            receipt["source_sha256"]=hashlib.sha256(raw).hexdigest()
            receipt["source_bytes"]=len(raw)
            receipt["source_captured_utc"]=now().isoformat()
            try:
                with (destination/"official_selection.html").open("xb") as original:
                    original.write(raw)
            except FileExistsError as exc:
                raise DiscoveryRejected("one_shot_original_already_exists") from exc
            if hashlib.sha256((destination/"official_selection.html").read_bytes()).hexdigest()!=receipt["source_sha256"]:
                raise DiscoveryRejected("one_shot_original_write_corrupted")
            summary=strict_link_from_official(raw)
            receipt.update(summary)
            receipt["completed_utc"]=now().isoformat()
        except Exception as exc:
            receipt["status"]="FAILED_CLOSED"
            receipt["error_class"]=type(exc).__name__
            if isinstance(exc,DiscoveryRejected):
                category=str(exc)
                if category in {
                    "any_redirect_disallowed","unverified_original_http_response",
                    "invalid_original_source","source_encoding_invalid",
                    "unofficial_meeting_link","invalid_observed_meeting_token",
                    "ambiguous_current_kyoto_link"}:
                    receipt["safe_error_code"]=category
            receipt["completed_utc"]=now().isoformat()
    encoded=json.dumps(receipt,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
    try:
        with (destination/"receipt.json").open("x",encoding="utf8") as output:
            output.write(encoded)
    except FileExistsError as exc:
        raise DiscoveryRejected("one_shot_receipt_already_exists") from exc
    return receipt
