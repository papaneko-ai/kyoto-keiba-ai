"""Prove official market links from saved source bytes, never from a racecard URL."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import json
from diagnostics.jra_market_source_chain import _html_race_identity
from diagnostics.jra_official_market_navigation import find_market_links, MarketNavigationError

def _utc(value):
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None or dt.utcoffset()!=timezone.utc.utcoffset(None):
        raise ValueError("not_utc")
    return dt

def observed_market_links(root, *, race_spec, verified_start_utc):
    root=Path(root)
    result={channel:{"observed":False,"reason":"NO_VERIFIED_MARKET_MENU"} for channel in ("PC","SP")}
    for channel in ("PC","SP"):
        folder=root/channel.lower()
        receipt_file=folder/"receipt.json"
        if receipt_file.is_symlink() or not receipt_file.is_file():
            continue
        try:
            receipt=json.loads(receipt_file.read_text(encoding="utf-8"))
            if receipt.get("channel")!=channel or receipt.get("race_id")!=race_spec.race_id:
                raise ValueError("receipt_identity_mismatch")
            if receipt.get("state") in ("REJECT_FINAL_ODDS","CUTOFF_PASSED_NO_HTTP","OFFICIAL_NOT_PUBLISHED"):
                raise ValueError("unsafe_sale_state")
            steps={x["step"]:x for x in receipt["request_receipts"]}
            nav_steps=sorted((k for k in steps if k.startswith("odds_navigation_")),
                key=lambda k:int(k.rsplit("_",1)[-1]))
            chosen=nav_steps[-1] if nav_steps else "odds_menu"
            name=("official_odds_menu.html" if chosen=="odds_menu" else
                "official_odds_navigation_"+chosen.rsplit("_",1)[-1]+".html")
            step=steps[chosen]
            raw_file=folder/name
            if raw_file.is_symlink() or not raw_file.is_file():
                raise ValueError("menu_original_missing")
            raw=raw_file.read_bytes()
            if not raw or len(raw)!=step["bytes"] or sha256(raw).hexdigest()!=step["sha256"]:
                raise ValueError("menu_sha_mismatch")
            if _utc(step["captured_at_utc"])>=_utc(verified_start_utc):
                raise ValueError("menu_after_race_start")
            if not _html_race_identity(raw,race_spec.race_day,race_spec.venue,race_spec.race_number):
                raise ValueError("menu_race_identity_mismatch")
            host="sp.jra.jp" if channel=="SP" else "jra.jp"
            links=find_market_links(raw,expected_race_day=race_spec.race_day,
                expected_race_number=race_spec.race_number,expected_host=host)
            if links["source_final_odds_detected"]:
                raise ValueError("final_odds_detected")
            result[channel]={"observed":True,"reason":"INDEPENDENT_ORIGINAL_VERIFIED",
                "menu_sha256":step["sha256"],
                "markets":{m:{"cname_sha256":v["cname_sha256"],
                              "official_post_url":v["official_post_url"]}
                           for m,v in links["markets"].items()}}
        except (KeyError,IndexError,ValueError,TypeError,AttributeError,OSError,MarketNavigationError) as exc:
            result[channel]={"observed":False,"reason":str(exc)[:160]}
    return result
