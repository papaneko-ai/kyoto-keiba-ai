"""Reparse official SP source without HTTP; count parity against archived PC horse."""
from pathlib import Path
from hashlib import sha256
import argparse,json
from diagnostics.jra_p1_sp_profile_offline import parse
ROOT=Path("docs/diagnostics")
def run(artifact,out):
    rec=json.loads((ROOT/"jra_p1_fb_offline_20261106/sp_profile_receipt.json").read_text())
    paths=list(Path(artifact).rglob("sp_11r_horse01.html"))
    if len(paths)!=1:raise ValueError("sp_original_missing")
    raw=paths[0].read_bytes()
    if rec["horse_name"]!="モンドプリューム" or sha256(raw).hexdigest()!=rec["source_sha256"]:
        raise ValueError("sp_source_not_original")
    d=parse(raw,"モンドプリューム")
    pc=json.loads((ROOT/"jra_p1_batch14_96_profiles_20261106/feature_rows_148.json").read_text())
    match=[r for r in pc if r["race_number"]==11 and r["horse_number"]==1]
    if len(match)!=1 or match[0]["horse_name"]!=rec["horse_name"] or match[0]["profile_status"]!="HISTORY_TABLE_PARSED":
        raise ValueError("pc_source_not_preverified")
    pc_count=match[0]["performance_features"]["prior_valid_finishes_available"]
    result={"schema":"p1_fb_sp_profile_real_parity.v1",
        "horse_name":"モンドプリューム","race":11,"number":1,
        "sp_sha256":rec["source_sha256"],"pc_sha256":match[0]["profile_source_sha256"],
        "sp_history_rows":d["history_rows_total"],"sp_prior_valid_finishes":len(d["prior_rows"]),
        "sp_nonfinish_count":len(d["nonfinish_rows"]), "sp_invalid_rows":d["invalid_rows"],
        "pc_prior_valid_finishes":pc_count,
        "count_parity":len(d["prior_rows"])==pc_count,
        "new_network_requests":0,"live_auto_fallback_authorized":False,
        "prediction_ready":False,"training_ready":False}
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    if d["invalid_rows"] or not result["count_parity"]:raise ValueError("sp_profile_parser_not_parity_verified")
    return result
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--artifact",required=True);a.add_argument("--out",required=True);x=a.parse_args()
    print(json.dumps(run(x.artifact,x.out),ensure_ascii=False))
