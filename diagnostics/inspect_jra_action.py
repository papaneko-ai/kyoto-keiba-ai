"""Inspect actual JRA navigation JS and forms, do not post or submit anything."""
from urllib.request import Request, urlopen
from html.parser import HTMLParser
from pathlib import Path
import json,re

class Forms(HTMLParser):
    def __init__(self):
        super().__init__();self.forms=[];self.cur=None
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if tag=="form":
            self.cur={"action":d.get("action"),"method":d.get("method"),"id":d.get("id"),"name":d.get("name"),"fields":[]}
            self.forms.append(self.cur)
        if tag=="input" and self.cur is not None:
            self.cur["fields"].append({"name":d.get("name"),"type":d.get("type"),"value":(d.get("value") or "")[:100]})
    def handle_endtag(self,tag):
        if tag=="form":self.cur=None

def main():
    url="https://www.jra.go.jp/keiba/"
    with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=15) as r:
        body=r.read(1_500_001)
        if len(body)>1_500_000:raise ValueError("too_large")
    html=body.decode("cp932",errors="replace")
    x=Forms();x.feed(html)
    js=[]
    for p in (r"function\\s+doAction\\s*\\(",r"doAction\\s*[:=]\\s*function",r"function\\s+postAction\\s*\\("):
        for match in list(re.finditer(p,html,re.I))[:3]:
            js.append(html[max(0,match.start()-50):match.start()+1500])
    scripts=re.findall(r'<script[^>]+src=["\\\']([^"\\\']+)',html,re.I)
    data={"forms":x.forms[:30],"inline_action_js":js,"scripts":scripts[:60],"declared_charset":re.findall(r"charset[=\\\"' ]+([\\w-]+)",html[:3000],re.I)[:5]}
    Path("jra_link_discovery").mkdir(exist_ok=True)
    Path("jra_link_discovery/action_details.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf8")
    print("FORMS",json.dumps(data["forms"],ensure_ascii=False)[:9000])
    print("ACTION_JS",json.dumps(js,ensure_ascii=False)[:7000])
    print("SCRIPTS",json.dumps(scripts[:35],ensure_ascii=False))
if __name__=="__main__":main()
