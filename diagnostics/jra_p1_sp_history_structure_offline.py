"""Offline inspect SP history table fields from original SHA locked incident source."""
from pathlib import Path
from bs4 import BeautifulSoup
from hashlib import sha256
import json,argparse
def inspect(original):
    raw=Path(original).read_bytes()
    receipt=json.loads(Path("docs/diagnostics/jra_p1_fb_offline_20261106/sp_profile_receipt.json").read_text())
    if sha256(raw).hexdigest()!=receipt["source_sha256"]:raise ValueError("original_mismatch")
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    table=next(t for t in soup.select("table") if "出走レース" in t.get_text(" ",strip=True)[:50])
    rows=[]
    for index,tr in enumerate(table.select("tr")):
        cells=tr.find_all(["th","td"],recursive=False)
        rows.append({"index":index,"count":len(cells),
            "cells":[{"tag":c.name,"text":c.get_text(" ",strip=True)[:140],
                      "class":c.get("class",[]),"rowspan":c.get("rowspan"),
                      "colspan":c.get("colspan")} for c in cells]})
    return {"sha":receipt["source_sha256"],"row_count":len(rows),
        "first_rows":rows[:6],"last_rows":rows[-3:],"new_network_requests":0}
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--artifact",required=True);p.add_argument("--out",required=True);a=p.parse_args()
    paths=list(Path(a.artifact).rglob("sp_11r_horse01.html"))
    if len(paths)!=1:raise ValueError("missing_artifact")
    result=inspect(paths[0]);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"rows":result["row_count"],"network":0}))
