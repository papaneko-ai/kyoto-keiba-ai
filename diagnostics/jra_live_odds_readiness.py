"""One-stage JRA odds publication acceptance from real official PC/SP receipts.
Does not call JRA, guess CNAME, synthesize prices, or alter production.
"""
from datetime import date
from pathlib import Path
import argparse,json
from diagnostics.jra_market_integrity_gate import publication_status,normal_sales_open,utc

ROOT=Path("docs/diagnostics")
MENU=ROOT/"JRA_PC_SP_ODDS_MENU_20261106.json"
LINKS=ROOT/"JRA_ODDS_NAV_DISCOVERY_20261106.json"
DAY=date(2026,11,7)
EXPECTED="2026-11-07-KYOTO-11R"

def accept(menu,links):
    if menu.get("race")!=EXPECTED or links.get("race")!=EXPECTED:
        raise ValueError("source_race_identity_mismatch")
    records=menu.get("sources",[])
    navigations=links.get("sources",[])
    if len(records)!=2 or len(navigations)!=2:
        raise ValueError("must_have_both_independent_channels")
    output=[]
    for channel,hostname in (("PC","jra.jp"),("SP","sp.jra.jp")):
        pair=[x for x in records if x.get("channel")==channel]
        nav=[x for x in navigations if x.get("channel")==channel]
        if len(pair)!=1 or len(nav)!=1:
            raise ValueError("ambiguous_or_missing_channel")
        r=pair[0];n=nav[0]
        if r.get("status")!="OFFICIAL_MENU_CAPTURED" or n.get("status")!="NAVIGATION_AUDITED":
            raise ValueError("source_not_captured")
        if not r.get("content_sha256") or len(r["content_sha256"])!=64 or r.get("raw_bytes",0)<=0:
            raise ValueError("menu_original_provenance_missing")
        if n.get("odds_endpoints_visible",0)<1:
            raise ValueError("official_source_link_not_confirmed")
        if hostname not in r.get("source",""):
            raise ValueError("unexpected_origin")
        if "オッズ" not in r.get("title",""):
            raise ValueError("not_an_official_odds_menu")
        verdict=publication_status(
          race_day=DAY,checked_at_utc=r["captured_at_utc"],
          visible_text=r.get("visible_context",""),
          title=r["title"],official_verified=True)
        output.append({"channel":channel,"captured_at_utc":r["captured_at_utc"],
          "menu_sha256":r["content_sha256"],
          "official_link_sha256":n.get("sha256"),
          "status":verdict["state"],"usable":verdict["usable"],
          "market_matrix_captured":False,"market_price_verified":False})
    before=all(x["status"]=="NOT_PUBLISHED" for x in output)
    return {"schema_version":"jra_live_odds_readiness_gate.v1","race":EXPECTED,
      "normal_sale_start_utc":normal_sales_open(DAY).isoformat(),
      "source_channels":output,"both_not_published":before,
      "status":"OFFICIAL_UNPUBLISHED_CONFIRMED" if before else "NEEDS_REVIEW",
      "pre_race_odds_available":False,"market_capture_success":False,
      "historical_final_as_prerace_forbidden":True,
      "prediction_ready":False,"training_ready":False}

def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args()
    result=accept(json.loads(MENU.read_text(encoding="utf8")),
                  json.loads(LINKS.read_text(encoding="utf8")))
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
