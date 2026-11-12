"""Independent 2 genuine JRA historical result and FINAL payout extraction.

Offline original bytes from known GitHub Actions archive only. Cross-check
official race/date, source SHA, top-two horse and frame numbers against actual
quinella & bracket payout pairs. This is NOT authentic historical pre-race odds,
pre-registered investments, or a prediction model performance measure.
"""
from __future__ import annotations
import hashlib
import io
import json
import re
import zipfile
from bs4 import BeautifulSoup
from diagnostics.jra_historical_two_day_result_import import import_two_days
from diagnostics.jra_historical_two_day_source_capture import KNOWN
from diagnostics.parse_jra_result_roster import extract_result_roster

ARCHIVE_SHA256="dad5f93f72b3b993ab96ef1a053561d60a84ad3c868b4d3b4f4b2dc72bb9f004"
class RealHistoricalPayoutRejected(ValueError):pass

def _digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,
        separators=(",",":"),allow_nan=False).encode()).hexdigest()

def _payout(text,market,following):
    matches=re.findall(r"(?<!\S)"+market+r"\s+(.+?)\s+"+following+r"(?=\s|$)",text)
    if len(matches)!=1:
        raise RealHistoricalPayoutRejected("ambiguous_or_missing_"+market)
    match=re.fullmatch(r"\s*(\d{1,2})-(\d{1,2})\s+([\d,]+)\s+円\s+\d+\s+番人気\s*",matches[0])
    if not match:
        raise RealHistoricalPayoutRejected("ambiguous_"+market+"_payout_fields")
    a,b,y=match.groups()
    a=int(a);b=int(b);yen=int(y.replace(",",""))
    limit=18 if market=="馬連" else 8
    if not 1<=a<=b<=limit or (market=="馬連" and a==b) or not 100<=yen<=20_000_000:
        raise RealHistoricalPayoutRejected("pair_or_payout_out_of_range")
    return {"pair":[a,b],"yen_per_100":yen}

def extract_real_two_race_payouts(archive):
    if type(archive) is not bytes or hashlib.sha256(archive).hexdigest()!=ARCHIVE_SHA256:
        raise RealHistoricalPayoutRejected("source_zip_sha256_mismatch")
    # Reuse earlier *actual-byte* archive+race/date identity verification.
    csv_blob,prior=import_two_days(archive)
    if not (prior["runner_rows"]==31 and prior["race_count"]==2 and
            prior["original_source_html_verified"] is True and
            prior["source_scope"]=="HISTORICAL_POST_RACE_LABELS_ONLY"):
        raise RealHistoricalPayoutRejected("upstream_archive_roster_not_verified")
    results=[]
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        for date,race,url in KNOWN:
            path=date.replace("-","")+f"_kyoto_{race:02d}.html"
            raw=z.read(path)
            parsed=extract_result_roster(raw,url)
            if parsed["parse_errors"] or len(parsed["races"])!=1:
                raise RealHistoricalPayoutRejected("official_roster_parse_invalid")
            rows=parsed["races"][0]["rows"]
            first=[x for x in rows if x["placing"]=="1"]
            second=[x for x in rows if x["placing"]=="2"]
            if len(first)!=1 or len(second)!=1:
                raise RealHistoricalPayoutRejected("non_unique_top_two_requires_judgment")
            expected_quinella=sorted([first[0]["horse_number"],second[0]["horse_number"]])
            expected_frame=sorted([first[0]["frame_number"],second[0]["frame_number"]])
            try:visible=BeautifulSoup(raw.decode("cp932","strict"),"html.parser").get_text(" ",strip=True)
            except UnicodeDecodeError as e:raise RealHistoricalPayoutRejected("result_encoding_invalid") from e
            if len(re.findall(r"払戻金\s+単勝",visible))!=1:
                raise RealHistoricalPayoutRejected("official_payout_section_not_unique")
            quinella=_payout(visible,"馬連","馬単")
            bracket=_payout(visible,"枠連","ワイド")
            if quinella["pair"]!=expected_quinella or bracket["pair"]!=expected_frame:
                raise RealHistoricalPayoutRejected("payout_vs_official_top_two_mismatch")
            results.append({
                "date":date,"venue":"KYOTO","race_number":race,
                "source_type":"OFFICIAL_HISTORICAL_POST_RACE_FINAL",
                "source_sha256":hashlib.sha256(raw).hexdigest(),
                "source_url":url,"official_result_rows":len(rows),
                "winner_horse_number":first[0]["horse_number"],
                "runner_up_horse_number":second[0]["horse_number"],
                "winner_frame_number":first[0]["frame_number"],
                "runner_up_frame_number":second[0]["frame_number"],
                "quinella_final":quinella,
                "bracket_final":bracket,
                "payouts_are_genuine_final_not_prerace_odds":True,
                "no_prerace_bets_asserted":True
            })
    obj={
        "schema":"kyoto_p6_two_real_official_historical_final_payout_receipt.v1",
        "original_archive_sha256":ARCHIVE_SHA256,
        "original_capture_run_id":43129613002,
        "historical_race_count":len(results),"official_result_rows":31,
        "real_final_payout_pairs_verified":len(results)*2,
        "races":results,
        "all_sources_postrace_only":True,
        "pre_race_market_prices_verified":False,
        "pre_race_frozen_investments_verified":False,
        "real_paper_trade_pnl_verified":False,
        "official_lifecycle_proven":False,
        "JRA_network_requests_during_replay":0,
    }
    return {**obj,"receipt_sha256":_digest(obj)}
