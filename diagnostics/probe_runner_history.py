"""Inspect public JRA runner history and entry navigation from official source links.
At most one further horse-profile POST. No prediction or production changes.
"""
from pathlib import Path
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urljoin, urlsplit
from hashlib import sha256
from datetime import datetime, timezone
import re,json

ROOT=Path("jra_feature_discovery")
RESULT=Path("jra_action_capture/kyoto_all_results_20261031.html")
ENTRY=Path("jra_action_capture/entries.html")
MAX=1250000

class Links(HTMLParser):
 def __init__(self):super().__init__();self.items=[];self.a=None
 def handle_starttag(self,tag,attrs):
  if tag=="a":self.a={"text":"","onclick":dict(attrs).get("onclick") or "", "href":dict(attrs).get("href") or ""}
 def handle_data(self,data):
  if self.a is not None:self.a["text"]+=data
 def handle_endtag(self,tag):
  if tag=="a" and self.a is not None:
   self.a["text"]=" ".join(self.a["text"].split());self.items.append(self.a);self.a=None

def parse(path):
 p=Links();p.feed(path.read_bytes().decode("cp932",errors="replace"));return p.items

def capture_one(links):
 # A horse named on official result page, not a guessed identifier.
 choices=[x for x in links if "doAction" in x["onclick"] and "accessR.html" in x["onclick"] and x["text"] not in ("競走馬検索","競走馬登録","")]
 result={"candidate_count":len(choices),"samples":choices[:6],"status":"not_attempted"}
 if not choices:
  result["status"]="horse_profile_links_missing";return result
 x=choices[0]
 m=re.search(r"doAction\s*\(\s*'([^']+)'\s*,\s*'([^']+)'",x["onclick"])
 if not m:
  result["status"]="bad_action_signature";return result
 path,cname=m.groups()
 url=urljoin("https://www.jra.go.jp",path)
 if url!="https://www.jra.go.jp/JRADB/accessR.html":
  result["status"]="unexpected_endpoint";return result
 req=Request(url,method="POST",data=urlencode({"cname":cname}).encode("ascii"),headers={
  "User-Agent":"Mozilla/5.0","Referer":"https://www.jra.go.jp/keiba/",
  "Content-Type":"application/x-www-form-urlencoded","Accept":"text/html"})
 try:
  with urlopen(req,timeout=18) as response:
   body=response.read(MAX+1)
   if len(body)>MAX or urlsplit(response.geturl()).hostname not in ("www.jra.go.jp","jra.go.jp"):
    raise ValueError("invalid_response")
   result["http"]=response.status
  (ROOT/"horse_profile_one.html").write_bytes(body)
  text=" ".join(re.sub("<[^>]+>"," ",body.decode("cp932",errors="replace")).split())
  pos=text.find("ここから本文")
  if pos<0:pos=0
  result.update(status="captured",bytes=len(body),sha256=sha256(body).hexdigest(),
   page_text_excerpt=text[pos:pos+2100],
   feature_terms={term:text.count(term) for term in
    ("過去","レース成績","出走履歴","競走成績","着順","芝","ダート","騎手","調教師","馬名","タイム","距離")})
 except Exception as err:
  result.update(status="failed",reason=type(err).__name__+":"+str(err)[:130])
 return result

def main():
 ROOT.mkdir(exist_ok=True)
 rlinks=parse(RESULT);elinks=parse(ENTRY)
 entry_choices=[x for x in elinks if "doAction" in x["onclick"] and
                "accessD.html" in x["onclick"]]
 target_names=("マルモリマイベスト","ジャスコヒラリアス","ランズエンド")
 named_links=[x for x in rlinks if any(name in x["text"] for name in target_names)]
 other_horse_links=[x for x in rlinks if "doAction" in x["onclick"] and any(t in x["onclick"] for t in ("accessU.html","accessR.html","accessE.html"))]
 print("NAMED_HORSE_LINKS",json.dumps(named_links[:12],ensure_ascii=False))
 print("OTHER_HORSE_ACTIONS",json.dumps(other_horse_links[:15],ensure_ascii=False))
 report={"checked_at_utc":datetime.now(timezone.utc).isoformat(),
  "result_horse_link_count":sum("accessR.html" in x["onclick"] for x in rlinks),
  "entry_actions":entry_choices[:25],
  "horse_profile":capture_one(rlinks),"named_links":named_links[:12],"other_horse_actions":other_horse_links[:15]}
 (ROOT/"runner_history_probe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
 print("ENTRY_ACTIONS",json.dumps({"count":len(entry_choices),"sample":entry_choices[:15]},ensure_ascii=False)[:4500])
 print("RUNNER_HISTORY",json.dumps(report["horse_profile"],ensure_ascii=False)[:8000])

if __name__=="__main__":main()
