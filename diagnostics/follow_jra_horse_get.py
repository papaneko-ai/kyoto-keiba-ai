"""Follow one real horse-name hyperlink from JRA results; one GET only."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.request import Request,urlopen
from urllib.parse import urljoin,urlsplit,parse_qs
from hashlib import sha256
import json,re

SRC=Path("jra_action_capture/kyoto_all_results_20261031.html")
OUT=Path("jra_feature_discovery")
NAME="マルモリマイベスト"
class A(HTMLParser):
 def __init__(self):super().__init__();self.items=[];self.a=None
 def handle_starttag(self,tag,attrs):
  if tag=="a":self.a={"label":"","href":dict(attrs).get("href") or ""}
 def handle_data(self,s):
  if self.a is not None:self.a["label"]+=s
 def handle_endtag(self,tag):
  if tag=="a" and self.a is not None:
   self.items.append(self.a);self.a=None

def main():
 parser=A();parser.feed(SRC.read_bytes().decode("cp932",errors="replace"))
 matches=[x for x in parser.items if x["label"].strip()==NAME and x["href"].startswith("/JRADB/accessU.html?")]
 report={"name":NAME,"source_matches":len(matches),"status":"not_attempted"}
 if len(matches)==1:
  url=urljoin("https://www.jra.go.jp/",matches[0]["href"])
  u=urlsplit(url)
  if u.hostname!="www.jra.go.jp" or u.path!="/JRADB/accessU.html" or len(parse_qs(u.query).get("CNAME",[]))!=1:
   raise ValueError("invalid_link")
  try:
   with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"}),timeout=20) as r:
    body=r.read(1200001);report["http"]=r.status
    if urlsplit(r.geturl()).hostname not in ("www.jra.go.jp","jra.go.jp") or len(body)>1200000:
     raise ValueError("unexpected_response")
   (OUT/"jra_one_horse_history.html").write_bytes(body)
   text=" ".join(re.sub("<[^>]+>"," ",body.decode("cp932",errors="replace")).split())
   idx=text.find("ここから本文")
   report.update(status="captured",bytes=len(body),sha256=sha256(body).hexdigest(),
    count={w:text.count(w) for w in ("マルモリマイベスト","競走成績","出走履歴","過去","着順","年月日","芝","ダート","馬場","距離","騎手","タイム")},
    main_text=text[max(0,idx):max(0,idx)+2100])
  except Exception as e:
   report.update(status="failed",reason=type(e).__name__+":"+str(e)[:140])
 else:report["status"]="not_unique"
 OUT.mkdir(exist_ok=True)
 (OUT/"jra_one_horse_history_probe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
 print("HORSE_HISTORY_GET",json.dumps(report,ensure_ascii=False)[:10000])
if __name__=="__main__":main()
