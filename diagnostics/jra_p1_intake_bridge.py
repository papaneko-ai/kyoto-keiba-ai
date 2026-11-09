"""Join a source-byte-verified offline bundle to a prerace structured snapshot.

No source parsing, network requests, betting or official-origin attestation.
A successful structural join NEVER marks data as prediction-ready.
"""
import io
import json
import zipfile
from datetime import datetime

from diagnostics.jra_p1_offline_handoff import import_bundle
from diagnostics.jra_p1_snapshot_gate import evaluate


class IntakeRejected(ValueError):
    pass


def inspect_bundle_and_snapshot(bundle: bytes, snapshot: dict, *, observed_utc: str):
    """Validate separately and then reconcile race/date/raw-byte SHA evidence."""
    try:
        inspected = import_bundle(bundle, observed_utc=observed_utc)
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            receipt = json.loads(archive.read('receipt.json'))
    except (ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        raise IntakeRejected('source_bundle_invalid') from exc

    if not isinstance(snapshot, dict):
        raise IntakeRejected('snapshot_invalid')
    checked = evaluate(snapshot, observed_utc=observed_utc)
    if checked['status'] != 'STRUCTURAL_CHECK_ONLY':
        raise IntakeRejected('snapshot_structural_blocked:' + ','.join(checked['reasons']))
    if manifest.get('meeting_date') != snapshot.get('meeting_date'):
        raise IntakeRejected('meeting_date_mismatch')
    if receipt.get('source_count') != 2 or len(manifest.get('sources', [])) != 2:
        raise IntakeRejected('requires_one_racecard_and_one_odds_original')
    wanted = {'racecard': 'racecard', 'pre_race_odds': 'odds'}
    provided = {}
    for row in manifest['sources']:
        if not isinstance(row, dict):
            raise IntakeRejected('source_row_invalid')
        key = wanted.get(row.get('kind'))
        if key is None or key in provided:
            raise IntakeRejected('source_kind_missing_or_duplicated')
        if row.get('race') != snapshot.get('race'):
            raise IntakeRejected('race_number_mismatch')
        provided[key] = row
    if set(provided) != {'racecard', 'odds'}:
        raise IntakeRejected('source_kind_missing_or_duplicated')
    for key, item in provided.items():
        claimed = snapshot['sources'][key]
        if item['sha256'] != claimed['sha256']:
            raise IntakeRejected(key + '_original_sha_mismatch')
        if datetime.fromisoformat(item['captured_utc'].replace('Z', '+00:00')) != datetime.fromisoformat(claimed['captured_utc'].replace('Z', '+00:00')):
            raise IntakeRejected(key + '_capture_time_mismatch')
    if inspected['source_count'] != 2:
        raise IntakeRejected('bundle_source_count_mismatch')
    return {'status': 'OFFLINE_SOURCE_JOIN_ONLY', 'meeting_date': snapshot['meeting_date'],
            'race': snapshot['race'], 'runner_count': checked['runner_count'],
            'bundle_sha256': inspected['raw_sha256'],
            'snapshot_sha256': checked['snapshot_sha256'],
            'prediction_ready': False, 'network_requests': 0,
            'unverified': checked['unverified']}
