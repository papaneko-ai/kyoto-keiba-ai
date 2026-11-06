"""Inspect current JRA racecard's own race-selection links, without guessed tokens."""
from pathlib import Path
from bs4 import BeautifulSoup
import argparse,json
def inspect(raw):
 soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
 links=[]
 for a in soup.select("a"):
  href=a.get("href","");action=a.get("onclick","")
  if "/JRADB/accessD.html" in href or "/JRADB/accessD.html" in action:
   links.append({"label":a.get_text(" ",strip=True)[:60],"href":href[:230],"onclick":action[:230]})
 return {"link_count":len(links),"links":links,"prediction_ready":False}
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--html",required=True);p.add_argument("--out",required=True)
 a=p.parse_args();result=inspect(Path(a.html).read_bytes())
 d=Path(a.out);d.parent.mkdir(parents=True,exist_ok=True)
 d.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 print(json.dumps({"count":result["link_count"]}))
