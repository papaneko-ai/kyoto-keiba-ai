"""Analyze one archived official Kyoto future racecard HTML offline.
Structure evidence only; never promotes to model without independent source gates.
"""
import json,argparse,re
from pathlib import Path
from bs4 import BeautifulSoup
from hashlib import sha256

def inspect(raw:bytes):
 soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
 tables=soup.select("table")
 summary={"schema_version":"jra_live_racecard_structure.v1","html_sha256":sha256(raw).hexdigest(),
 "table_count":len(tables),"rows":[],"raw_horse_id_verified":False,"ready_for_training":False}
 for ti,t in enumerate(tables):
  for ri,tr in enumerate(t.select("tr")):
   cells=tr.find_all(["th","td"],recursive=False)
   anchors=[{"label":a.get_text(" ",strip=True)[:38],
    "href":(a.get("href") or "")[:180],
    "onclick":(a.get("onclick") or "")[:180]} for a in tr.select("a")[:5]]
   summary["rows"].append({"table":ti,"row":ri,"cell_count":len(cells),
     "cells":[{"tag":x.name,"class":x.get("class",[]),
               "sample":x.get_text(" ",strip=True)[:100]} for x in cells[:12]],
     "anchors":anchors})
 summary["row_count"]=len(summary["rows"])
 summary["horse_number_like_rows"]=sum(1 for x in summary["rows"] if any(c["sample"].isdigit() and len(c["sample"])<=2 for c in x["cells"]))
 return summary

if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--html",required=True);p.add_argument("--out",required=True)
 a=p.parse_args()
 result=inspect(Path(a.html).read_bytes())
 d=Path(a.out);d.parent.mkdir(parents=True,exist_ok=True)
 d.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"table_count":result["table_count"],"row_count":result["row_count"],
 "horse_number_like_rows":result["horse_number_like_rows"]},ensure_ascii=False))
