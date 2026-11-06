"""Offline examination of exactly 12 rejected rows, SHA-locked SP original."""
import argparse,hashlib,json
from pathlib import Path
from bs4 import BeautifulSoup
R=Path("docs/diagnostics/jra_p1_fb_offline_20261106/sp_profile_second_receipt.json")
def inspect(root):
    r=json.loads(R.read_text(encoding="utf8"))
    matches=list(Path(root).rglob("sp_11r_horse02.html"))
    if len(matches)!=1:raise ValueError("original_not_unique")
    raw=matches[0].read_bytes()
    if hashlib.sha256(raw).hexdigest()!=r["source_sha256"] or len(raw)!=r["source_bytes"]:
        raise ValueError("sha_mismatch")
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    t=next((t for t in soup.select("table") if "出走レース" in t.get_text(" ",strip=True)[:80]),None)
    if t is None:raise ValueError("not_official_history")
    rows=t.select("tr")[1:]
    if len(rows)!=r["history_rows_total"]:raise ValueError("row_count_changed")
    evidence=[]
    for issue in r["invalid_rows"]:
        n=issue["row"];td=rows[n-1].find_all("td",recursive=False)
        evidence.append({"row":n,"reason":issue["reason"],
          "cells":[c.get_text(" ",strip=True)[:210] for c in td]})
    return {"schema":"p1_fb_sp_second_invalid_exact_evidence.v1",
       "source_sha256":r["source_sha256"],"invalid_count":len(evidence),
       "rows":evidence,"new_network_requests":0}
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--artifact",required=True);p.add_argument("--out",required=True);a=p.parse_args()
    d=inspect(a.artifact);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps(d,ensure_ascii=False))
