"""Read-only feature discovery from real JRA entries and track pages.
Uses already captured entry HTML, no new network to inspect entry links.
One optional GET to horse-specific links is NOT attempted.
"""
from html.parser import HTMLParser
from pathlib import Path
import json,re

ROOT=Path("jra_action_capture")
EXTRA=Path("jra_feature_discovery")
OUT=EXTRA/"predictive_field_structure.json"

class Parser(HTMLParser):
 def __init__(self):
  super().__init__();self.links=[];self.cur=None;self.tables=[];self.t=None;self.depth=0;self.forms=[]
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag=="a":self.cur={"label":"","href":d.get("href"),"onclick":d.get("onclick")}
  if tag=="table":
   if self.depth==0:self.t={"class":d.get("class"),"id":d.get("id"),"sample":[]}
   self.depth+=1
 def handle_data(self,data):
  s=" ".join(data.split())
  if not s:return
  if self.cur is not None:self.cur["label"]+=s+" "
  if self.depth and self.t is not None and len(self.t["sample"])<35:self.t["sample"].append(s)
 def handle_endtag(self,tag):
  if tag=="a" and self.cur is not None:
   self.cur["label"]=" ".join(self.cur["label"].split());self.links.append(self.cur);self.cur=None
  if tag=="table" and self.depth:
   self.depth-=1
   if not self.depth and self.t is not None:self.tables.append(self.t);self.t=None

def report_file(path):
 raw=path.read_bytes();html=raw.decode("cp932",errors="replace");p=Parser();p.feed(html)
 choices=[x for x in p.links if x.get("onclick") and any(k in x["label"] for k in ("京都","出馬","競走","馬連","枠連","4回","2026","結果","騎手","調教師"))]
 links=[x for x in p.links if any(k in x["label"] for k in ("京都","馬場","競走馬","騎手","出馬表","PDF","過去","成績","クッション","含水"))]
 return {"bytes":len(raw),"tables_count":len(p.tables),"table_samples":p.tables[:10],
         "relevant_actions":choices[:45],"relevant_links":links[:30],
         "body_titles":re.findall(r"<h[1-4][^>]*>(.*?)</h[1-4]>",html,re.I|re.S)[:14]}

def main():
 paths={
  "entry_index":ROOT/"entries.html",
  "historic_result":ROOT/"kyoto_all_results_20261031.html",
  "track":EXTRA/"kyoto_track_conditions.html",
  "horse_racecard_pdf":EXTRA/"racecard_pdf_index.html",
  "rider":EXTRA/"jockey_trainer_index.html",
 }
 out={}
 for key,path in paths.items():
  try:out[key]=report_file(path);print("FIELD_STRUCTURE",key,json.dumps(out[key],ensure_ascii=False)[:11500])
  except Exception as exc:out[key]={"error":type(exc).__name__+":"+str(exc)[:140]};print("FIELD_STRUCTURE_FAIL",key,out[key])
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf8")
if __name__=="__main__":main()
