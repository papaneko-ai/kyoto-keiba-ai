"""P1 future-race source evidence gate (offline only; no network transport).

Checks a user-supplied evidence manifest against local raw source bytes before
any racecard is offered as a pre-race candidate. This does not attest JRA origin
or permission to fetch, and never asserts prediction readiness.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


class EvidenceRejected(ValueError):
    pass


def instant(value):
    if not isinstance(value, str):
        raise EvidenceRejected('timestamp_missing')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise EvidenceRejected('timestamp_invalid') from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise EvidenceRejected('timestamp_not_utc')
    if dt.utcoffset().total_seconds() != 0:
        raise EvidenceRejected('timestamp_not_utc')
    return dt.astimezone(timezone.utc)


def verify(manifest, root, *, observed_utc=None):
    if not isinstance(manifest, dict):
        raise EvidenceRejected('manifest_invalid')
    if manifest.get('schema') != 'kyoto_p1_future_race_source_evidence.v1':
        raise EvidenceRejected('manifest_schema_invalid')
    meeting = manifest.get('meeting_date')
    cutoff = instant(manifest.get('cutoff_utc'))
    observed = instant(observed_utc.isoformat()) if isinstance(observed_utc, datetime) else instant(observed_utc) if observed_utc is not None else datetime.now(timezone.utc)
    try:
        day = datetime.fromisoformat(meeting).date()
    except (TypeError, ValueError) as exc:
        raise EvidenceRejected('meeting_date_invalid') from exc
    if day.isoformat() != meeting or day.isoformat() <= '2026-11-07':
        raise EvidenceRejected('not_a_future_target_from_baseline')
    if (cutoff + timedelta(hours=9)).date() != day:
        raise EvidenceRejected('cutoff_not_on_meeting_day_jst')
    rows = manifest.get('sources')
    if not isinstance(rows, list) or not rows:
        raise EvidenceRejected('sources_missing')
    root = Path(root).resolve(strict=True)
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or row.get('kind') not in ('racecard', 'pre_race_odds', 'bracket_odds'):
            raise EvidenceRejected('source_type_invalid')
        if type(row.get('race')) is not int or not 1 <= row['race'] <= 12:
            raise EvidenceRejected('race_invalid')
        key = (row['kind'], row['race'])
        if key in seen:
            raise EvidenceRejected('duplicate_source')
        seen.add(key)
        recorded = instant(row.get('captured_utc'))
        if recorded >= cutoff:
            raise EvidenceRejected('post_cutoff_source')
        if recorded > observed:
            raise EvidenceRejected('future_dated_source')
        path_value = row.get('path')
        if not isinstance(path_value, str) or not path_value or Path(path_value).is_absolute() or '..' in Path(path_value).parts:
            raise EvidenceRejected('unsafe_source_path')
        path = root / path_value
        actual = path.resolve(strict=True)
        if not actual.is_relative_to(root) or not actual.is_file() or path.is_symlink():
            raise EvidenceRejected('source_outside_root')
        raw = actual.read_bytes()
        if not raw or len(raw) > 1_800_000:
            raise EvidenceRejected('source_size_invalid')
        expected = row.get('sha256')
        if not isinstance(expected, str) or len(expected) != 64 or hashlib.sha256(raw).hexdigest() != expected:
            raise EvidenceRejected('source_sha_mismatch')
        if not isinstance(row.get('official_url_observed'), bool) or not row['official_url_observed']:
            raise EvidenceRejected('official_url_not_observed')
    return {'status': 'SOURCE_BYTES_AND_TIMESTAMPS_INTERNALLY_CONSISTENT_ONLY',
            'meeting_date': meeting, 'checked_source_count': len(rows),
            'prediction_ready': False, 'network_requests': 0,
            'not_verified': ['official_source_authenticity', 'legal_permission',
                             'prerace_odds_completeness', 'horse_identity', 'multi_host_lease']}


def main():
    parser = argparse.ArgumentParser(description='Offline pre-race source evidence check')
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding='utf-8'))
        result = verify(data, args.manifest.parent)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (EvidenceRejected, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f'BLOCKED: {exc}\n')


if __name__ == '__main__':
    main()
