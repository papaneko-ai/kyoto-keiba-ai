"""P1-FB stage5: bind PC horse URLs to archived official racecard feature registry.

Offline only. No SP fallback URL is inferred from PC tokens.
The registry is an already committed record, not raw HTML itself.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from diagnostics.jra_p1_fb_stage5_guarded_replay import RosterHorse
from diagnostics.jra_pending_profile_plan import trusted_url

def load_roster_horse(*, registry_file, meeting_date, race, number,
                      expected_registry_sha256=None):
    """Require exactly one identity in archived feature rows, never synthesize URLs."""
    from hashlib import sha256
    path=Path(registry_file)
    raw=path.read_bytes()
    digest=sha256(raw).hexdigest()
    if expected_registry_sha256 is not None and digest != expected_registry_sha256:
        raise ValueError("registry_bytes_changed")
    rows=json.loads(raw)
    if not isinstance(rows,list):
        raise ValueError("invalid_registry_rows")
    expected_id=f"{meeting_date}_KYOTO_{race:02d}R"
    matches=[row for row in rows if
             row.get("race_number")==race and row.get("horse_number")==number]
    if len(matches)!=1:
        raise ValueError("horse_not_unique_in_registry")
    row=matches[0]
    if row.get("race")!=expected_id:
        raise ValueError("race_identity_conflict")
    if row.get("source_coverage",{}).get("racecard")!="CONFIRMED":
        raise ValueError("racecard_not_confirmed")
    sha=row.get("racecard_source_sha256")
    if not isinstance(sha,str) or re.fullmatch("[0-9a-f]{64}",sha) is None:
        raise ValueError("invalid_racecard_sha")
    when=datetime.fromisoformat(row["racecard_captured_at_utc"].replace("Z","+00:00"))
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("unverified_roster_timestamp")
    from zoneinfo import ZoneInfo
    if when.astimezone(ZoneInfo("Asia/Tokyo")).date().isoformat()>meeting_date:
        raise ValueError("roster_captured_after_race_day")
    coverage=row.get("source_coverage",{}).get("horse_profile")
    if coverage!="NOT_QUERIED" or row.get("profile_source_sha256"):
        raise ValueError("horse_already_has_source_record")
    pc=trusted_url(row["profile_href"])
    name=row["horse_name"]
    if not isinstance(name,str) or not name.strip():
        raise ValueError("missing_horse_name")
    if row.get("prediction_ready") is not False or row.get("training_ready") is not False:
        raise ValueError("unverified_model_status")
    return RosterHorse(meeting_date=meeting_date, race=race, number=number,
                       horse_name=name, racecard_sha256=sha,
                       pc_url=pc, sp_url=None, pc_observed=True, sp_observed=False)
