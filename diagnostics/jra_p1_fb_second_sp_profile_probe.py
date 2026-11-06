"""One bounded second SP profile observation from a frozen official SP racecard link.
No URL guessing, no retries, no P1 verified-count increment or production use.
"""
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from diagnostics.jra_p1_sp_profile_offline import parse
ROOT=Path("docs/diagnostics/jra_p1_fb_offline_20261106")
LINKS=ROOT/"sp_11r_profile_links.json"
CUTOFF=datetime(2026,11,7,tzinfo=timezone.utc)
NAME="エティエンヌ"
def now():return datetime.now(timezone.utc)
def preflight():
    source=json.loads(LINKS.read_text(encoding="utf8"))
    links=[x for x in source["links"] if x["horse_name"]==NAME]
    if len(links)!=1 or source["source_sha256"]!="de806dc0a9977a41ffd2a795a5e6cda485fb243e26fbf8eb56d932326986ba54":
        raise ValueError("sp_roster_link_unproven")
    url=links[0]["url"];u=urlsplit(url)
    if u.scheme!="https" or u.hostname!="sp.jra.jp" or u.path!="/JRADB/accessU.html" or not u.query.startswith("CNAME=sj01ude"):
        raise ValueError("untrusted_sp_url")
    if (ROOT/"sp_profile_second_receipt.json").exists():raise ValueError("already_attempted_do_not_repeat")
    return url
def capture(out,opener=urlopen,clock=now):
    url=preflight()
    folder=Path(out);folder.mkdir(parents=True,exist_ok=True)
    state={"schema":"p1_fb_second_official_sp_profile.v1","race":11,"number":2,
           "horse_name":NAME,"source_url":url,"state":"BLOCKED",
           "network_requests":0,"production_adoption":False,
           "prediction_ready":False,"training_ready":False}
    def persist():(folder/"receipt.json").write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    if clock()>=CUTOFF:
        state["reason"]="cutoff_expired_zero_http";persist();return state
    state["network_requests"]=1
    try:
        req=Request(url,headers={"User-Agent":"Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)","Accept":"text/html"},method="GET")
        with opener(req,timeout=20) as resp:
            raw=resp.read(1800001);code=resp.status;ct=resp.headers.get("Content-Type","");final=urlsplit(resp.geturl())
        stamp=clock()
        if (code!=200 or not 0<len(raw)<=1800000 or "html" not in ct.lower()
            or final.scheme!="https" or final.hostname!="sp.jra.jp"
            or final.path!="/JRADB/accessU.html" or stamp>=CUTOFF):
            raise ValueError("untrusted_response_or_cutoff")
        state["captured_at_utc"]=stamp.isoformat()
        state["source_sha256"]=hashlib.sha256(raw).hexdigest()
        state["source_bytes"]=len(raw)
        (folder/"sp_11r_horse02.html").write_bytes(raw)
        state["original_saved_before_parser"]=True
        persist()
        result=parse(raw,NAME)
        state["history_rows_total"]=result["history_rows_total"]
        state["prior_rows_count"]=len(result["prior_rows"])
        state["invalid_rows"]=result["invalid_rows"]
        state["nonfinish_events"]=len(result["nonfinish_rows"])
        state["administrative_events"]=result.get("administrative_events",[])
        state["state"]="SOURCE_PARSED" if not result["invalid_rows"] else "PARSER_INVALID_ROWS"
    except Exception as exc:
        state["state"]="BLOCKED"
        state["reason"]=type(exc).__name__+":"+str(exc)[:200]
    persist();return state
if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--out",required=True);a=ap.parse_args()
    print(json.dumps(capture(a.out),ensure_ascii=False))
