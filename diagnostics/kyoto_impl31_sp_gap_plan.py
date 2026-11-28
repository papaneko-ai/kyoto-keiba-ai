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
EVALUATION_SECONDS=180
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
    future={}; gaps={}; urgent={}; expired=[]; unknown=[]
    for n in RACES:
        row=slot["races"].get(str(n),{})
        try:
            if not re.fullmatch(r"[0-9a-f]{64}",row["racecard"]["sha256"]):raise ValueError("racecard_digest")
            stamp=utc(row["racecard"]["utc"]);start=utc(row["start_utc"])
            if stamp.strftime("%Y%m%d")!=day or start.strftime("%Y%m%d")!=day or stamp>now or stamp>=start:raise ValueError("racecard_time")
            cutoff=start-timedelta(minutes=10)
        except (KeyError,TypeError,ValueError,AttributeError):
            unknown.append(n);continue
        if cutoff<=now:
            # Evaluation needs a ten-minute margin; acquisition does not.
            # An actual upcoming race with missing market originals retains
            # the opportunity to collect strictly before the verified start.
            if now<start and row.get('paired_same_slot') is not True:
                urgent[n]=start
            else:expired.append(n)
            continue
        future[n]=cutoff
        if row.get("paired_same_slot") is not True:gaps[n]=cutoff
    if not future and not urgent:return None
    order=lambda d: sorted(d,key=lambda n:(d[n],n))
    mode="GAP_FIRST" if gaps else "START_FIRST"
    reason="VERIFIED_CURRENT_PC_MARKET_GAPS" if gaps else "VERIFIED_CURRENT_PC_START_ORDER"
    # Only same-day, independently revalidated previous SP feedback on the
    # same still-eligible races may switch to the alternative strategy.
    prior=previous or {}
    comparable={}
    if prior.get("day")==day and prior.get("window_seconds")==EVALUATION_SECONDS:
        prior_targets=prior.get("measured_targets",{})
        for n,cutoff in gaps.items():
            old=prior_targets.get(str(n),{})
            if (old.get("cutoff_utc")==cutoff.isoformat() and cutoff>=now+timedelta(seconds=EVALUATION_SECONDS)
                and old.get("outcome") in ("PAIR_WITHIN_WINDOW","NO_PAIR_WITHIN_WINDOW")):
                comparable[str(n)]=old
    failed=[int(n) for n,x in comparable.items() if x["outcome"]=="NO_PAIR_WITHIN_WINDOW"]
    if mode=="GAP_FIRST" and comparable:
        if prior.get("comparison")=="OBSERVED_REGRESSION" or (prior.get("mode")=="START_FIRST" and failed):
            mode="BASELINE";reason="PREVIOUS_STRATEGY_REGRESSION_OR_NO_PAIR"
        elif prior.get("mode")=="GAP_FIRST" and failed:
            mode="START_FIRST";reason="PREVIOUS_GAP_STRATEGY_NO_PAIR_RECOVERY"
    if mode=="GAP_FIRST":
        races=order(gaps)+unknown+order({n:v for n,v in future.items() if n not in gaps})+expired
    elif mode=="START_FIRST":races=order(future)+unknown+expired
    else:races=RACES.copy()
    if urgent:
        first=order(urgent)
        races=first+[n for n in races if n not in urgent]
    if sorted(races)!=RACES:raise ValueError('race_order_partition')
    return {"schema":"kyoto_impl31_sp_gap_plan.v1","day":day,"source_run_id":str(rid),
        "selected_at_utc":now.isoformat(),"mode":mode,"reason":reason,"race_order":races,
        "targets":{str(n):v.isoformat() for n,v in gaps.items()},
        "urgent_prestart_missing_market_races":order(urgent),
        "window_seconds":EVALUATION_SECONDS,"previous_measured_targets":comparable,
        "previous_same_day_failed_targets":sorted(failed),
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
    failed=[];recovered=[];unknown=[];measured={}
    if plan.get("window_seconds")!=EVALUATION_SECONDS:raise ValueError("window")
    window_end=start+timedelta(seconds=EVALUATION_SECONDS)
    for key,until in plan["targets"].items():
        n=int(key)
        if n not in RACES or str(n)!=key:raise ValueError("target")
        cutoff=utc(until)
        if cutoff<=start or cutoff.strftime("%Y%m%d")!=day:raise ValueError("cutoff")
        if cutoff<window_end:
            unknown.append(n);continue
        prefix=f"r{n:02d}_official_sp_"
        def inside(name):
            row=byname.get(prefix+name+".html")
            if not row:return False
            stamp=utc(row["captured_at_utc"])
            return start<=stamp<window_end and stamp<cutoff
        integrity=post.get("sp_race_integrity",{}).get(key,{})
        if integrity.get("state")!="DIGEST_UTC_CHECKED_ONLY" or not inside("racecard"):
            unknown.append(n);continue
        if integrity.get("both_market_originals_verified_bytes") is True and inside("quinella_odds") and inside("bracket_quinella_odds"):
            recovered.append(n);outcome="PAIR_WITHIN_WINDOW"
        else:
            failed.append(n);outcome="NO_PAIR_WITHIN_WINDOW"
        measured[key]={"cutoff_utc":cutoff.isoformat(),"outcome":outcome}
    before=plan.get("previous_measured_targets",{})
    common={k for k in measured if k in before and before[k].get("cutoff_utc")==measured[k]["cutoff_utc"] and before[k].get("outcome") in ("PAIR_WITHIN_WINDOW","NO_PAIR_WITHIN_WINDOW")}
    b=sum(before[k]["outcome"]=="PAIR_WITHIN_WINDOW" for k in common)
    n=sum(measured[k]["outcome"]=="PAIR_WITHIN_WINDOW" for k in common)
    comparison=("OBSERVED_IMPROVEMENT" if n>b else "OBSERVED_REGRESSION" if n<b else "OBSERVED_UNCHANGED") if common else "NOT_COMPARABLE"
    requests=raw_receipt.get("observed_http_requests_started")
    return {"day":day,"run_id":str(rid),"mode":plan["mode"],
        "comparable_failed_races":sorted(failed),"raw_pair_recovered_races":sorted(recovered),
        "unknown_races":sorted(unknown),"window_seconds":EVALUATION_SECONDS,"measured_targets":measured,
        "comparison":comparison,"compared_races":sorted(int(k) for k in common),
        "before_pairs":b,"after_pairs":n,
        "request_count":requests if type(requests) is int and requests>=0 else None,
        "request_count_scope":"ENTIRE_SP_LANE_NOT_FIXED_COMPARISON_WINDOW",
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
            # A verified main dispatch (including the external timer) is an
            # acquisition attempt, not a native schedule success. Reuse its
            # authenticated feedback on the same basis as native evidence.
            def eligible(r):
                return (r.get("event") in ("schedule","workflow_dispatch")
                        and r.get("head_branch")=="main")
            if eligible(current[0]):
                earlier=[r for r in runs if r["created_at"]<current[0]["created_at"]
                         and r.get("status")=="completed" and eligible(r)]
                # A late native safe-stop or an unavailable recent archive
                # must not erase an earlier comparable result. Bound reads
                # within the original 12-second shared budget.
                for row in reversed(earlier[-2:]):
                    if clock()>=end:break
                    old=row["id"]
                    try:
                        prior=invoke(("lane",day,repo,old,"SP"),end)
                        f=prior.get("sp_gap_feedback")
                        if (prior.get("ciphertext_authenticated") is True
                            and prior.get("source_original_sha_utc_checked") is True
                            and prior.get("channel")=="SP" and prior.get("day")==day
                            and isinstance(f,dict) and f.get("day")==day
                            and f.get("run_id")==str(old)
                            and f.get("official_market_success_claimed") is False
                            and f.get("causal_effect_proved") is False
                            and f.get("mode") in MODES
                            and f.get("window_seconds")==EVALUATION_SECONDS
                            and isinstance(f.get("measured_targets"),dict)
                            and f["measured_targets"]):
                            previous=f
                            break
                    except Exception:
                        # Optional feedback must never erase current PC planning.
                        continue
        return plan_from_pc(pc,day,rid,wall(),previous)
    except Exception:
        return None
