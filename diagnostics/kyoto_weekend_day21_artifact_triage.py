"""Read Day21 encrypted original artifacts and report factual Sunday repair evidence.

Do not use Actions job success or artifact existence as proof of JRA success.
Decrypted HTML is ephemeral and never included in the published triage report.
"""
from __future__ import annotations
import argparse,hashlib,json,os,tempfile
from datetime import datetime,timezone
from pathlib import Path
from diagnostics.kyoto_nov15_encrypted_evidence import decrypt_evidence

def _utc(s):
    try:
        t=datetime.fromisoformat(s.replace("Z","+00:00"))
        return t.utcoffset()==timezone.utc.utcoffset(None)
    except (ValueError,TypeError,AttributeError):
        return False

def assess_lane(root,*,day,channel,key,repo,run_id):
    root=Path(root)
    result={"channel":channel,"day":day,"state":"NO_ARTIFACT",
            "ciphertext_authenticated":False,
            "source_original_sha_utc_checked":False,
            "both_raw_market_originals_present":False,
            "official_live_market_accepted":False,
            "prediction_ready":False}
    if not root.is_dir() or root.is_symlink():
        return result
    safe=root/"safe_stop.json"
    if safe.is_file() and not safe.is_symlink():
        try:
            doc=json.loads(safe.read_text(encoding="utf8"))
            if not isinstance(doc,dict) or doc.get("race_day")!=day or doc.get("JRA_success") is not False:
                result["state"]="MALFORMED_SAFE_STOP"
            elif day in ("20261128","20261129"):
                # A safe-stop JSON is not authenticated proof of a skipped job.
                # Even a legacy zero claim needs independent step evidence.
                if (doc.get("state") in ("NO_SOURCE_HTTP_UNVERIFIED","NO_CAPTURE_OR_PRE_HTTP_STOP")
                    and doc.get("official_originals_authenticated") is False and type(doc.get("operational_credit")) is int
                    and doc["operational_credit"]==0 and not any((root/n).exists() for n in ("manifest.json","originals.tar.gz.aesgcm"))):
                    result["state"]="NO_SOURCE_HTTP_UNVERIFIED"
                    result["actual_jra_http_requests"]="UNKNOWN"
                else:
                    result["state"]="MALFORMED_SAFE_STOP"
            else:
                result["state"]="PRE_HTTP_SAFE_STOP_NO_SOURCE"
        except (ValueError,TypeError,OSError):
            result["state"]="MALFORMED_SAFE_STOP"
        return result
    if not (root/"manifest.json").is_file() or not (root/"originals.tar.gz.aesgcm").is_file():
        result["state"]="ENCRYPTED_ARTIFACT_INCOMPLETE"
        return result
    try:
        with tempfile.TemporaryDirectory(prefix="kyoto_day21_ephemeral_") as tmp:
            source=Path(tmp)/"raw"
            decrypt_evidence(root,source,key_hex=key,repo=repo,run_id=run_id)
            result["ciphertext_authenticated"]=True
            receipt=json.loads((source/"receipt.json").read_text(encoding="utf8"))
            if receipt.get("day")!=day:
                result["state"]="RAW_RECEIPT_DAY_MISMATCH"
                return result
            if receipt.get("schema")=="kyoto_archive_salvage.v1":
                result["state"]="PARTIAL_ARCHIVE_SALVAGED_NOT_SOURCE_VERIFIED"
                result["salvage_saved_originals"]=receipt.get("saved_originals",{})
                result["salvage_rejected_members"]=receipt.get("rejected_members",[])
                return result
            verification=source/"source_verification.json"
            if not verification.is_file():
                result["state"]="DECRYPTED_WITHOUT_POSTFLIGHT_RECORD"
                return result
            post=json.loads(verification.read_text(encoding="utf8"))
            if post.get("day")!=day or post.get("channel")!=channel:
                result["state"]="POSTFLIGHT_DAY_OR_CHANNEL_MISMATCH"
                return result
            rows=post.get("source_rows")
            if not isinstance(rows,list) or not rows:
                result["state"]="POSTFLIGHT_NO_SOURCE_ROWS"
                return result
            for row in rows:
                name=row.get("filename","")
                if (name not in {p.name for p in source.iterdir()} or
                    not (source/name).is_file() or (source/name).is_symlink() or
                    hashlib.sha256((source/name).read_bytes()).hexdigest()!=row.get("sha256") or
                    not _utc(row.get("captured_at_utc"))):
                    result["state"]="SOURCE_SHA_UTC_MISMATCH"
                    return result
            if channel=="SP" and day in ("20261128","20261129"):
                from diagnostics.kyoto_weekend_postflight import check_originals
                fresh=check_originals(source,day=day,channel=channel)
                if "sp_race_integrity" in fresh:
                    if fresh!=post:
                        result["state"]="SP_RACEWISE_POSTFLIGHT_MISMATCH"
                        return result
                    result["sp_race_integrity"]=fresh["sp_race_integrity"]
                    result["sp_racewise_partial_integrity"]=fresh["source_verified"] is not True
                    try:
                        from diagnostics.kyoto_impl31_sp_saved_roster_audit import assess_checked
                        result["sp_saved_roster_audit"]=assess_checked(source,day,fresh)
                    except (OSError,ValueError,KeyError,TypeError,AttributeError):
                        result["sp_saved_roster_audit_error"]="CONTENT_AUDIT_UNAVAILABLE"
                    if isinstance(receipt.get("sp_gap_plan"),dict):
                        try:
                            from diagnostics.kyoto_impl31_sp_gap_plan import feedback
                            result["sp_gap_feedback"]=feedback(receipt["sp_gap_plan"],receipt,fresh,day,run_id)
                        except (ValueError,KeyError,TypeError,AttributeError):
                            result["sp_gap_feedback_error"]="INVALID_PLAN_OR_EVIDENCE"
            result["source_original_sha_utc_checked"]=True
            if day=="20261129":
                try:
                    from diagnostics.kyoto_impl31_improvement_evaluation import receipt as validate_policy
                    policy=source/"nextday_applied_policy.json"
                    if policy.is_file() and not policy.is_symlink() and policy.stat().st_size<=8192:
                        result["applied_policy"]=validate_policy(json.loads(policy.read_text()),channel)
                except (OSError,ValueError,KeyError,TypeError,AttributeError):
                    result["applied_policy_error"]="INVALID_OR_MISSING_POLICY_RECEIPT"
            if channel=="PC":
                # Use decrypted source bytes directly; no summary flag is
                # promoted to a day-wide source proof.
                if day in ("20261128","20261129"):
                    try:
                        from diagnostics.kyoto_impl30_day_coverage import extract_slot
                        result["day_coverage_slot"]=extract_slot(source,day,run_id)
                    except Exception as exc:
                        result["day_coverage_error"]=type(exc).__name__
                c11_file=source/"c11_per_family_source_proof.json"
                result["c11_family_evidence_state"]="MISSING_C11_RECEIPT"
                result["c11_verified_counts"]={}
                if c11_file.is_file() and not c11_file.is_symlink():
                    from diagnostics.kyoto_impl25_c11_per_family_proof import assess as reassess_c11
                    recomputed=reassess_c11(source,day)
                    stored=json.loads(c11_file.read_text(encoding="utf8"))
                    if stored==recomputed:
                        result["c11_family_evidence_state"]="RECOMPUTED_SOURCE_SHA_UTC_MATCH"
                        result["c11_verified_counts"]={
                            key:recomputed[key] for key in (
                                "g03_verified_races","g04_verified_profiles",
                                "g05_bound_races","g06_paired_market_races_locally_verified")}
                    else:
                        result["c11_family_evidence_state"]="SAVED_C11_CANNOT_BE_REVALIDATED"
            markets=(("official_quinella_odds.html","official_bracket_quinella_odds.html") if channel=="PC"
                else ("official_sp_quinella_odds.html","official_sp_bracket_quinella_odds.html"))
            result["both_raw_market_originals_present"]=all((source/name).is_file() for name in markets)
            # Artifact presence alone is insufficient: the postflight receipt
            # must independently hash and UTC-bind *each* market original.
            verified_names={row["filename"] for row in rows}
            result["both_raw_market_originals_sha_utc_verified"]=(
                result["both_raw_market_originals_present"] and
                all(name in verified_names for name in markets))
            result["state"]=(
                "RAW_BOTH_MARKETS_PRESERVED_NOT_AUTHENTICATED"
                if result["both_raw_market_originals_sha_utc_verified"] else
                "MARKET_ORIGINALS_PRESENT_BUT_NOT_SHA_UTC_VERIFIED"
                if result["both_raw_market_originals_present"] else
                "VALID_ORIGINALS_WITH_INCOMPLETE_MARKETS")
    except (OSError,ValueError,KeyError,TypeError,Exception) as exc:
        # The public triage report contains only exception classes, never
        # decrypted originals, URL query tokens or secrets.
        result["state"]="DECRYPT_OR_SOURCE_EVIDENCE_REJECTED"
        result["error_class"]=type(exc).__name__
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--day",required=True,choices=("20261121","20261122","20261128","20261129"))
    p.add_argument("--run-id",required=True)
    p.add_argument("--pc",type=Path,required=True)
    p.add_argument("--sp",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    if args.run_id=="0":
        lanes={c:{"channel":c,"state":"NO_DAY_RUN","official_live_market_accepted":False}
               for c in ("PC","SP")}
    else:
        lanes={c:assess_lane(root,day=args.day,channel=c,
               key=os.getenv("ARCHIVE_KEY",""),repo=os.environ["GITHUB_REPOSITORY"],
               run_id=args.run_id) for c,root in (("PC",args.pc),("SP",args.sp))}
    report={"schema":"kyoto_actual_day21_evidence_triage.v1","day":args.day,
            "run_id":args.run_id,"lanes":lanes,
            "proves_full_live_jra_market_success":False,
            "requires_day22_human_source_review":True,
            "raw_source_uploaded":False}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
    print("DAY21_ACTUAL_SOURCE_TRIAGE="+",".join(x["state"] for x in lanes.values()))

if __name__=="__main__":
    main()
