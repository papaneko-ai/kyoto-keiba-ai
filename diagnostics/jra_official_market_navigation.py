"""Derive real PC/SP JRA race-specific odds market actions from official HTML.
Never synthesizes CNAME tokens, odds, or source publication state.
"""
from bs4 import BeautifulSoup
from hashlib import sha256
import re

ACTION=re.compile(r"doAction\s*\(\s*['\"](/JRADB/accessO\.html)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)")
MARKETS={"馬連":"quinella","枠連":"bracket_quinella"}
class MarketNavigationError(ValueError):pass

def find_market_links(raw,*,expected_race_day,expected_race_number,expected_host="jra.jp"):
    if not isinstance(raw,bytes) or not 0<len(raw)<=1500000:
        raise MarketNavigationError("invalid_original_html")
    if not re.fullmatch(r"20\d{6}",expected_race_day) or not 1<=expected_race_number<=12:
        raise MarketNavigationError("invalid_race_identity")
    soup=BeautifulSoup(raw.decode("cp932",errors="replace"),"html.parser")
    if not soup.title or "オッズ" not in soup.title.get_text():
        raise MarketNavigationError("not_official_odds_page")
    result={}
    for label,market in MARKETS.items():
        tokens=set()
        for a in soup.select("a"):
            if a.get_text(" ",strip=True)!=label:continue
            match=ACTION.search(a.get("onclick",""))
            if not match:continue
            token=match.group(2)
            if (not token.startswith(("pw","sw")) or expected_race_day not in token
                or f"{expected_race_number:02d}{expected_race_day}" not in token
                or not re.fullmatch(r"[A-Za-z0-9]+/[A-Za-z0-9]+",token)):continue
            tokens.add(token)
        if len(tokens)!=1:raise MarketNavigationError(market+"_unique_link_missing")
        token=next(iter(tokens))
        is_mobile=token.startswith("sw")
        if (expected_host=="sp.jra.jp")!=is_mobile:
            raise MarketNavigationError("unexpected_channel_token")
        result[market]={"official_post_url":f"https://{expected_host}/JRADB/accessO.html",
            "form_parameter":"cname","cname":token,
            "cname_sha256":sha256(token.encode()).hexdigest()}
    return {"schema_version":"jra_official_market_navigation.v1",
        "source_sha256":sha256(raw).hexdigest(),
        "race_date":expected_race_day,"race_number":expected_race_number,
        "markets":result,
        "source_final_odds_detected":"最終オッズ" in soup.get_text(" ",strip=True),
        "prices_verified":False,"prediction_ready":False,"training_ready":False}
