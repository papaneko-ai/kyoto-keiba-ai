"""Atomic, immutable local archive of independently validated JRA odds originals.
Never writes the Streamlit app, Turso database or prediction ledger.
"""
from dataclasses import dataclass
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit
import os,json
class SnapshotArchiveError(ValueError):pass
HOSTS={"PC":{"jra.jp","www.jra.go.jp"},"SP":{"sp.jra.jp"}}
MARKETS={"quinella","bracket_quinella"}

def aware_utc(timestamp):
    if not isinstance(timestamp,str):raise SnapshotArchiveError("timestamp_missing")
    try:dt=datetime.fromisoformat(timestamp.replace("Z","+00:00"))
    except ValueError as e:raise SnapshotArchiveError("invalid_timestamp") from e
    if dt.tzinfo is None or dt.utcoffset() is None:raise SnapshotArchiveError("timezone_required")
    return dt.astimezone(timezone.utc)

def validate_receipt(record,raw,*,race_start_utc):
    if record.get("channel") not in HOSTS or record.get("market") not in MARKETS:raise SnapshotArchiveError("invalid_channel_or_market")
    if record.get("source_phase")!="LIVE_PRE_RACE":raise SnapshotArchiveError("not_live_phase")
    if not record.get("official_race_identity_verified"):raise SnapshotArchiveError("race_identity_missing")
    if record.get("source_sha256")!=sha256(raw).hexdigest() or record.get("source_bytes")!=len(raw) or not raw:raise SnapshotArchiveError("source_original_mismatch")
    u=urlsplit(record.get("source_url",""))
    if u.scheme!="https" or u.hostname not in HOSTS[record["channel"]] or u.path!="/JRADB/accessO.html":raise SnapshotArchiveError("unexpected_official_url")
    start=aware_utc(race_start_utc)
    stamp=aware_utc(record.get("captured_at_utc"))
    if stamp>=start:raise SnapshotArchiveError("late_source")
    if record.get("usage")=="PAPER_TRADE" and stamp>=start-timedelta(minutes=10):raise SnapshotArchiveError("paper_trade_cutoff_passed")
    if "最終オッズ".encode("cp932") in raw or "今週のオッズは未発表です".encode("cp932") in raw:raise SnapshotArchiveError("nonlive_original")
    if record.get("market_integrity_state")!="VALIDATED_MARKET_SOURCE":raise SnapshotArchiveError("market_gate_missing")
    race=record.get("race_id")
    if not isinstance(race,str) or not race or not race.replace("-","").replace("_","").isalnum():raise SnapshotArchiveError("invalid_race_id")
    if not isinstance(record.get("market_pair_count"),int) or record["market_pair_count"]<1:raise SnapshotArchiveError("missing_market_pairs")
    return True

def freeze_once(directory,record,raw,*,race_start_utc):
    validate_receipt(record,raw,race_start_utc=race_start_utc)
    target=Path(directory);target.mkdir(parents=True,exist_ok=True)
    key=f"{record['race_id']}_{record['channel']}_{record['market']}"
    original=target/(key+".html");receipt=target/(key+".json")
    canonical=(json.dumps(record,sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n").encode("utf8")
    if original.exists() or receipt.exists():
        if original.exists() and receipt.exists() and original.read_bytes()==raw and receipt.read_bytes()==canonical:
            return {"state":"ALREADY_FROZEN","original_sha256":record["source_sha256"]}
        raise SnapshotArchiveError("immutable_source_conflict")
    for path,data in ((original,raw),(receipt,canonical)):
        with NamedTemporaryFile(dir=target,prefix=".pending-",delete=False) as tmp:
            tmp.write(data);tmp.flush();os.fsync(tmp.fileno());temporary=Path(tmp.name)
        try:os.link(temporary,path)
        except FileExistsError as e:raise SnapshotArchiveError("immutable_source_conflict") from e
        finally:temporary.unlink(missing_ok=True)
    return {"state":"FROZEN","original_sha256":record["source_sha256"]}
