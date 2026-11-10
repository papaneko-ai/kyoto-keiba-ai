"""Portable offline-only source evidence handoff. Does NOT authenticate JRA data."""
import hashlib
import io
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from diagnostics.jra_p1_future_evidence import EvidenceRejected, instant, verify

MAX_BUNDLE_BYTES = 12_000_000
MAX_SOURCES = 24

def _canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')

def _source_name(index):
    return f'originals/source_{index:02d}.html'

def export_bundle(evidence, root, *, observed_utc):
    """Builds a bounded portable archive from locally saved evidence; no HTTP."""
    verify(evidence, root, observed_utc=observed_utc)
    rows = evidence['sources']
    if len(rows) > MAX_SOURCES:
        raise EvidenceRejected('too_many_sources')
    stamped = instant(observed_utc.isoformat() if isinstance(observed_utc, datetime) else observed_utc)
    manifest = dict(evidence)
    sanitized = []
    originals = []
    for i, row in enumerate(rows, 1):
        raw = (Path(root) / row['path']).read_bytes()
        new = dict(row)
        new['path'] = _source_name(i)
        sanitized.append(new)
        originals.append((new['path'], raw))
    manifest['sources'] = sanitized
    receipt = {'schema': 'kyoto_p1_offline_handoff.v1', 'observed_utc': stamped.isoformat(),
               'manifest_sha256': hashlib.sha256(_canonical(manifest)).hexdigest(),
               'source_count': len(rows), 'prediction_ready': False,
               'transport': 'offline_file_transfer_only'}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:
        # Fixed ZIP metadata: a source handoff is a content-addressed artifact,
        # not a timestamped build product. Otherwise 2s DOS time ticks alter
        # raw SHA and invalidate independent replay across runs.
        members = [('manifest.json', _canonical(manifest)),
                   ('receipt.json', _canonical(receipt)), *originals]
        for name, raw in members:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o600 << 16
            archive.writestr(info, raw)
    data = buffer.getvalue()
    if len(data) > MAX_BUNDLE_BYTES:
        raise EvidenceRejected('bundle_too_large')
    return data

def import_bundle(data, *, observed_utc):
    """Checks zip bytes in memory; no extraction, network or prediction enable."""
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_BUNDLE_BYTES:
        raise EvidenceRejected('bundle_size_invalid')
    now = instant(observed_utc.isoformat() if isinstance(observed_utc, datetime) else observed_utc)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if len(names) != len(set(names)) or len(names) < 3 or len(names) > MAX_SOURCES + 2:
                raise EvidenceRejected('bundle_members_invalid')
            if any(item.is_dir() or item.file_size > 1_800_000 or item.compress_type != zipfile.ZIP_STORED
                   or ((item.external_attr >> 16) & 0o170000) == 0o120000 for item in infos):
                raise EvidenceRejected('bundle_member_unsafe')
            if any(not re.fullmatch(r'(?:manifest\.json|receipt\.json|originals/source_\d{2}\.html)', n) for n in names):
                raise EvidenceRejected('bundle_filename_invalid')
            receipt = json.loads(archive.read('receipt.json'))
            manifest_raw = archive.read('manifest.json')
            manifest = json.loads(manifest_raw)
            if receipt.get('schema') != 'kyoto_p1_offline_handoff.v1' or receipt.get('prediction_ready') is not False:
                raise EvidenceRejected('receipt_invalid')
            if receipt.get('transport') != 'offline_file_transfer_only':
                raise EvidenceRejected('transport_invalid')
            if _canonical(manifest) != manifest_raw or hashlib.sha256(manifest_raw).hexdigest() != receipt.get('manifest_sha256'):
                raise EvidenceRejected('manifest_integrity_invalid')
            source_rows = manifest.get('sources')
            if not isinstance(source_rows, list) or not 1 <= len(source_rows) <= MAX_SOURCES:
                raise EvidenceRejected('source_count_invalid')
            if receipt.get('source_count') != len(source_rows):
                raise EvidenceRejected('source_count_mismatch')
            expected_names = {'manifest.json', 'receipt.json'} | {r.get('path') for r in source_rows if isinstance(r, dict)}
            if set(names) != expected_names or len(expected_names) != len(names):
                raise EvidenceRejected('manifest_members_mismatch')
            for i, row in enumerate(source_rows, 1):
                if row['path'] != _source_name(i):
                    raise EvidenceRejected('source_order_invalid')
                raw = archive.read(row['path'])
                if not raw or hashlib.sha256(raw).hexdigest() != row.get('sha256'):
                    raise EvidenceRejected('source_bytes_modified')
            captured = instant(receipt.get('observed_utc'))
            if captured > now:
                raise EvidenceRejected('bundle_future_dated')
            if any(instant(row['captured_utc']) > captured for row in source_rows):
                raise EvidenceRejected('source_after_bundle_assembly')
            return {'status': 'OFFLINE_HANDOFF_INTEGRITY_ONLY', 'meeting_date': manifest['meeting_date'],
                    'source_count': len(source_rows), 'prediction_ready': False,
                    'network_requests': 0, 'raw_sha256': hashlib.sha256(data).hexdigest(),
                    'not_verified': ['JRA_authorization', 'official_source_authenticity',
                                     'official_race_time', 'horse_identity', 'odds_completeness']}
    except (zipfile.BadZipFile, KeyError, ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        if isinstance(exc, EvidenceRejected):
            raise
        raise EvidenceRejected('bundle_malformed') from exc
