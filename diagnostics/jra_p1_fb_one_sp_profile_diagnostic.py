"""One official SP horse profile diagnostic; never automatic fallback."""
import json,hashlib,argparse
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from bs4 import BeautifulSoup

LINKS=Path("docs/diagnostics/jra_p1_fb_offline_20261106/sp_11r_profile_links.json")
CUTOFF=datetime(2026,11,7,tzinfo=timezone.utc)
EXPECTED="モンドプリューム"
def diagnose(out,opener=urlopen,clock=lambda:datetime.now(timezone.utc)):
    links=json.loads(LINKS.read_text(encoding="utf8"))["links"]
    matches=[x["url"] for x in links if x["horse_name"]==EXPECTED]
    if len(matches)!=1:raise ValueError("sp_roster_link_not_unique")
    url=matches[0];u=urlsplit(url)
    if u.scheme!="https" or u.hostname!="sp.jra.jp" or u.path!="/JRADB/accessU.html":raise ValueError("not_official_sp_link")
    folder=Path(out);folder.mkdir(parents=True,exist_ok=True)
    report={"schema":"p1_fb_sp_profile_diagnostic.v1","source_url":url,
            "horse_name":EXPECTED,"race":11,"horse_number":1,
            "requests":0,"prediction_ready":False,"training_ready":False}
    def save():(folder/"receipt.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    if clock()>=CUTOFF:
        report["state"]="CUTOFF_NO_HTTP";save();return report
    report["requests"]=1
    try:
        with opener(Request(url,headers={"User-Agent":"Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)","Accept":"text/html"},method="GET"),timeout=20) as response:
            raw=response.read(1800001);status=response.status;ct=response.headers.get("Content-Type","");final=urlsplit(response.geturl())
        stamp=clock()
        if status!=200 or not 0<len(raw)<=1800000 or "html" not in ct.lower() or final.hostname not in ("sp.jra.jp","app.jra.jp") or final.path!="/JRADB/accessU.html" or stamp>=CUTOFF:
            raise ValueError("sp_response_invalid_or_cutoff")
        report.update(captured_at_utc=stamp.isoformat(),source_sha256=hashlib.sha256(raw).hexdigest(),source_bytes=len(raw))
        (folder/"sp_11r_horse01.html").write_bytes(raw)
        report["original_saved_before_parser"]=True;save()
        soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
        text=soup.get_text(" ",strip=True)
        tables=soup.select("table")
        report.update(state="HTML_INSPECTED_NOT_PROFILE_PARSED",identity_in_visible_text=EXPECTED in text,
            title=soup.title.get_text(" ",strip=True) if soup.title else "",
            table_count=len(tables),
            table_shapes=[{"rows":len(t.select("tr")),"head":t.get_text(" ",strip=True)[:120]} for t in tables[:4]],
            first_250_chars=text[:250])
    except Exception as exc:
        report.update(state="SP_DIAGNOSTIC_BLOCKED",error=type(exc).__name__+":"+str(exc)[:150])
    save();return report
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args()
    print(json.dumps(diagnose(a.out),ensure_ascii=False))
