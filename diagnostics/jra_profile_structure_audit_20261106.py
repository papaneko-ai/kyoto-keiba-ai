"""Inspect 3 previously downloaded real JRA horse originals without new HTTP."""
from pathlib import Path
from bs4 import BeautifulSoup
from hashlib import sha256
import argparse,json
def main(directory,out):
    root=Path(directory);data={}
    for race in (1,5,11):
        paths=list(root.rglob(f"kyoto_{race:02d}_horse_01.html"))
        if len(paths)!=1:raise ValueError(f"missing_source_for_{race}")
        raw=paths[0].read_bytes()
        soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
        table=next((t for t in soup.select("table") if t.select_one("th.date") and t.select_one("th.place") and t.select_one("th.dist")),None)
        rows=table.select("tr") if table else []
        data[str(race)]={"sha256":sha256(raw).hexdigest(),
            "title":soup.title.get_text(" ",strip=True) if soup.title else "",
            "identity_texts":[x.get_text(" ",strip=True)[:140] for x in soup.select("span.txt") if x.select_one("span.opt")][:4],
            "history_table_found":table is not None,
            "first_history_rows":[[td.get_text(" ",strip=True) for td in tr.select("td")] for tr in rows[1:3]],
            "body_markers":{k:soup.get_text(" ",strip=True).count(k) for k in ("競走成績","出走履歴","競走馬情報","未出走","過去","年月日","着順","出走経験")}}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps(data,ensure_ascii=False,indent=2))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--artifact",required=True);p.add_argument("--out",required=True);a=p.parse_args()
    main(a.artifact,a.out)
