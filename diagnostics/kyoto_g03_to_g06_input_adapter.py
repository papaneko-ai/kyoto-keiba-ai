"""Convert saved official G03 twelve-race originals into executable G06 inputs.

Only actually saved and byte-verified G03 PC racecard links are accepted.
No SP URL is generated from PC. Missing races stay None so peers proceed.
The adapter is designed to run against the weekend collector's PC originals.
"""
from __future__ import annotations
from datetime import datetime,date,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from hashlib import sha256
import json,re
from diagnostics.jra_market_integrity_gate import normal_sales_open
from diagnostics.jra_one_shot_market_capture import ObservedRaceSpec,SourceChainError

JST=ZoneInfo("Asia/Tokyo")
def records_from_g03(original_root,*,day,skip_invalid_races=False,rejections=None):
    """Default strict contract stays unchanged. Production can isolate bad races.

    A rejected race has no G06 input; never invent a URL or reuse a stale
    source. Global day/meeting/schema failures still reject the entire batch.
    """
    if type(skip_invalid_races) is not bool:
        raise SourceChainError("race_isolation_flag_invalid")
    if rejections is not None and not isinstance(rejections,dict):
        raise SourceChainError("rejections_report_invalid")
    root=Path(original_root)
    if not re.fullmatch(r"2026112[12]",day) or not root.is_dir() or root.is_symlink():
        raise SourceChainError("g03_day_or_root_invalid")
    receipt=root/"g03_receipt.json"
    if not receipt.is_file() or receipt.is_symlink():
        raise SourceChainError("g03_receipt_missing")
    proof=json.loads(receipt.read_text(encoding="utf8"))
    if proof.get("schema")!="kyoto_g03_all_races.v1" or proof.get("day")!=day:
        raise SourceChainError("g03_receipt_day_mismatch")
    sources=proof.get("races")
    if not isinstance(sources,dict):
        raise SourceChainError("g03_races_missing")
    opened=normal_sales_open(date.fromisoformat(day[:4]+"-"+day[4:6]+"-"+day[6:]))
    if opened is None:
        raise SourceChainError("g03_sales_open_not_verified")
    output={}
    for race in range(1,13):
        item=sources.get(str(race))
        if not isinstance(item,dict) or item.get("state")!="ROSTER_AND_START_VERIFIED_OFFLINE":
            output[race]=None
            continue
        try:
            filename=item.get("original_file")
            if filename!=f"official_racecard_{race:02d}.html":
                raise SourceChainError("unexpected_g03_original_filename")
            choices=(root/("g03_"+filename),root/filename)
            found=[p for p in choices if p.is_file() and not p.is_symlink()]
            if len(found)!=1:
                raise SourceChainError("missing_or_ambiguous_g03_original")
            raw=found[0].read_bytes()
            if not raw or sha256(raw).hexdigest()!=item.get("original_sha256"):
                raise SourceChainError("g03_original_sha_mismatch")
            stamp=datetime.fromisoformat(str(item.get("captured_at_utc","")).replace("Z","+00:00"))
            if stamp.tzinfo is None or stamp.utcoffset()!=timezone.utc.utcoffset(None):
                raise SourceChainError("g03_original_utc_missing")
            start_str=item.get("start_time_jst")
            if not isinstance(start_str,str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d",start_str):
                raise SourceChainError("g03_start_time_invalid")
            hour,minute=map(int,start_str.split(":"))
            start=datetime(int(day[:4]),int(day[4:6]),int(day[6:]),hour,minute,tzinfo=JST).astimezone(timezone.utc)
            if stamp>=start:
                raise SourceChainError("g03_original_not_before_start")
            horses=item.get("runners")
            if not isinstance(horses,list) or not 2<=len(horses)<=18:
                raise SourceChainError("g03_roster_missing")
            nums=[h["number"] for h in horses]
            if nums!=list(range(1,len(horses)+1)):
                raise SourceChainError("g03_horse_number_sequence_invalid")
            active=tuple((h["number"],h["frame"]) for h in horses)
            named=tuple((h["number"],h["frame"],h["name"]) for h in horses)
            if any(type(f) is not int or not 1<=f<=8 for _,f in active) or any(not isinstance(n,str) or not n for _,_,n in named):
                raise SourceChainError("g03_roster_not_named")
            spec=ObservedRaceSpec(day,race,f"{day[:4]}-{day[4:6]}-{day[6:]}_KYOTO_{race}R",
                "京都",item["source_url"],"",opened.isoformat())
            spec.validate(require_channels=("PC",))
            output[race]={"race_spec":spec,"verified_start_utc":start.isoformat(),
                "active_runners":active,"expected_named_runners":named,
                "primary_channel":"PC"}
        except (SourceChainError,ValueError,TypeError,KeyError,AttributeError,OSError) as exc:
            if not skip_invalid_races:
                raise
            output[race]=None
            if rejections is not None:
                rejections[str(race)]={"state":"LOCAL_G03_INPUT_REJECTED",
                                       "error_class":type(exc).__name__,
                                       "reason_code":str(exc)[:90] if isinstance(exc,SourceChainError) else "INVALID_RACE_RECEIPT"}
    return output
