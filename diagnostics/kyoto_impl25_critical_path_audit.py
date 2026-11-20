"""Read-only static audit of Nov21-22 source capture critical path.

No JRA HTTP, Turso, secrets, or runtime workflow modification. The result
identifies risks and unknowns, not a measured race-day completion time.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path


def audit(collector_text: str, workflow_text: str) -> dict:
    markers = {
        "g03": "g03=collect_after_observer(",
        "g06": "markets=run_twelve(",
        "g04": "g04=g04_capture(",
        "g05": "g05=compile_saved(",
        "track": "track=capture_kyoto_track(",
    }
    positions = {k: collector_text.find(v) for k, v in markers.items()}
    if any(v < 0 for v in positions.values()):
        raise ValueError("capture_stage_missing")
    order = sorted(positions, key=positions.get)
    # Bound timeout extraction to each job block; never cross into SP's timeout.
    pc_block = workflow_text.split("  pc-originals-independent:", 1)[-1].split(
        "\n  sp-originals-independent:", 1)[0]
    sp_block = workflow_text.split("  sp-originals-independent:", 1)[-1]
    if "  pc-originals-independent:" not in workflow_text or (
        "  sp-originals-independent:" not in workflow_text
    ):
        raise ValueError("expected_jobs_missing")
    timeout = re.search(r"(?m)^ {4}timeout-minutes: *([0-9]+)", pc_block)
    sp_timeout = re.search(r"(?m)^ {4}timeout-minutes: *([0-9]+)", sp_block)
    if timeout is None or sp_timeout is None:
        raise ValueError("job_timeout_missing")
    cron = re.findall(r"(?m)^\s*- cron: ['\"]([^'\"]+)['\"]", workflow_text)
    if len(cron) != 8 or len(set(cron)) != 8:
        raise ValueError("eight_independent_schedule_slots_not_confirmed")
    pin = re.findall(r"989aaba017c5450fed91b383421f5d2da53c6c69", workflow_text)
    if not pin:
        raise ValueError("expected_immutable_collector_pin_missing")
    sequential_sp = bool(re.search(r"sp-originals-independent:.*?needs:\s*pc-originals-independent", workflow_text, re.S))
    return {
        "schema": "kyoto_impl25_critical_path_audit.v1",
        "no_external_http_performed": True,
        "source_stage_order": order,
        "pc_timeout_minutes": int(timeout.group(1)),
        "sp_timeout_minutes": int(sp_timeout.group(1)),
        "scheduled_slots": cron,
        "scheduled_slot_count": len(cron),
        "sp_waits_for_pc_completion": sequential_sp,
        "g04_after_g06": positions["g04"] > positions["g06"],
        "g04_earliest_race_cutoff_risk": positions["g04"] > positions["g06"],
        "duration_measured": False,
        "race_day_success_proven": False,
        "all_races_and_horses_proven": False,
        "audit_disposition": "PROFILE_DEFERRED_BEHIND_MARKETS" if positions["g04"] > positions["g06"]
            else "PROFILE_FIRST_MARKET_DELAY_UNMEASURED",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collector", type=Path, required=True)
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.collector.read_text(encoding="utf-8"),
                   args.workflow.read_text(encoding="utf-8"))
    args.out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
