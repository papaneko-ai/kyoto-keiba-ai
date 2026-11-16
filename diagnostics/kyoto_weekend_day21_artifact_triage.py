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
            if doc.get("race_day")==day and doc.get("JRA_success") is False:
                result["state"]="PRE_HTTP_SAFE_STOP_NO_SOURCE"
            else:
                result["state"]="MALFORMED_SAFE_STOP"
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
            result["source_original_sha_utc_checked"]=True
            markets=(("official_quinella_odds.html","official_bracket_quinella_odds.html") if channel=="PC"
                else ("official_sp_quinella_odds.html","official_sp_bracket_quinella_odds.html"))
            result["both_raw_market_originals_present"]=all((source/name).is_file() for name in markets)
            result["state"]=("RAW_BOTH_MARKETS_PRESERVED_NOT_AUTHENTICATED" if result["both_raw_market_originals_present"]
                  else "VALID_ORIGINALS_WITH_INCOMPLETE_MARKETS")
    except (OSError,ValueError,KeyError,TypeError,Exception) as exc:
        # The public triage report contains only exception classes, never
        # decrypted originals, URL query tokens or secrets.
        result["state"]="DECRYPT_OR_SOURCE_EVIDENCE_REJECTED"
        result["error_class"]=type(exc).__name__
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--day",required=True,choices=("20261121","20261122"))
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
