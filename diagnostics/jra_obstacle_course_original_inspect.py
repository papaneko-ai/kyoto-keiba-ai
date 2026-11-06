"""Inspect ONLY abnormal course cells from archived source JRA obstacle profile."""
import argparse,json
from pathlib import Path
from bs4 import BeautifulSoup
from hashlib import sha256
def inspect(path):
 raw=Path(path).read_bytes();s=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
 t=next((x for x in s.select("table") if x.select_one("th.date") and x.select_one("th.place") and x.select_one("th.dist")),None)
 if t is None:raise ValueError("actual_horse_history_table_missing")
 rows=[]
 for i,tr in enumerate(t.select("tr")[1:],1):
  cells=[x.get_text(" ",strip=True) for x in tr.find_all("td",recursive=False)]
  if i in (2,4,6) or (len(cells)>3 and ("→" in cells[3] or "⇒" in cells[3])):
   rows.append({"row":i,"date":cells[0] if cells else None,"course":cells[3] if len(cells)>3 else None,
       "finish":cells[7] if len(cells)>7 else None,
       "field_size":cells[5] if len(cells)>5 else None})
 return {"source_sha256":sha256(raw).hexdigest(),"horse_name":"ロードリベラシオン",
   "special_course_rows":rows,"model_ready":False}
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--original",required=True);p.add_argument("--out",required=True);a=p.parse_args()
 x=inspect(a.original);dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 print(json.dumps(x,ensure_ascii=False))
