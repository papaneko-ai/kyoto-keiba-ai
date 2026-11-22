"""Discover exact on-page PC odds POST action from real Nov22 12R originals.

Uses the established frozen JRA parser. No network and no token synthesis.
"""
import hashlib,io,json,os,re,tarfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from diagnostics.jra_one_shot_market_capture import exact_odds_action,SourceChainError

AAD=b"kyoto-nov22-observed-official-all12-source-only"
def main():
    key=os.environ.get("KYOTO_JRA_ARCHIVE_AES256_HEX","")
    if not re.fullmatch(r"[0-9a-fA-F]{64}",key):raise RuntimeError("archive_key_missing")
    b=(Path("nov22_all12_source")/"originals_all12.tar.gz.aesgcm").read_bytes()
    raw=AESGCM(bytes.fromhex(key)).decrypt(b[:12],b[12:],AAD)
    with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as tar:
        members={m.name:tar.extractfile(m).read(1_500_001)
                 for m in tar.getmembers() if m.isfile()}
    receipt=json.loads(members["receipt.json"])
    results={};verified=0
    for n in range(1,13):
        name=f"r{n:02d}_pc_official_racecard.html"
        meta=receipt["races"][str(n)].get("PC",{})
        if name not in members:
            results[str(n)]={"state":"PC_RAW_ABSENT"}
            continue
        data=members[name]
        if hashlib.sha256(data).hexdigest()!=meta["sha256"]:
            raise RuntimeError("original_sha_mismatch")
        try:
            token=exact_odds_action(data,"PC")
            verified+=1
            results[str(n)]={"state":"EXACT_OFFICIAL_PC_ODDS_ACTION_OBSERVED",
                             "cname":token,"source_url":meta["observed_official_url"],
                             "source_sha256":meta["sha256"],
                             "source_utc":meta["captured_at_utc"],
                             "market_prices_verified":False}
        except Exception as exc:
            results[str(n)]={"state":"PC_MARKET_ACTION_NOT_OBSERVED",
                             "error_class":type(exc).__name__,
                             "market_prices_verified":False}
    report={"schema":"kyoto_nov22_real_official_pc_odds_action_inventory.v1",
            "day":"20261122","prediction_ready":False,
            "actual_market_prices_verified":False,"races":results}
    target=Path("nov22_odds_actions")
    target.mkdir()
    (target/"observed_official_actions.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("REAL_OFFICIAL_PC_ODDS_ACTIONS="+str(verified)+"/12")
    print("MARKET_ACTION_STATES="+json.dumps({n:v["state"] for n,v in results.items()},sort_keys=True))
    print("NO_JRA_HTTP;NO_GUESSED_MARKET")
if __name__=="__main__":main()
