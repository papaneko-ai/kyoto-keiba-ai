"""Independent one-request cushion capture, original-bound replay and encryption.
Not a predictor or replacement for the existing PC/SP collection. The caller
must schedule this separately from the existing critical source budget.
"""
import argparse,json,os,re,tempfile
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path
from urllib.request import build_opener
from diagnostics.kyoto_impl36_official_cushion import URL,parse_official,utc,JST
from diagnostics.kyoto_nov15_two_original_observer import _read,NoRedirect
from diagnostics.kyoto_nov15_encrypted_evidence import encrypt_evidence,DAY

DAYS=("20261128","20261129")
REPO="papaneko-ai/kyoto-keiba-ai"
SCHEMA="kyoto_impl36_cushion_capture.v1"
ORIGINAL="g05_official_cushion_fragment.html"
MAX=1_500_000

def window(day,stamp):
    t=utc(stamp)
    return day in DAYS and t.astimezone(JST).strftime("%Y%m%d")==day and 0<=t.hour<8

def capture(root,day,fetch,clock):
    root=Path(root)
    before=utc(clock()).isoformat()
    if not window(day,before) or root.exists() or root.is_symlink():
        raise ValueError("capture_window_or_root")
    root.mkdir()
    receipt={"schema":SCHEMA,"day":day,"source_url":URL,"requested_at_utc":before,
             "state":"REQUEST_FAILED","request_count":1,"prediction_ready":False}
    try:
        raw=fetch(URL)
        stamp=utc(clock()).isoformat()
        receipt["captured_at_utc"]=stamp
        if type(raw) is not bytes or not 0<len(raw)<=MAX:
            raise ValueError("raw_size")
        (root/ORIGINAL).write_bytes(raw)
        receipt.update(source_sha256=sha256(raw).hexdigest(),bytes=len(raw),state="RAW_SAVED_NOT_PARSED")
        if not window(day,stamp) or utc(stamp)<utc(before):
            raise ValueError("capture_window_or_time_order")
        receipt["observation"]=parse_official(raw,day,URL,stamp)
        receipt["state"]="OFFICIAL_ORIGINAL_PARSED"
    except Exception as exc:
        receipt["error_class"]=type(exc).__name__
    (root/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf8")
    return receipt

def replay(root,day,cutoff_utc=None):
    root=Path(root)
    try:
        if root.is_symlink() or not root.is_dir():return None
        rp=root/"receipt.json"; op=root/ORIGINAL
        if any(p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=MAX for p in (rp,op)):return None
        stored=json.loads(rp.read_text(encoding="utf8"))
        if (stored["schema"]!=SCHEMA or stored["day"]!=day or stored["source_url"]!=URL or
            stored["state"]!="OFFICIAL_ORIGINAL_PARSED" or stored["request_count"]!=1 or
            stored["prediction_ready"] is not False):return None
        requested=utc(stored["requested_at_utc"]);captured=utc(stored["captured_at_utc"])
        if not window(day,requested.isoformat()) or not window(day,captured.isoformat()) or requested>captured:return None
        raw=op.read_bytes()
        obs=parse_official(raw,day,URL,captured.isoformat())
        if stored["source_sha256"]!=obs["source_sha256"] or stored["bytes"]!=len(raw) or stored["observation"]!=obs:return None
        if cutoff_utc is not None and not captured<utc(cutoff_utc):return None
        return obs
    except (OSError,ValueError,TypeError,KeyError,AttributeError):return None

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--day",required=True,choices=DAYS)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    repo=os.environ.get("GITHUB_REPOSITORY","");rid=os.environ.get("GITHUB_RUN_ID","");key=os.environ.get("ARCHIVE_KEY","")
    now=lambda:datetime.now(timezone.utc).isoformat()
    if (repo!=REPO or not rid.isdigit() or DAY!=a.day or os.environ.get("KYOTO_TARGET_DAY")!=a.day
        or os.environ.get("KYOTO_CUSHION_HTTP_APPROVED")!="YES"
        or os.environ.get("GITHUB_EVENT_NAME") not in ("schedule","workflow_dispatch","workflow_run")
        or not re.fullmatch(r"[a-fA-F0-9]{64}",key) or not window(a.day,now())):
        raise ValueError("cushion_live_guard_no_http")
    client=build_opener(NoRedirect())
    with tempfile.TemporaryDirectory(prefix="kyoto_cushion_") as d:
        raw=Path(d)/"raw"
        r=capture(raw,a.day,lambda url:_read(client,url),now)
        encrypt_evidence(raw,a.out,key_hex=key,repo=repo,run_id=rid)
    print(json.dumps({"day":a.day,"state":r["state"],"requests":r["request_count"],"prediction_ready":False}))
if __name__=="__main__":main()
