"""Offline numerical matrix replay against actual encrypted 2026-11-22 JRA markets.

Uses the existing strict matrix parser; lack of roster/frame verification
remains an explicitly separate acceptance gate for bracket quinella.
Nothing here proves a pre-race snapshot or allows real money wagers.
"""
import hashlib,io,json,os,re,tarfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from diagnostics.jra_odds_matrix_parser import parse_matrix
AAD=b"kyoto-nov22-actual-odds-source-remainder-v1"
def main():
    root=Path("nov22_market_source")
    cipher=(root/"market_followup.tar.gz.aesgcm").read_bytes()
    if hashlib.sha256(cipher).hexdigest()!=(root/"encrypted_sha256.txt").read_text().strip():
        raise RuntimeError("CIPHERTEXT_SHA_MISMATCH")
    key=os.environ.get("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[a-fA-F0-9]{64}",key):raise RuntimeError("KEY_MISSING")
    raw=AESGCM(bytes.fromhex(key)).decrypt(cipher[:12],cipher[12:],AAD)
    files={}
    with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as t:
        for m in t.getmembers():
            if not m.isfile() or not (m.name=="source_receipt.json" or re.fullmatch(
                   r"r(0[1-9]|1[0-2])_(pc|sp)_(odds_menu|quinella_original|bracket_quinella_original)\.html",m.name)):
                raise RuntimeError("UNTRUSTED_ARCHIVE_FILE")
            files[m.name]=t.extractfile(m).read(1500001)
    receipt=json.loads(files["source_receipt.json"])
    g03=json.loads(Path("nov22_g03/safe_race_parser_results.json").read_text())
    result={"schema":"kyoto_20261122_real_market_numerical_replay.v1",
            "day":"20261122","source_market_run":44983969532,
            "pre_start_quote_certified":False,
            "bracket_roster_eligible_pairs_independently_verified":False,
            "races":{}}
    valid={"quinella":0,"bracket_quinella":0}
    for race in range(1,13):
        row={}
        expected=g03["races"][str(race)].get("runner_count")
        if type(expected)!=int or not 2<=expected<=18:
            raise RuntimeError("G03_RACE_ROSTER_COUNT_MISSING")
        for market in ("quinella","bracket_quinella"):
            record=None
            for ch in ("pc","sp"):
                filename=f"r{race:02d}_{ch}_{market}_original.html"
                if filename not in files:continue
                info=receipt["races"][str(race)][ch.upper()]["market_items"][market]
                original=files[filename]
                if hashlib.sha256(original).hexdigest()!=info["sha256"]:
                    raise RuntimeError("ORIGINAL_SHA_INVALID")
                record={"channel":ch.upper(),"original_sha256":info["sha256"],
                        "captured_at_utc":info["captured_at_utc"],
                        "state":"ORIGINAL_EXISTS_NUMERIC_UNVERIFIED"}
                try:
                    matrix=parse_matrix(original,market,expected_runners=expected if market=="quinella" else None)
                    record.update(state="NUMERICAL_MATRIX_STRUCTURALLY_PARSED",
                                  matrix_dimension=matrix["matrix_dimension"],
                                  pair_count=matrix["pair_count"],
                                  detected_final=matrix["historical_final_detected"])
                    valid[market]+=1
                except Exception as exc:
                    record.update(state="NUMERICAL_MATRIX_REJECTED",
                                  error_class=type(exc).__name__,
                                  reason=str(exc)[:100])
                break
            row[market]=record or {"state":"NO_MARKET_ORIGINAL"}
        result["races"][str(race)]=row
    target=Path("nov22_market_numeric_report");target.mkdir()
    (target/"market_numeric_replay.json").write_text(
        json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("ACTUAL_NUMERIC_QUINELLA_PARSER_OK="+str(valid["quinella"])+"/12")
    print("ACTUAL_NUMERIC_BRACKET_PARSER_OK="+str(valid["bracket_quinella"])+"/12")
    print("PRE_START_QUOTE_CERTIFIED_FALSE;BRACKET_ROSTER_ELIGIBILITY_UNVERIFIED")
if __name__=="__main__":main()
