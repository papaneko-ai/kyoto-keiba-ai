"""Read-only *historical final* market status for Kyoto new mobile preview.

Never interprets a historical final payout as a pre-race quote, predicted
ticket, user's earnings or recorded virtual investment.
"""
import json,re
from pathlib import Path

RECEIPT=Path(__file__).resolve().parents[1]/"docs"/"diagnostics"/"kyoto_two_real_official_final_ui_receipt_20261112.json"
EXPECTED_SOURCE_ZIP="dad5f93f72b3b993ab96ef1a053561d60a84ad3c868b4d3b4f4b2dc72bb9f004"
EXPECTED_DB="bba8d8c69bd68a1747dfe3d360fa899959f876d716d931842c32d932c2c62bc9"
EXPECTED={
 "2026-10-25-KYOTO-R10":{"source":"44d5480f668fca57293f67924e90d44294c9222c902cb187e594ed3087de54a2",
       "event":"1a00c115862825f5836dab9ea7a46507aaf15149ba8370428da570732283d3ad",
       "q":([10,12],15090),"b":([6,7],1540)},
 "2026-11-08-KYOTO-R11":{"source":"846c0f0b9a491f5375604ff11385f0f7e7f8c7a10960c717c2a381ff06667325",
       "event":"6a75026fd542de27c2c91af1d98e449c0ed1927b322d06932d87bc5917f4fd6c",
       "q":([8,11],1670),"b":([4,6],1330)}
}
class ActualFinalViewRejected(ValueError):pass
def view(path=RECEIPT):
    data=json.loads(Path(path).read_text(encoding="utf8"))
    if (data.get("schema")!="kyoto_actual_official_historical_final_ui_receipt.v1"
        or data.get("source_scope")!="TWO_JRA_ACTUAL_POSTRACE_FINALS_REPLAYED_FROM_ORIGINAL_HTML"
        or data.get("original_source_zip_sha256")!=EXPECTED_SOURCE_ZIP
        or data.get("official_sqlite_registry_sha256")!=EXPECTED_DB
        or data.get("original_postrace_runner_count")!=31
        or data.get("official_real_market_final_payout_count")!=4
        or data.get("independent_original_audit_result")!="SUCCESS"
        or data.get("independent_original_audit_run_id")!=43141831772
        or any(data.get(key) is not False for key in (
            "actual_pre_race_quinella_bracket_prices_authenticated",
            "real_virtual_paper_trades_precommitted","actual_paper_pnl_available",
            "f15_entire_lifecycle_accepted","f19_real_smartphone_accepted",
            "production_write_authorized"))):
        raise ActualFinalViewRejected("official_final_receipt_identity_or_scope_changed")
    entries=data.get("races")
    if type(entries) is not list or len(entries)!=2:
        raise ActualFinalViewRejected("expected_two_real_finals")
    rows=[]
    for item in entries:
        key=item.get("race_id")
        if key not in EXPECTED or key in {x["race_id"] for x in rows}:
            raise ActualFinalViewRejected("unexpected_real_race")
        e=EXPECTED[key]
        if item.get("source_sha256")!=e["source"] or item.get("event_sha256")!=e["event"]:
            raise ActualFinalViewRejected("official_source_or_event_changed")
        for k,exp in (("quinella",e["q"]),("bracket",e["b"])):
            o=item.get(k)
            if type(o) is not dict or o.get("pair")!=exp[0] or o.get("yen_per_100")!=exp[1]:
                raise ActualFinalViewRejected("payout_numbers_changed")
        rows.append({
            "race_id":key,
            "開催・レース":item["date"]+" 京都"+str(item["race"])+"R",
            "馬連の確定組番":"－".join(map(str,item["quinella"]["pair"])),
            "馬連払戻（100円）":item["quinella"]["yen_per_100"],
            "枠連の確定組番":"－".join(map(str,item["bracket"]["pair"])),
            "枠連払戻（100円）":item["bracket"]["yen_per_100"],
        })
    if set(x["race_id"] for x in rows)!=set(EXPECTED):
        raise ActualFinalViewRejected("historical_source_missing")
    return {"rows":rows,"source_kind":"ACTUAL_JRA_POSTRACE_FINAL_READ_ONLY",
      "real_virtual_investment_profit":None,
      "actual_prerace_market_odds_verified":False,
      "source_archive_sha256":EXPECTED_SOURCE_ZIP,
      "source_registry_sha256":EXPECTED_DB,
      "real_bet_execution_enabled":False}
