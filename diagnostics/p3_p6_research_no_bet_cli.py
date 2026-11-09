"""Emit P6 no-bet receipt for historic, unlabeled 148-horse matrix only."""
import argparse
import csv
import json
from pathlib import Path
from diagnostics.p3_p6_research_no_bet import historical_no_bet_receipt

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--features", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    args=p.parse_args()
    with args.features.open(encoding="utf-8", newline="") as f:
        rows=list(csv.DictReader(f))
    if len(rows) != 148 or {r.get("meeting_date") for r in rows} != {"2026-11-07"}:
        raise ValueError("locked_historical_meeting_expected")
    if {r.get("profile_state") for r in rows} != {"VERIFIED_SOURCE_ROWS","VERIFIED_EMPTY_HISTORY","NOT_QUERIED"}:
        raise ValueError("missing_evidence_state")
    receipt=historical_no_bet_receipt(rows)
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(receipt,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("P6_NO_BET_HISTORIC_ONLY: 148 runners, 0 predictions, 0 virtual/actual stakes")

if __name__=="__main__":
    main()
