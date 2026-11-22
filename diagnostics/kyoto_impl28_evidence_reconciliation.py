"""Conservative reconciliation of saved 2026-11-22 Kyoto evidence.

Never infer full data availability from encrypted original capture or a
108-record ledger snapshot. Only matching per-race SHA and identity can
establish a structured roster.
"""
import json
from pathlib import Path

def reconcile(source, parsed, ledger):
    if source.get("day") != "20261122":
        raise ValueError("SOURCE_DAY_MISMATCH")
    result = {"day":"20261122","racecard_originals":0,"structured_rosters":0,
              "races":{},"ledger_is_snapshot":True,"unverified_families":[
              "quinella_odds","bracket_quinella_odds","horse_profile",
              "past_performances","track_conditions","official_result","official_payout"]}
    for race in range(1,13):
        lanes=source.get("races",{}).get(str(race),{})
        pc=lanes.get("PC",{})
        sp=lanes.get("SP",{})
        verified=[]
        for ch, entry in (("PC",pc),("SP",sp)):
            if (entry.get("state")=="REAL_OFFICIAL_ORIGINAL_SAVED_ROSTER_NOT_AUTHENTICATED"
                and entry.get("identity_hints",{}).get("same_day_kyoto_race_heading") is True
                and isinstance(entry.get("sha256"),str) and len(entry["sha256"])==64):
                verified.append((ch,entry["sha256"]))
        original=bool(verified)
        result["racecard_originals"]+=int(original)
        row=parsed.get("races",{}).get(str(race),{})
        structured=(original and isinstance(row,dict) and
                    row.get("original_sha256") in [sha for _,sha in verified] and
                    row.get("state") == "G03_ROSTER_AND_START_PARSED_FROM_ACTUAL_ORIGINAL")
        result["structured_rosters"]+=int(structured)
        result["races"][str(race)]={"original_verified":original,
                                   "channels":[ch for ch,_ in verified],
                                   "roster_verified":bool(structured)}
    result["ledger_record_count"]=(len(ledger) if isinstance(ledger,list) else len(ledger.get("records",[])) if isinstance(ledger,dict) else None)
    return result

def main():
    import argparse
    parser=argparse.ArgumentParser()
    for key in ("source","parsed","ledger"):
        parser.add_argument(key,type=Path)
    a=parser.parse_args()
    data=[json.loads(getattr(a,key).read_text(encoding="utf-8")) for key in ("source","parsed","ledger")]
    print(json.dumps(reconcile(*data),ensure_ascii=False,indent=2))
if __name__=="__main__":main()
