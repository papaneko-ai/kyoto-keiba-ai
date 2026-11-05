"""Follow exactly one Kyoto past-result link present in official results page."""
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urlencode,urljoin,urlsplit
from pathlib import Path
from hashlib import sha256
import json,re

OUT=Path("jra_action_capture")
SOURCE=OUT/"results.html"
URL="https://www.jra.go.jp/JRADB/accessS.html"

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.active=None
    def handle_starttag(self,tag,attrs):
        if tag=="a":self.active={"label":"","onclick":dict(attrs).get("onclick") or ""}
    def handle_data(self,data):
        if self.active is not None:self.active["label"]+=data
    def handle_endtag(self,tag):
        if tag=="a" and self.active is not None:
            self.active["label"]=" ".join(self.active["label"].split())
            self.links.append(self.active)
            self.active=None

def links_from(body):
    p=Links();p.feed(body.decode("cp932",errors="replace"));return p.links

def main():
    if not SOURCE.exists():
        raise FileNotFoundError("results.html unavailable")
    links=links_from(SOURCE.read_bytes())
    matches=[x for x in links if "京都" in x["label"] and "20261031" in x["onclick"]]
    report={"candidates":len(matches),"selected":None,"status":"not_attempted"}
    if len(matches)!=1:
        report["status"]="no_unique_official_kyoto_link"
    else:
        link=matches[0]
        m=re.search("doAction\\s*\\(\\s*'([^']+)'\\s*,\\s*'([^']+)'",link["onclick"])
        if not m:
            report["status"]="unknown_action"
        else:
            path,cname=m.groups()
            target=urljoin("https://www.jra.go.jp",path)
            if target!=URL:raise ValueError("unexpected_target")
            report["selected"]={"label":link["label"],"target":target}
            request=Request(target,data=urlencode({"cname":cname}).encode("ascii"),method="POST",headers={
                "User-Agent":"Mozilla/5.0","Referer":"https://www.jra.go.jp/keiba/",
                "Content-Type":"application/x-www-form-urlencoded","Accept":"text/html"})
            try:
                with urlopen(request,timeout=20) as resp:
                    body=resp.read(1500001)
                    if urlsplit(resp.geturl()).hostname not in ("www.jra.go.jp","jra.go.jp"):
                        raise ValueError("redirect")
                    if len(body)>1500000:raise ValueError("large_html")
                    report["http"]=resp.status
                (OUT/"kyoto_results_20261031.html").write_bytes(body)
                items=links_from(body)
                selected=[x for x in items if any(k in x["label"] for k in ("1R","2R","3R","4R","5R","6R","7R","8R","9R","10R","11R","12R","京都","レース"))]
                report.update(status="captured_html",bytes=len(body),sha256=sha256(body).hexdigest(),links_total=len(items),race_links=selected[:65])
            except Exception as exc:
                report.update(status="failed",error=type(exc).__name__ + ":" + str(exc)[:140])
    (OUT/"kyoto_result_follow.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("KYOTO_FOLLOW",json.dumps(report,ensure_ascii=False)[:16000])

if __name__=="__main__":main()
