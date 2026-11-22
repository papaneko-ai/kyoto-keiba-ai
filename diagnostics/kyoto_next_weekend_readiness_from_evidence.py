"""Build Nov28/29 acquisition readiness from immutable Nov21/22 evidence.

This is a deterministic preparation plan, not fabricated official race URLs,
JRA schedule, live odds or a production deployment.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from diagnostics.kyoto_evidence_complete_family_ledger import FAMILIES

DAYS=("20261128","20261129")
PREFLIGHT_FAMILIES=("racecard_original","roster","horse_profile",
                    "past_performances","track_conditions","quinella_odds",
                    "bracket_quinella_odds")
AFTER_RACE_FAMILIES=("official_result","official_payout")
REQUIRED_RUNS={44848944302,44854931835,44857934629,44861934823}
ARCHIVED_SOURCE_ROOT="evidence/2026-11-21_22/"

def _hash(b):return hashlib.sha256(b).hexdigest()

def prepare(archive_root,previous):
    if previous.get("schema")!="kyoto_evidence_complete_family_ledger.v1" or previous.get("day")!="20261122":
        raise ValueError("invalid_prior_108_source_ledger")
    if len(previous.get("records",[]))!=108:
        raise ValueError("previous_108_records_missing")
    prior_hash=previous.get("content_sha256")
    body={k:v for k,v in previous.items() if k!="content_sha256"}
    if _hash(json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode())!=prior_hash:
        raise ValueError("prior_ledger_digest_mismatch")
    manifest_path=archive_root/"evidence/2026-11-21_22/ARCHIVE_MANIFEST.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema")!="kyoto_encrypted_evidence_archive.v1":
        raise ValueError("archive_schema_unknown")
    if set(manifest["source_runs"]["failure"])!=REQUIRED_RUNS:
        raise ValueError("historic_failure_runs_incomplete")
    if manifest["source_runs"]["all12"]!=44966013490 or manifest["source_runs"]["g03"]!=44966654858:
        raise ValueError("successful_source_run_mismatch")
    files=manifest.get("files",[])
    if len(files)!=18 or len(set(x["path"] for x in files))!=18:
        raise ValueError("archive_file_count_or_duplicates")
    for item in files:
        path=item["path"]
        if not path.startswith(ARCHIVED_SOURCE_ROOT) or ".." in Path(path).parts:
            raise ValueError("archive_path_outside_dedicated_prefix")
        exact=archive_root/path
        if not exact.is_file() or exact.is_symlink():
            raise ValueError("archived_file_missing:"+path)
        raw=exact.read_bytes()
        if _hash(raw)!=item["sha256"] or len(raw)!=item["size"]:
            raise ValueError("archived_source_byte_difference:"+path)
        if path.endswith(".html") or path.endswith(".htm"):
            raise ValueError("plaintext_archive_forbidden")
    for family in FAMILIES:
        count=previous["counts"][family]
        if sum(count.values())!=12:
            raise ValueError("previous_family_count_inconsistent:"+family)
    if previous["counts"]["racecard_original"]["ORIGINAL_VERIFIED"]!=12:
        raise ValueError("prior_real_12_source_not_proven")
    if previous["counts"]["roster"]["STRUCTURED_VERIFIED"]!=12:
        raise ValueError("prior_12_g03_not_proven")
    unresolved=[
        family for family in FAMILIES if previous["counts"][family]["STRUCTURED_VERIFIED"]==0
        and previous["counts"][family]["ORIGINAL_VERIFIED"]==0
    ]
    expected=list(PREFLIGHT_FAMILIES[2:])+list(AFTER_RACE_FAMILIES)
    if unresolved!=expected:raise ValueError("unresolved_family_set_changed")
    rows=[]
    for day in DAYS:
        for race in range(1,13):
            for family in FAMILIES:
                rows.append({"race_day":day,"race":race,"family":family,
                             "status":"AWAITING_REAL_SAME_DAY_OFFICIAL_EVIDENCE",
                             "phase":"POST_RESULT" if family in AFTER_RACE_FAMILIES else "PRE_START",
                             "source_url":None,"original_sha256":None,
                             "captured_at_utc":None,"parser_version":None,
                             "recovery_from_prior":"USE_VALIDATED_METHOD_NOT_OLD_RACE_URL"})
    result={"schema":"kyoto_next_week_evidence_driven_capture_readiness.v1",
            "days":list(DAYS),"venue":"KYOTO_ONLY_IF_OFFICIAL_MEETING_CONFIRMED",
            "source_evidence_run":44966013490,
            "parser_replay_run":44966654858,
            "archived_failure_runs":sorted(REQUIRED_RUNS),
            "prior_ledger_sha256":prior_hash,
            "archived_evidence_files":len(files),
            "previously_proven":["12R_PC_SP_OFFICIAL_ORIGINAL_BYTES",
                                 "12R_G03_ROSTER_AND_START_REAL_REPLAY"],
            "unresolved_prior_data_families":unresolved,
            "required_now":[
                "VERIFY_OFFICIAL_20261128_AND_20261129_KYOTO_MEETING_EXISTS",
                "FRESH_SAME_DAY_PC_AND_APP_SP_NAVIGATION_NO_URL_SYNTHESIS",
                "PROVE_ACTUAL_12R_SOURCE_SHA_UTC_BEFORE_START",
                "PROVE_12R_ROSTERS_HORSE_IDS_AND_HISTORY",
                "PROVE_REAL_QUINELLA_AND_BRACKET_QUINELLA_ODDS_AT_CAPTURE_TIME",
                "PROVE_TRACK_MOISTURE_AND_CUSHION_SOURCE_TIME",
                "FREEZE_PRE_START_PREDICTION_AND_PAPER_TRADE_ONLY_AFTER_PROOF",
                "GET_OFFICIAL_RESULT_AND_PAYOUT_POST_RACE",
                "SAVE_FAILURE_AND_SUCCESS_IN_DEPENDENCY_INDEPENDENT_ARCHIVE",
                "EVALUATE_AND_TEST_ADAPTIVE_REPAIR_FOR_NEXT_DAY_BEFORE_RELEASE"
            ],
            "source_provenance_invariant":"REAL_OFFICIAL_BYTES_HASH_UTC_AND_RACE_ID",
            "known_unfixed_automation_issue":87,
            "unreviewed_auto_patch_execution_prohibited":True,
            "must_revalidate_daily_url":True,
            "old_nov22_CNAME_REUSE_FOR_NEW_DAY_FORBIDDEN":True,
            "scheduled_start_and_recovery_experiment_verified":False,
            "actual_next_weekend_data_captured":False,
            "next_week_end_to_end_GO":False,
            "prediction_ready":False,
            "target_cells":rows}
    content=json.dumps(result,ensure_ascii=False,sort_keys=True,
                       separators=(",",":")).encode()
    result["content_sha256"]=_hash(content)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive-root",type=Path,required=True)
    p.add_argument("--ledger",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=prepare(a.archive_root,json.loads(a.ledger.read_text(encoding="utf-8")))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n",
                     encoding="utf-8")
    print("NEXT_WEEKEND_TARGET_EVIDENCE_CELLS="+str(len(result["target_cells"])))
    print("LAST_WEEKENDFALLBACK_EVIDENCE_FILES="+str(result["archived_evidence_files"]))
    print("NEXT_WEEKEND_PREPARATION_READY_AS_EVIDENCE_ONLY")
    print("NEXT_WEEKEND_LIVE_E2E_GO=FALSE")
    print("DETERMINISTIC_PLAN_SHA256="+result["content_sha256"])

if __name__=="__main__":main()
