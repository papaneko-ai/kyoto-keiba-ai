"""Replay 185 actual encrypted profile originals through frozen G04 history parser.

Actual 2026-11-22 12R JRA source HTML and all individual profile SHA/UTC
are joined using independently observed URL ordering. No JRA HTTP.
After-race capture is NEVER a certified prerace horse snapshot.
"""
import hashlib,io,json,os,re,tarfile
from pathlib import Path
from datetime import date,datetime,timedelta,timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from diagnostics.kyoto_nov22_horse_profile_followup import plan,source_cards
from diagnostics.jra_prior_form_offline import parse_horse_history
from diagnostics.kyoto_g04_all_horse_profiles import _metadata
from diagnostics.kyoto_g05_official_track import parse_kyoto_track,KYOTO_TRACK_PAGE
DAY="20261122"
AAD_P=b"kyoto-nov22-observed-profile-history-originals-v1"
AAD_T=b"kyoto-nov22-official-ground-source-only"
def archived(name,digest,aad,key):
    base=Path("real_source")/name
    b=(base/("horse_profiles.tar.gz.aesgcm" if name=="profile" else "ground_original.tar.gz.aesgcm")).read_bytes()
    if hashlib.sha256(b).hexdigest()!=(base/digest).read_text().strip():raise ValueError("AES_BUNDLE_HASH_MISMATCH")
    raw=AESGCM(key).decrypt(b[:12],b[12:],aad)
    out={}
    with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as t:
        for m in t.getmembers():
            if not m.isfile() or "/" in m.name or ".." in m.name or m.name in out:raise ValueError("UNTRUSTED_TAR")
            out[m.name]=t.extractfile(m).read(1_500_001)
    return out
def main():
    hexkey=os.environ.get("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[0-9a-fA-F]{64}",hexkey):raise ValueError("ARCHIVE_KEY_REQUIRED")
    key=bytes.fromhex(hexkey)
    orig,cardreceipt=source_cards(key)
    queue=plan(orig)
    bundle=archived("profile","ciphertext_sha256.txt",AAD_P,key)
    receipt=json.loads(bundle["profile_receipt.json"])
    recorded=receipt.get("items",[])
    if len(queue)!=185 or len(recorded)!=185:raise ValueError("PROFILE_QUEUE_OR_RECEIPT_MISMATCH")
    result={"schema":"kyoto_nov22_real_185_profile_history_replay.v1",
            "day":DAY,"verified_saved_originals":0,"profile_metadata_parsed":0,
            "prior_history_parsed":0,"prior_finish_rows_total":0,
            "rejected_count":0,"no_history_valid_count":0,
            "all_are_pre_race_snapshots":False,"prerace_training_approved":False,
            "items":[]}
    # Historical-only cutoff after the target date. The parser excludes every
    # Nov22 and later event; this is NOT a historical proof of original as-of.
    cutoff=datetime(2026,11,23,0,0,tzinfo=timezone.utc)
    for i,(q,record) in enumerate(zip(queue,recorded),1):
        if record.get("priority_index")!=i or hashlib.sha256(q["url"].encode()).hexdigest()!=record.get("observed_profile_url_sha256"):
            raise ValueError("ACTUAL_OBSERVED_PROFILE_URL_QUEUE_CONFLICT")
        filename=f"profile_{i:03d}.html"
        original=bundle.get(filename)
        row={"priority_index":i,"source_races":q["races"],
             "source_sha256":record.get("sha256"),
             "observed_name_match":record.get("visible_name_match"),
             "state":"NOT_VERIFIED"}
        if original is None or hashlib.sha256(original).hexdigest()!=record.get("sha256"):
            row.update(state="SOURCE_MISSING_OR_SHA_MISMATCH")
            result["rejected_count"]+=1
            result["items"].append(row)
            continue
        result["verified_saved_originals"]+=1
        try:
            timestamp=datetime.fromisoformat(record["captured_at_utc"].replace("Z","+00:00"))
            if timestamp.tzinfo is None:raise ValueError("CAPTURE_UTC_MISSING")
            horse=q["horse_name_observed"]
            features=_metadata(original,horse)
            result["profile_metadata_parsed"]+=1
            parsed=parse_horse_history(original,
                source_url=q["url"],fetched_at_utc=timestamp,
                prediction_cutoff_utc=cutoff,
                target_date=date(2026,11,22),
                expected_horse_name=horse,allow_verified_no_history=True)
            if parsed["invalid_rows"]:
                raise ValueError("HISTORY_INVALID_ROWS_"+str(len(parsed["invalid_rows"])))
            if any(x.get("date","")>=DAY[:4]+"-"+DAY[4:6]+"-"+DAY[6:] for x in parsed["prior_rows"]):
                raise ValueError("SAME_DAY_FUTURE_HISTORY_LEAK")
            row.update(state="OFFLINE_PRIOR_HISTORY_PARSED_SOURCE_NOT_PRERACE",
                       historical_prior_races=len(parsed["prior_rows"]),
                       excluded_rows=len(parsed["excluded_rows"]),
                       nonfinish_rows=len(parsed["nonfinish_rows"]),
                       profile_source_sha256=parsed["source_sha256"],
                       historical_only=True,
                       horse_id_permanent_verified=False)
            result["prior_history_parsed"]+=1
            result["prior_finish_rows_total"]+=len(parsed["prior_rows"])
            if parsed.get("profile_history_table_absent"):
                result["no_history_valid_count"]+=1
        except Exception as exc:
            row.update(state="SOURCE_PARSER_REJECTED",
                       failure_class=type(exc).__name__,
                       reason=str(exc)[:140])
            result["rejected_count"]+=1
        result["items"].append(row)
    track=archived("track","source_sha256.txt",AAD_T,key)
    tr=json.loads(track["source_receipt.json"])
    data=track.get("official_kyoto_track.html")
    if data is None or hashlib.sha256(data).hexdigest()!=tr.get("sha256"):
        raise ValueError("TRACK_ORIGINAL_SHA_INVALID")
    result["track"]=parse_kyoto_track(data,DAY,KYOTO_TRACK_PAGE,tr["captured_at_utc"])
    result["track"]["verified_same_day_publication_not_prerace"]=False
    out=Path("real_history_track_report");out.mkdir()
    (out/"independent_actual_185_history_and_ground.json").write_text(
        json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("REAL_PROFILE_METADATA_PARSED="+str(result["profile_metadata_parsed"])+"/185")
    print("REAL_PRIOR_HISTORY_PARSED="+str(result["prior_history_parsed"])+"/185")
    print("REAL_HISTORICAL_PRIOR_FINISH_ROWS="+str(result["prior_finish_rows_total"]))
    print("REAL_PROFILE_REJECTED="+str(result["rejected_count"]))
    print("REAL_OFFICIAL_TRACK_STATE="+result["track"]["state"])
    print("POSTCAPTURE_ASOF_PRERACE_NOT_CERTIFIED")
if __name__=="__main__":main()
