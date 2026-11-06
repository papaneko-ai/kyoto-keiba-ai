"""P1-FB offline PC/SP adapters based on separately verified historical originals."""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json
from diagnostics.jra_p1_sp_profile_offline import parse
from diagnostics.jra_p1_failover_offline import ChannelResult,choose
from diagnostics.jra_pending_profile_plan import canonical
ROOT=Path("docs/diagnostics")
HORSE="モンドプリューム"
PC=ROOT/"jra_profile_replay_20261106/race_11_horse_01_form.json"
SP=ROOT/"jra_p1_fb_offline_20261106/sp_profile_receipt.json"
ROSTER="0c443ce664e6c8c7ed54ea2ebda837edef07f1a2697405bf069677b0cc67f565"
FIELDS=("date","venue","surface","distance_m","field_size","finish_position","popularity")
CUTOFF=datetime(2026,11,7,tzinfo=timezone.utc)
def load(p):return json.loads(Path(p).read_text(encoding="utf8"))
def normalized(rows,nonfinish):
    a=[]
    for r in rows:
        obj={k:(int(r[k]) if k=="popularity" else r[k]) for k in FIELDS}
        a.append(obj)
    b=[{"date":r["date"],"status":"除外" if r["status"] in ("除","除外") else r["status"]} for r in nonfinish]
    return {"finishes":a,"nonfinish":b}
def evaluate(original_folder):
    pc=load(PC);sp_receipt=load(SP)
    if pc["horse_name"]!=HORSE or sp_receipt["horse_name"]!=HORSE or sp_receipt["race"]!=11 or sp_receipt["horse_number"]!=1:
        raise ValueError("official_horse_identity_changed")
    paths=list(Path(original_folder).rglob("sp_11r_horse01.html"))
    if len(paths)!=1:raise ValueError("sp_original_missing_or_ambiguous")
    raw=paths[0].read_bytes()
    if sha256(raw).hexdigest()!=sp_receipt["source_sha256"] or len(raw)!=sp_receipt["source_bytes"]:
        raise ValueError("sp_source_sha_mismatch")
    mobile=parse(raw,HORSE)
    if mobile["invalid_rows"]:raise ValueError("sp_parser_invalid_rows")
    pc_norm=normalized(pc["prior_rows"],pc["nonfinish_rows"])
    sp_norm=normalized(mobile["prior_rows"],mobile["nonfinish_rows"])
    if pc_norm!=sp_norm:raise ValueError("official_pc_sp_row_difference")
    stamp_pc=pc["fetched_at_utc"];stamp_sp=sp_receipt["captured_at_utc"]
    for stamp in (stamp_pc,stamp_sp):
        d=datetime.fromisoformat(stamp.replace("Z","+00:00"))
        if d.tzinfo is None or d.astimezone(timezone.utc)>=CUTOFF:raise ValueError("source_after_cutoff")
    for x in pc_norm["finishes"]+pc_norm["nonfinish"]:
        if x["date"]>="2026-11-07":raise ValueError("future_event_in_training_input")
    normsha=sha256(canonical(pc_norm)).hexdigest()
    def ch(channel,source_sha,stamp):
        return ChannelResult(channel=channel,verified=True,source_sha256=source_sha,
            horse=HORSE,asof_utc=stamp,race=11,number=1,roster_sha=ROSTER,
            normalized_sha256=normsha,url_verified=True,raw_saved=True)
    pc_ch=ch("PC",pc["source_sha256"],stamp_pc)
    sp_ch=ch("SP",sp_receipt["source_sha256"],stamp_sp)
    comparisons={}
    for first,backup,ident in ((pc_ch,sp_ch,"PC_TO_SP"),(sp_ch,pc_ch,"SP_TO_PC")):
        comparisons[ident+"_BOTH_VALID"]=choose(first,backup,cutoff=CUTOFF,compare=True)[1]
        bad=ChannelResult(**{**first.__dict__,"verified":False,"error":"SIMULATED_PARSER_FAULT"})
        comparisons[ident+"_SIMULATED_FAILURE"]=choose(bad,backup,cutoff=CUTOFF)[1]
    if set(comparisons.values())!={"PRIMARY_VALID","FALLBACK_VALID_PRIMARY_STILL_BROKEN"}:
        raise ValueError("bidirectional_control_regressed")
    return {"schema":"kyoto_p1_fb_two_official_sources_offline.v1",
        "horse_name":HORSE,"pc_source_sha256":pc["source_sha256"],
        "sp_source_sha256":sp_receipt["source_sha256"],
        "roster_sha256":ROSTER,"normalized_sha256":normsha,
        "finishes":len(pc_norm["finishes"]),"nonfinish":len(pc_norm["nonfinish"]),
        "all_common_rows_match":True,"bidirectional_cases":comparisons,
        "network_requests":0,"live_automatic_fallback_authorized":False,
        "prediction_ready":False,"training_ready":False}
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--artifact",required=True);p.add_argument("--out",required=True);a=p.parse_args()
    result=evaluate(a.artifact);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(canonical(result))
    print(json.dumps(result,ensure_ascii=False))
