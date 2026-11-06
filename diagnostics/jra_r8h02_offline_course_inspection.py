"""Inspect exactly the two failed course cells from already archived R8 horse02 HTML.
Offline only. Report bounded row text, no network and no training.
"""
import argparse,json,hashlib
from pathlib import Path
from bs4 import BeautifulSoup
from diagnostics.jra_prior_form_offline import COURSE,HEADERS
from diagnostics.jra_batch13_r8h02_one_shot_diagnostic import EXPECTED

def inspect(originals):
    root=Path(originals)
    paths=list(root.rglob("race_08_horse_02_diagnostic.html"))
    if len(paths)!=1:raise ValueError("incident_html_missing_or_ambiguous")
    raw=paths[0].read_bytes()
    receipt=json.loads((Path("docs/diagnostics/jra_p1_r8h02_diagnosis_20261106/receipt.json")).read_text())
    if hashlib.sha256(raw).hexdigest()!=receipt["source_sha256"] or len(raw)!=receipt["source_bytes"]:
        raise ValueError("mismatched_sha_source")
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    table=next((t for t in soup.select("table") if t.select_one("th.date") and t.select_one("th.place") and t.select_one("th.dist")),None)
    if table is None:raise ValueError("missing_history")
    rows=table.select("tr")[1:]
    if len(rows)!=28:raise ValueError("changed_history_count")
    records=[]
    for n in (17,23):
        td=rows[n-1].find_all("td",recursive=False)
        fields=[x.get_text(" ",strip=True) for x in td]
        records.append({"row":n,"column_count":len(fields),"date":fields[0],
           "race_title":fields[2],"course_value":fields[3],
           "course_repr":repr(fields[3]),"surface_parsed":bool(COURSE.fullmatch(fields[3])),
           "field_size":fields[5],"finish_position":fields[7]})
    return {"source_sha256":receipt["source_sha256"],"source_bytes":len(raw),
            "previous_invalid_rows":receipt["invalid_rows"],
            "offending_rows":records,"new_network_requests":0,"training_ready":False,"prediction_ready":False}
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--artifact",required=True);p.add_argument("--out",required=True);a=p.parse_args()
    data=inspect(a.artifact);path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(data,ensure_ascii=False))
