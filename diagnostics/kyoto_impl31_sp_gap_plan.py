"""Bounded same-day PC-to-SP gap prioritization; never supplies source URLs.
An independently verified SP anchor is still mandatory for every request.
The optional plan changes order only; it never suppresses a race or reuses odds.
"""
from datetime import datetime, timezone, timedelta
import re,time
from concurrent.futures import ThreadPoolExecutor
from diagnostics.kyoto_impl31_handoff_budget import _invoke, _index
from diagnostics.kyoto_impl25_c12_all_runs_handoff import WEEKENDS

DAYS=("20261128","20261129")
RACES=list(range(1,13))
MODES=("BASELINE","GAP_FIRST","START_FIRST")
def utc(s):
    t=datetime.fromisoformat(s.replace("Z","+00:00"))
    if t.utcoffset()!=timedelta(0):raise ValueError("not_utc")
    return t

def plan_from_pc(pc,day,rid,now,previous=None):
    if day not in DAYS or now.strftime("%Y%m%d")!=day or now.utcoffset()!=timedelta(0):
        return None
    slot=pc.get("day_coverage_slot",{})
    if (pc.get("ciphertext_authenticated") is not True or pc.get("source_original_sha_utc_checked") is not True
        or slot.get("day")!=day or slot.get("run_id")!=str(rid) or not isinstance(slot.get("races"),dict)):
        return None
    future={}; gaps={}; expired=[]; unknown=[]
    for n in RACES:
        row=slot["races"].get(str(n),{})
        try:
            if not re.fullmatch(r"[0-9a-f]{64}",row["racecard"]["sha256"]):raise ValueError("racecard_digest")
            stamp=utc(row["racecard"]["utc"]);start=utc(row["start_utc"])
            if stamp.strftime("%Y%m%d")!=day or start.strftime("%Y%m%d")!=day or stamp>now or stamp>=start:raise ValueError("racecard_time")
            cutoff=start-timedelta(minutes=10)
        except (KeyError,TypeError,ValueError,AttributeError):
            unknown.append(n);continue
        if cutoff<=now:expired.append(n);continue
        future[n]=cutoff
        if row.get("paired_same_slot") is not True:gaps[n]=cutoff
    if not future:return None
    order=lambda d: sorted(d,key=lambda n:(d[n],n))
    mode="GAP_FIRST" if gaps else "START_FIRST"
    reason="VERIFIED_CURRENT_PC_MARKET_GAPS" if gaps else "VERIFIED_CURRENT_PC_START_ORDER"
    # Only same-day, independently revalidated previous SP feedback on the
    # same still-eligible races may switch to the alternative strategy.
    prior=previous or {}
    comparable=set(gaps)&set(prior.get("comparable_failed_races",[]))
    if mode=="GAP_FIRST" and prior.get("day")==day and prior.get("mode")=="GAP_FIRST" and comparable:
        mode="START_FIRST";reason="PREVIOUS_GAP_STRATEGY_NO_PAIR_RECOVERY"
    if mode=="GAP_FIRST":
        races=order(gaps)+unknown+order({n:v for n,v in future.items() if n not in gaps})+expired
    else:races=order(future)+unknown+expired
    return {"schema":"kyoto_impl31_sp_gap_plan.v1","day":day,"source_run_id":str(rid),
        "selected_at_utc":now.isoformat(),"mode":mode,"reason":reason,"race_order":races,
        "targets":{str(n):v.isoformat() for n,v in gaps.items()},
        "previous_same_day_failed_targets":sorted(comparable),
        "official_market_success_claimed":False}

def feedback(plan,raw_receipt,post,day,rid):
    """Recompute pre-cutoff *raw pair* recovery, not market correctness.
    Failed target counts only if both an attempt and pre-cutoff saved racecard
    are evidenced. Missing/late evidence cannot force a strategy switch.
    """
    if (plan.get("schema")!="kyoto_impl31_sp_gap_plan.v1" or plan.get("day")!=day
        or plan.get("source_run_id")!=str(rid) or plan.get("mode") not in MODES
        or plan.get("official_market_success_claimed") is not False
        or sorted(plan.get("race_order",[]))!=RACES):raise ValueError("plan_identity")
    start=utc(plan["selected_at_utc"])
    if start.strftime("%Y%m%d")!=day:raise ValueError("plan_time")
    byname={r["filename"]:r for r in post.get("source_rows",[])}
    failed=[];recovered=[];unknown=[]
    for key,until in plan["targets"].items():
        n=int(key)
        if n not in RACES or str(n)!=key:raise ValueError("target")
        cutoff=utc(until)
        if cutoff<=start or cutoff.strftime("%Y%m%d")!=day:raise ValueError("cutoff")
        prefix=f"r{n:02d}_official_sp_"
        def inside(name):
            row=byname.get(prefix+name+".html")
            if not row:return False
            stamp=utc(row["captured_at_utc"])
            return start<=stamp<cutoff
        integrity=post.get("sp_race_integrity",{}).get(key,{})
        if integrity.get("state")!="DIGEST_UTC_CHECKED_ONLY" or not inside("racecard"):
            unknown.append(n);continue
        if integrity.get("both_market_originals_verified_bytes") is True and inside("quinella_odds") and inside("bracket_quinella_odds"):
            recovered.append(n)
        else:failed.append(n)
    return {"day":day,"run_id":str(rid),"mode":plan["mode"],
        "comparable_failed_races":sorted(failed),"raw_pair_recovered_races":sorted(recovered),
        "unknown_races":sorted(unknown),"request_count":raw_receipt.get("observed_http_requests_started"),
        "causal_effect_proved":False,"official_market_success_claimed":False}

def get_plan(day,repo,rid,*,deadline,clock=time.monotonic,wall=lambda:datetime.now(timezone.utc),invoke=_invoke):
    if day not in DAYS or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repo) or not str(rid).isdigit():return None
    if wall().strftime("%Y%m%d")!=day:return None
    end=min(deadline,clock()+12.0)
    try:
        # Both current PC evidence and the run index are read-only. No second
        # JRA request is made; the entire lookup uses the SP existing budget.
        with ThreadPoolExecutor(max_workers=2) as pool:
            one=pool.submit(invoke,("lane",day,repo,int(rid),"PC"),end)
            two=pool.submit(invoke,("index",day,repo,0,"main"),end)
            pc=one.result();index=two.result()
        name,filename,_=WEEKENDS[day]
        runs,complete,_=_index(index,day,repo,name,filename)
        previous=None
        current=[r for r in runs if str(r["id"])==str(rid)]
        if complete and len(current)==1 and clock()<end:
            earlier=[r for r in runs if r["created_at"]<current[0]["created_at"] and r.get("status")=="completed" and r.get("event")=="schedule"]
            if earlier:
                old=earlier[-1]["id"]
                prior=invoke(("lane",day,repo,old,"SP"),end)
                if prior.get("ciphertext_authenticated") is True and prior.get("source_original_sha_utc_checked") is True:
                    previous=prior.get("sp_gap_feedback")
        return plan_from_pc(pc,day,rid,wall(),previous)
    except Exception:
        return None
