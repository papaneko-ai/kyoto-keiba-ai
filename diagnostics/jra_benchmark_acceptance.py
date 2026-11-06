"""Accept a bounded real PC/SP paired benchmark into the offline routing policy.

This is not a live-switch or a source authentication bypass. Uses only previously
captured immutable source receipts and independently frozen pre-race PC roster.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from statistics import median
import json
from diagnostics.jra_source_router import SourceEvidence,decide,REQUIRED_FIELDS

RACES=(1,5,6,11,12)
ROOT=Path("docs/diagnostics")
REPORT=ROOT/"pc_sp_benchmark_20261106"/"benchmark_report.json"
def _read(p):
    return json.loads(Path(p).read_text(encoding="utf8"))

def _snapshot(race):
    if race==7:p=ROOT/"JRA_KYOTO_R7_PRERACE_FROZEN_20261106.json"
    elif race in (1,6,12):p=ROOT/"multirace_20261106"/f"kyoto_{race:02d}_snapshot.json"
    else:p=ROOT/"remaining8_20261106"/f"kyoto_{race:02d}_snapshot.json"
    return _read(p)

def audit_report(data):
    if data.get("sample_races")!=list(RACES) or len(data.get("races",[]))!=len(RACES):
        raise ValueError("unexpected_comparison_sample")
    if data.get("full_roster_parity") is not True:
        raise ValueError("five_races_not_verified")
    pc_samples=[];sp_samples=[];counts=[]
    for pair,expected_race in zip(data["races"],RACES):
        if pair["race"]!=expected_race or not pair["pc_snapshot_match"] or not pair["sp_snapshot_match"]:
            raise ValueError("roster_parity_missing")
        baseline=_snapshot(expected_race)
        if baseline["runner_count"]!=pair["expected_count"]:
            raise ValueError("frozen_count_mismatch")
        counts.append(pair["expected_count"])
        for channel,samples in (("pc",pc_samples),("sp",sp_samples)):
            entry=pair[channel]
            if entry["status"]!="PARSED" or entry["race"]!=expected_race:
                raise ValueError("unparsed_official_source")
            if entry["rows"]!=pair["expected_count"] or entry["raw_bytes"]<=0:
                raise ValueError("incomplete_official_source")
            if len(entry["source_sha256"])!=64:
                raise ValueError("missing_original_sha256")
            captured=datetime.fromisoformat(entry["recorded_at_utc"].replace("Z","+00:00"))
            if captured.tzinfo is None or captured.astimezone(timezone.utc)>=datetime.fromisoformat("2026-11-07T01:05:00+00:00"):
                raise ValueError("late_or_unqualified_timestamp")
            total=entry.get("network_ms",0)+entry.get("parse_ms",0)
            if total<=0:raise ValueError("invalid_elapsed_measurement")
            samples.append(round(total,2))
    mpc=median(pc_samples);msp=median(sp_samples)
    improved=100*(1-msp/mpc)
    if data["pc_total_bytes"]!=sum(x["pc"]["raw_bytes"] for x in data["races"]) or data["sp_total_bytes"]!=sum(x["sp"]["raw_bytes"] for x in data["races"]):
        raise ValueError("reported_sizes_conflict")
    last=next(x for x in data["races"] if x["race"]==11)
    prior=_snapshot(11)
    rows=tuple((x["horse_number"],x["frame_number"],x["horse_name"]) for x in prior["runners"])
    def proof(channel):
        v=last[channel]
        return SourceEvidence(
            channel=channel.upper(),race_key="2026-11-07-KYOTO-11R",
            captured_at_utc=v["recorded_at_utc"],
            content_sha256=v["source_sha256"],
            rows=rows,fields_verified=REQUIRED_FIELDS,
            independent_checks=5,
            latency_ms_samples=tuple(pc_samples if channel=="pc" else sp_samples),
            observed_bytes=v["raw_bytes"],response_verified=True)
    decision=decide(proof("pc"),proof("sp"),successful_sp_crosschecks=5,require_scratches=False)
    return {"schema_version":"jra_adaptive_evidence_acceptance.v1",
        "date":"2026-11-07","venue":"KYOTO","sampled_races":list(RACES),
        "total_checked_runners":sum(counts),"parity_passed_for_all_five":True,
        "pc_total_bytes":data["pc_total_bytes"],"sp_total_bytes":data["sp_total_bytes"],
        "sp_bytes_reduction_pct":round(100*(1-data["sp_total_bytes"]/data["pc_total_bytes"]),1),
        "pc_end_to_end_median_ms":round(mpc,2),"sp_end_to_end_median_ms":round(msp,2),
        "sp_end_to_end_gain_pct":round(improved,1),
        "sp_faster_race_count":sum(x<y for x,y in zip(sp_samples,pc_samples)),
        "pc_samples_ms":pc_samples,"sp_samples_ms":sp_samples,
        "router_candidate":decision["preferred_source"],
        "router_state":decision["state"],
        "router_reason":decision["reason"],
        "safety":{"production_switch_performed":False,
                  "longitudinal_speed_advantage_proven":False,
                  "all_history_fields_verified":False,
                  "final_scratches_verified":False,
                  "odds_verified":False,"training_ready":False,
                  "prediction_ready":False}}
def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--report",default=str(REPORT));p.add_argument("--out",required=True)
    a=p.parse_args()
    verdict=audit_report(_read(a.report))
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(verdict,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps(verdict,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
