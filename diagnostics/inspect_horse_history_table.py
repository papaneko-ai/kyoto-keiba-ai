"""Offline inspect real JRA horse profile for history-table structure."""
from html.parser import HTMLParser
from pathlib import Path
import json,re

P=Path("jra_feature_discovery/jra_one_horse_history.html")
OUT=Path("jra_feature_discovery/horse_history_structure.json")
class Tables(HTMLParser):
 def __init__(self):super().__init__();self.tables=[];self.depth=0;self.t=None;self.hide=0
 def handle_starttag(self,tag,attrs):
  if tag in ("style","script"):self.hide+=1
  if tag=="table":
   if not self.depth:self.t={"class":dict(attrs).get("class",""),"tokens":[]}
   self.depth+=1
 def handle_endtag(self,tag):
  if tag in ("style","script") and self.hide:self.hide-=1
  if tag=="table" and self.depth:
   self.depth-=1
   if not self.depth and self.t:self.tables.append(self.t);self.t=None
 def handle_data(self,data):
  if self.depth and not self.hide and self.t:
   value=" ".join(data.split())
   if value:self.t["tokens"].append(value)
def main():
 body=P.read_bytes();html=body.decode("cp932",errors="replace")
 p=Tables();p.feed(html)
 result={"tables":len(p.tables),"candidates":[]}
 for i,t in enumerate(p.tables):
  sample=" ".join(t["tokens"])
  if any(k in sample for k in ("年月日","レース名","着順","距離","馬場","競馬場","騎手","出走履歴")):
   result["candidates"].append({"index":i,"class":t["class"],"length":len(sample),"excerpt":sample[:2400]})
 OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
 print("HORSE_HISTORY_STRUCTURE",json.dumps(result,ensure_ascii=False)[:12000])
if __name__=="__main__":main()
