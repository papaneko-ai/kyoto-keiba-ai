"""Independent G05 incident replay with a pinned collector. Never emit source values.
Run as a script with the exact trusted reader checkout as cwd/PYTHONPATH.
No network, no DB writes, and no archive keys in this process.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

TRACK=("weather","turf_going","dirt_going")
EXTRA=("turf_moisture_finish_pct","turf_moisture_turn4_pct","dirt_moisture_finish_pct","dirt_moisture_turn4_pct")
WEIGHT=("body_weight_kg","body_weight_change_kg")

def review(root,day):
    from diagnostics.kyoto_g03_independent_partial import verify_partial
    from diagnostics.kyoto_g03_to_g06_input_adapter import records_from_g03
    from diagnostics.kyoto_g04_all_horse_profiles import _utc
    from diagnostics.kyoto_impl30_day_coverage import independent_track
    from diagnostics.kyoto_g05_conditions import _race_fields,_body_weights
    root=Path(root)
    if day not in ("20261128","20261129") or root.is_symlink() or not root.is_dir():
        raise ValueError("invalid_replay_identity")
    out={"replay_complete":True,"verified_races":[],"race_rows":{},"roster_replay_available":False}
    try:
        course=independent_track(root,day)
    except Exception:
        course={}
    out["course_observed"]=[k for k in TRACK+EXTRA if k in course]
    out["course_missing"]=[k for k in TRACK+EXTRA if k not in course]
    try:
        good=verify_partial(root,expected_day=day)["verified_race_numbers"]
        records=records_from_g03(root,day=day,skip_invalid_races=True)
        g03=json.loads((root/"g03_receipt.json").read_text(encoding="utf8"))
        out["roster_replay_available"]=True
    except Exception:
        return out
    for n in sorted(good):
        try:
            rec=records[n]
            if rec is None:continue
            info=g03["races"][str(n)]
            roster=info["runners"]
            cancelled={h["number"] for h in roster if h.get("cancelled") is True}
            active=sorted({h["number"] for h in roster}-cancelled)
            raw=(root/f"g03_official_racecard_{n:02d}.html").read_bytes()
            cutoff=_utc(rec["verified_start_utc"])
            row={"active_horses":len(active),"cancelled_horses":sorted(cancelled),
                 "missing_body_weight_kg":active[:],"missing_body_weight_change_kg":active[:],
                 "missing_race_conditions":list(TRACK)}
            try:
                track=_race_fields(raw)
                row["missing_race_conditions"]=[k for k in TRACK if track.get(k) is None and not
                    (k in course and _utc(course[k]["utc"])<cutoff)]
            except Exception:pass
            try:
                weights=_body_weights(raw,[h["number"] for h in roster],expected_cancelled=cancelled)
                row["missing_body_weight_kg"]=[h for h in active if weights[h][0] is None]
                row["missing_body_weight_change_kg"]=[h for h in active if weights[h][1] is None]
            except Exception:pass
            out["verified_races"].append(n)
            out["race_rows"][str(n)]=row
        except Exception:continue
    return out

def main():
    if len(sys.argv)!=3:raise SystemExit(2)
    def denied(*a,**kw):raise AssertionError("source_network_forbidden")
    with patch("socket.socket.connect",side_effect=denied),patch("socket.create_connection",side_effect=denied):
        result=review(sys.argv[1],sys.argv[2])
    print(json.dumps(result,sort_keys=True,separators=(",",":"),allow_nan=False))

if __name__=="__main__":main()
