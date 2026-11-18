"""Deterministically rehearse promotion and rollback of the actual weekend YAML.

No write to main. No API/HTTP access. Reject any unrelated configuration changes.
"""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path
BASE="c96df31542cb94435ca36cb4a1b8bd6de938233f"
CANDIDATE="922d1b879edd8b40d37ee52b36ba8c75dab965cb"
FILE=".github/workflows/kyoto-20261121-22-two-source-production-observer.yml"
EXPECTED_BASE="669124c020e627bcba186228b20fb1721cc688e1"
SCHEDULES=("15 0 21 11 *","15 1 21 11 *","5 2 21 11 *","50 2 21 11 *",
           "15 0 22 11 *","15 1 22 11 *","10 2 22 11 *","55 2 22 11 *")

def digest(value:bytes)->str:
    return hashlib.sha256(value).hexdigest()

def review(main_path,review_path):
    main=Path(main_path).read_bytes()
    candidate=Path(review_path).read_bytes()
    if BASE.encode() not in main or main.count(BASE.encode())!=6:
        raise ValueError("main_source_pin_changed_or_incomplete")
    if CANDIDATE.encode() not in candidate or candidate.count(CANDIDATE.encode())!=6:
        raise ValueError("candidate_pin_changed_or_incomplete")
    promoted=main.replace(BASE.encode(),CANDIDATE.encode())
    if candidate!=promoted:
        raise ValueError("review_has_unapproved_nonpin_changes")
    restored=candidate.replace(CANDIDATE.encode(),BASE.encode())
    if restored!=main:
        raise ValueError("rollback_bytes_differ")
    schedule=re.findall(rb"^\s*- cron: ['\"]([^'\"]+)['\"]",main,re.M)
    if sorted(c.decode() for c in schedule)!=sorted(SCHEDULES):
        raise ValueError("actual_8_windows_not_preserved")
    if not all(marker in main for marker in
        (b"pc-originals-independent:",b"sp-originals-independent:",
         b"KYOTO_JRA_ARCHIVE_AES256_HEX",b"cancel-in-progress: false")):
        raise ValueError("operational_safety_lost")
    return {"schema":"kyoto_weekend_reversible_promotion.v1",
            "production_main_workflow_sha256":digest(main),
            "candidate_workflow_sha256":digest(candidate),
            "restored_workflow_sha256":digest(restored),
            "reversible_byte_identical":True,"review_only":True,
            "source_pin_changes_only":True,"pinned_replacements":6,
            "preserved_observation_slots":len(SCHEDULES),
            "future_production_merge_performed":False,
            "rollback_target_collector_sha":BASE,
            "candidate_collector_sha":CANDIDATE,
            "requires_approval_before_main_change":True,
            "network_requests":0}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main-workflow",required=True)
    p.add_argument("--candidate-workflow",required=True)
    p.add_argument("--out",required=True)
    x=p.parse_args()
    r=review(x.main_workflow,x.candidate_workflow)
    Path(x.out).parent.mkdir(parents=True,exist_ok=True)
    Path(x.out).write_text(json.dumps(r,indent=2,sort_keys=True)+"\n")
    print("REVIEW_ROLLBACK_BYTE_IDENTICAL=TRUE")
if __name__=="__main__":
    main()
