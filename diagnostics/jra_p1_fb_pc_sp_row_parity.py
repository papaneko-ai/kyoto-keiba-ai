"""P1-FB: 31 event row-by-row parity of original SP HTML and saved PC records.
Offline only, no HTTP, no model adoption. Fail closed for a single mismatch.
"""
import argparse,hashlib,json
from pathlib import Path
from diagnostics.jra_p1_sp_profile_offline import parse
PC=Path("docs/diagnostics/jra_profile_replay_20261106/race_11_horse_01_form.json")
SP=Path("docs/diagnostics/jra_p1_fb_offline_20261106/sp_profile_receipt.json")
FIELDS=("date","venue","surface","distance_m","field_size","finish_position")
def verify(root):
    expected=json.loads(SP.read_text(encoding="utf8"))
    pc=json.loads(PC.read_text(encoding="utf8"))
    paths=list(Path(root).rglob("sp_11r_horse01.html"))
    if len(paths)!=1:raise ValueError("official_sp_original_missing_or_ambiguous")
    raw=paths[0].read_bytes()
    if (hashlib.sha256(raw).hexdigest()!=expected["source_sha256"] or
        len(raw)!=expected["source_bytes"] or expected["horse_name"]!=pc["horse_name"] or
        expected["horse_number"]!=1 or expected["race"]!=11 or
        expected["requests"]!=1 or pc["source_sha256"]!="87bcbe38112dc1855f22099edb9bff5cc30a14b78b595470373b6355b2907b9c"):
        raise ValueError("pc_sp_provenance_mismatch")
    sp=parse(raw,expected["horse_name"])
    if sp["invalid_rows"]:raise ValueError("sp_unparsed_records")
    pc_rows=pc["prior_rows"];sp_rows=sp["prior_rows"]
    if len(pc_rows)!=len(sp_rows):raise ValueError("finish_count_mismatch")
    mismatches=[]
    for i,(a,b) in enumerate(zip(pc_rows,sp_rows),1):
        for field in FIELDS:
            if a[field]!=b[field]:
                mismatches.append({"row":i,"field":field,"pc":a[field],"sp":b[field]})
        if int(a["popularity"])!=b["popularity"]:
            mismatches.append({"row":i,"field":"popularity","pc":a["popularity"],"sp":b["popularity"]})
    if len(pc["nonfinish_rows"])!=len(sp["nonfinish_rows"]):
        mismatches.append({"field":"nonfinish_count"})
    else:
        for i,(a,b) in enumerate(zip(pc["nonfinish_rows"],sp["nonfinish_rows"]),1):
            if a["date"]!=b["date"] or not (a["status"]=="除外" and b["status"] in ("除","除外")):
                mismatches.append({"nonfinish_row":i,"pc":a,"sp":b})
    return {"schema":"p1_fb_pc_sp_31_event_row_parity.v1",
        "horse_name":pc["horse_name"],"race":11,"horse_number":1,
        "pc_sha256":pc["source_sha256"],"sp_sha256":expected["source_sha256"],
        "pc_finish_rows":len(pc_rows),"sp_finish_rows":len(sp_rows),
        "pc_nonfinish_rows":len(pc["nonfinish_rows"]),"sp_nonfinish_rows":len(sp["nonfinish_rows"]),
        "checked_finish_fields":list(FIELDS)+["popularity"],
        "checked_finish_cells":len(pc_rows)*(len(FIELDS)+1),
        "mismatches":mismatches,"row_parity":not mismatches,
        "network_requests":0,"live_auto_fallback_authorized":False,
        "training_ready":False,"prediction_ready":False}
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--artifact",required=True);a.add_argument("--out",required=True);q=a.parse_args()
    result=verify(q.artifact);out=Path(q.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps(result,ensure_ascii=False))
    if not result["row_parity"]:raise SystemExit(1)
