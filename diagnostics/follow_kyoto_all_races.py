"""Retrieve one official 'show all races' page for historic Kyoto meeting."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urlencode,urljoin,urlsplit
import json,re,hashlib
P=Path("jra_action_capture")
SOURCE=P/"kyoto_results_20261031.html"
class Anchors(HTMLParser):
    def __init__(self):super().__init__();self.items=[];self.cur=None
    def handle_starttag(self,tag,attrs):
        if tag=="a":self.cur={"text":"","onclick":dict(attrs).get("onclick") or ""}
    def handle_data(self,data):
        if self.cur is not None:self.cur["text"]+=data
    def handle_endtag(self,tag):
        if tag=="a" and self.cur is not None:
            self.cur["text"]=" ".join(self.cur["text"].split())
            self.items.append(self.cur);self.cur=None
def get_links(body):
    p=Anchors();p.feed(body.decode("cp932",errors="replace"));return p.items
def main():
    summary={"status":"not_attempted"}
    if not SOURCE.exists():raise FileNotFoundError(SOURCE)
    matched=[x for x in get_links(SOURCE.read_bytes()) if x["text"]=="全てのレースを表示"]
    if len(matched)!=1:
        summary.update(status="not_unique",matched=len(matched))
    else:
        m=re.search("doAction\\s*\\(\\s*'([^']+)'\\s*,\\s*'([^']+)'",matched[0]["onclick"])
        if not m:raise ValueError("unrecognized_JRA_action")
        path,cname=m.groups()
        url=urljoin("https://www.jra.go.jp/",path)
        if url!="https://www.jra.go.jp/JRADB/accessS.html":raise ValueError("unexpected_url")
        req=Request(url,method="POST",data=urlencode({"cname":cname}).encode("ascii"),headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.jra.go.jp/keiba/","Content-Type":"application/x-www-form-urlencoded"})
        try:
            with urlopen(req,timeout=20) as resp:
                data=resp.read(1500001)
                if len(data)>1500000:raise ValueError("too_large")
                if urlsplit(resp.geturl()).hostname not in ("www.jra.go.jp","jra.go.jp"):raise ValueError("redirect")
                status=resp.status
            (P/"kyoto_all_results_20261031.html").write_bytes(data)
            links=get_links(data)
            action_links=[x for x in links if "doAction" in x["onclick"]]
            summary.update(status="captured_html",http=status,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),links_total=len(links),actions=action_links[-50:])
        except Exception as exc:
            summary.update(status="failed",error=type(exc).__name__+":"+str(exc)[:120])
    (P/"kyoto_all_results_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf8")
    print("KYOTO_ALL_RESULTS",json.dumps(summary,ensure_ascii=False)[:19000])
if __name__=="__main__":main()
