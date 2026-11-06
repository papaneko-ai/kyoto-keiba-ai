"""Follow exactly one official odds menu link per PC/SP using published doAction.
Menu discovery only. Never labels menu or historical final odds as pre-race odds.
"""
from datetime import datetime,timezone
from urllib.parse import urlsplit,urlencode
from urllib.request import Request,urlopen
from hashlib import sha256
from pathlib import Path
from bs4 import BeautifulSoup
import argparse,json,re,time

NAV=Path("docs/diagnostics/JRA_ODDS_NAV_DISCOVERY_20261106.json")
ACTION=re.compile(r"doAction\s*\(\s*['\"](/JRADB/accessO\.html)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)")
MAX_BYTES=1_000_000
MOBILE_UA="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
MARKERS=("馬連","枠連","オッズ","発売","京都","2026年11月7日")

def link_for_channel(record):
    found=set()
    for item in record["relevant_anchors"]:
        text=item.get("onclick","")
        match=ACTION.search(text)
        if match: found.add(match.group(2))
    if len(found)!=1:raise ValueError("ambiguous_official_odds_menu")
    result=found.pop()
    if not re.fullmatch(r"[ps]w15oli00/[0-9A-Za-z]{2}",result):
        raise ValueError("unexpected_official_menu_token")
    if (record["channel"]=="PC")!=(result.startswith("pw")):
        raise ValueError("mobile_desktop_token_mismatch")
    return result

def inspect(raw):
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    anchors=[]
    for a in soup.select("a"):
        label=a.get_text(" ",strip=True)
        onclick=a.get("onclick","")
        href=a.get("href","")
        if any(k in label+" "+onclick+" "+href for k in MARKERS) or "accessO.html" in onclick+" "+href:
            anchors.append({"label":label[:90],"href":href[:200],"onclick":onclick[:260]})
    text=soup.get_text(" ",strip=True)
    return {"title":soup.title.get_text(" ",strip=True) if soup.title else "",
            "anchor_count":len(anchors),"anchors":anchors[:55],
            "market_terms":{x:text.count(x) for x in MARKERS},
            "contains_no_sale_notice":any(z in text for z in ("発売前","発売しておりません","オッズはありません","オッズを表示できません")),
            "visible_context":text[-1200:]}
def run(folder):
    p=Path(folder);p.mkdir(parents=True,exist_ok=True)
    nav=json.loads(NAV.read_text(encoding="utf8"))
    rows=[]
    for index,source in enumerate(nav["sources"]):
        if index:time.sleep(1)
        channel=source["channel"]
        host="jra.jp" if channel=="PC" else "sp.jra.jp"
        result={"channel":channel,"status":"STARTED","captured_at_utc":datetime.now(timezone.utc).isoformat(),
                "market_phase":"NOT_YET_CLASSIFIED","pre_race_odds_verified":False,"training_ready":False}
        try:
            token=link_for_channel(source)
            req=Request(f"https://{host}/JRADB/accessO.html",
                data=urlencode({"cname":token}).encode("ascii"),
                headers={"User-Agent":MOBILE_UA if channel=="SP" else "Mozilla/5.0",
                         "Referer":source["source"],"Accept":"text/html",
                         "Content-Type":"application/x-www-form-urlencoded"},method="POST")
            with urlopen(req,timeout=20) as response:
                raw=response.read(MAX_BYTES+1);status=response.status
                ct=response.headers.get("Content-Type","")
                final=urlsplit(response.geturl())
            if status!=200 or not 0<len(raw)<=MAX_BYTES or "html" not in ct.lower() or final.scheme!="https" or final.hostname not in ({host,"www.jra.go.jp"} if channel=="PC" else {host}):
                raise ValueError("not_allowed_official_menu_html")
            (p/f"{channel.lower()}_odds_menu.html").write_bytes(raw)
            summary=inspect(raw)
            result.update(status="OFFICIAL_MENU_CAPTURED",http_status=status,
                content_sha256=sha256(raw).hexdigest(),raw_bytes=len(raw),
                token_sha256=sha256(token.encode()).hexdigest(),**summary)
            # Absence of live numbers is not a networking failure.
            result["market_phase"]="MENU_ONLY_UNVERIFIED"
        except Exception as exc:
            result.update(status="FAILED",error=type(exc).__name__+":"+str(exc)[:200])
        rows.append(result)
    report={"schema_version":"jra_pc_sp_odds_menu_probe.v1",
        "race":"2026-11-07-KYOTO-11R","sources":rows,
        "prices_verified":False,"payout_as_input_prohibited":True,"training_ready":False}
    (p/"menus.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    return report
if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--out",default="odds_menus");a=ap.parse_args()
    d=run(a.out);print(json.dumps([{"channel":r["channel"],"status":r["status"],
      "title":r.get("title"),"anchor_count":r.get("anchor_count")} for r in d["sources"]],ensure_ascii=False))
