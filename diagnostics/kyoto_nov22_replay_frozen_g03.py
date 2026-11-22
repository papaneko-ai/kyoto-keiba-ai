"""Replay the frozen proven G03 PC roster parser on actual Nov22 saved HTML.

Uses frozen development source via PYTHONPATH, not a new parser or JRA HTTP.
Source receipts and timestamps are authenticated independently.
"""
import hashlib,io,json,os,re,tarfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from diagnostics.kyoto_g03_all_races import parse

AAD=b"kyoto-nov22-observed-official-all12-source-only"

def main():
    root=Path("nov22_all12_source")
    key_hex=os.environ.get("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[0-9a-fA-F]{64}",key_hex):
        raise RuntimeError("archive_key_missing")
    blob=(root/"originals_all12.tar.gz.aesgcm").read_bytes()
    if hashlib.sha256(blob).hexdigest()!=(root/"ciphertext_sha256.txt").read_text().strip():
        raise RuntimeError("ciphertext_tampered")
    raw=AESGCM(bytes.fromhex(key_hex)).decrypt(
        blob[:12],blob[12:],AAD)
    files={}
    with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as tar:
        for item in tar.getmembers():
            if not item.isfile() or not (re.fullmatch(
                  r"r(0[1-9]|1[0-2])_(pc|sp)_official_racecard.html",item.name)
                    or item.name=="receipt.json"):
                raise RuntimeError("unknown_or_unsafe_member")
            files[item.name]=tar.extractfile(item).read(1_500_001)
    receipt=json.loads(files["receipt.json"])
    out={"schema":"kyoto_nov22_frozen_g03_on_actual_source.v1","day":"20261122",
         "market_prices_verified":False,"prediction_ready":False,"races":{}}
    proven=0
    for n in range(1,13):
        row=receipt["races"][str(n)].get("PC",{})
        name=f"r{n:02d}_pc_official_racecard.html"
        if name not in files:
            out["races"][str(n)]={"state":"PC_RAW_ABSENT_SP_SOURCE_PRESERVED"}
            continue
        raw=files[name]
        if hashlib.sha256(raw).hexdigest()!=row.get("sha256"):
            raise RuntimeError("pc_original_sha_disagrees")
        try:
            result=parse(raw,"20261122",n,row["observed_official_url"],row["captured_at_utc"])
            out["races"][str(n)]={
                "state":"G03_ROSTER_AND_START_PARSED_FROM_ACTUAL_ORIGINAL",
                "runner_count":result["runner_count"],
                "start_time_jst":result["start_time_jst"],
                "original_sha256":result["sha256"],
                "captured_at_utc":row["captured_at_utc"],
                "horse_profiles_observed":sum(
                   bool(h.get("profile_navigation")) for h in result["runners"]),
                "past_run_dates_observed":sum(
                   len(h.get("past_race_dates",[])) for h in result["runners"])}
            proven+=1
        except Exception as exc:
            out["races"][str(n)]={"state":"G03_SOURCE_PARSER_REJECTED",
                                  "error_class":type(exc).__name__,
                                  "reason":str(exc)[:240],
                                  "original_sha256":row["sha256"]}
    target=Path("nov22_frozen_g03_replay")
    target.mkdir()
    (target/"safe_race_parser_results.json").write_text(
        json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("REAL_NOV22_G03_RACES_PARSED="+str(proven)+"/12")
    print("G03_SOURCE_REPLAY_RESULT="+json.dumps({
        k:v["state"] for k,v in out["races"].items()},sort_keys=True))
    print("NO_JRA_HTTP;MARKET_PRICES_UNVERIFIED")
if __name__=="__main__":main()
