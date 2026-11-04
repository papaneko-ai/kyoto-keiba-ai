"""Opt-in S3 compatible storage connectivity probe. No bets, forecasts or race data.

Creates one harmless random probe record, checks readback and overwrite rejection.
It never deletes records, and never claims bucket immutability from a successful probe.
"""
from __future__ import annotations
import base64
import datetime as dt
import hashlib
import json
import secrets
import re

_SAFE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$')


def _safe(value):
    if not isinstance(value, str) or value in ('.', '..') or not _SAFE.fullmatch(value):
        raise ValueError('Invalid bucket or prefix segment')
    return value


def _error_code(error):
    return str(getattr(error, 'response', {}).get('Error', {}).get('Code', ''))


def _read_object(client, bucket, key):
    response = client.get_object(Bucket=bucket, Key=key)
    data = response['Body'].read()
    return data if isinstance(data, bytes) else bytes(data)


def probe_storage(*, client_factory, bucket, prefix='kyoto-ai/healthchecks', clock=None):
    """Verify real read/write and conditional create without production records.

    client_factory must create an independent client each invocation. All connection
    details are held by the caller. Provider connection errors are returned as stage
    and sanitized error code only, not exception text (which may contain secrets).
    """
    _safe(bucket)
    parts = prefix.split('/')
    if not parts or any(not p or p in ('.', '..') or not _SAFE.fullmatch(p) for p in parts):
        raise ValueError('Invalid prefix')
    timestamp = clock or dt.datetime.now(dt.timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError('UTC-aware clock required')
    token = secrets.token_hex(16)
    key = f'{prefix}/v14-{token}.json'
    record = {'schema': 'kyoto-ai-storage-probe-v14', 'nonce': token,
              'created_utc': timestamp.astimezone(dt.timezone.utc).isoformat(),
              'contains_racing_data': False}
    raw = json.dumps(record, sort_keys=True, separators=(',', ':')).encode('utf-8')
    checksum = hashlib.sha256(raw).hexdigest()
    result = {'schema': 'kyoto-ai-storage-probe-result-v14', 'status': 'FAILED',
              'stage': 'connect', 'key': key, 'sha256': checksum,
              'write': False, 'readback': False, 'overwrite_rejected': False,
              'second_client_read': False,
              'versioning': 'NOT_CHECKED', 'object_lock': 'NOT_CHECKED',
              'limitations': ['A probe does not prove retention against administrator deletion',
                              'A probe does not prove recovery after a service outage',
                              'No forecast or real race data were archived']}
    try:
        client = client_factory()
        result['stage'] = 'write'
        client.put_object(Bucket=bucket, Key=key, Body=raw,
                          ContentType='application/json', IfNoneMatch='*',
                          ChecksumSHA256=base64.b64encode(hashlib.sha256(raw).digest()).decode('ascii'))
        result['write'] = True
        result['stage'] = 'readback'
        if _read_object(client, bucket, key) != raw:
            result['failure'] = 'READBACK_MISMATCH'
            return result
        result['readback'] = True
        result['stage'] = 'duplicate_write'
        try:
            client.put_object(Bucket=bucket, Key=key, Body=b'changed',
                              ContentType='application/json', IfNoneMatch='*')
        except Exception as exc:
            if _error_code(exc) not in ('PreconditionFailed', '412'):
                result['failure'] = 'DUPLICATE_UNEXPECTED_ERROR'
                return result
            result['overwrite_rejected'] = True
        else:
            result['failure'] = 'OVERWRITE_WAS_ALLOWED'
            return result
        result['stage'] = 'second_client_read'
        again = client_factory()
        if _read_object(again, bucket, key) != raw:
            result['failure'] = 'SECOND_CLIENT_MISMATCH'
            return result
        result['second_client_read'] = True
        result['status'] = 'PASS_CONNECTIVITY_ONLY'
        result['stage'] = 'complete'
    except Exception as exc:
        result['failure'] = 'PROVIDER_OR_NETWORK_ERROR'
        result['provider_error_code'] = _error_code(exc) or type(exc).__name__
    return result


def read_bucket_controls(client, bucket):
    """Best-effort provider controls; errors do not imply controls are disabled."""
    details = {'versioning': 'UNVERIFIED', 'object_lock': 'UNVERIFIED'}
    try:
        status = client.get_bucket_versioning(Bucket=bucket).get('Status')
        details['versioning'] = 'ENABLED' if status == 'Enabled' else 'NOT_ENABLED'
    except Exception:
        details['versioning'] = 'UNKNOWN_NO_PERMISSION_OR_UNSUPPORTED'
    try:
        configuration = client.get_object_lock_configuration(Bucket=bucket)
        enabled = configuration.get('ObjectLockConfiguration', {}).get('ObjectLockEnabled')
        details['object_lock'] = 'ENABLED_CONFIG_PRESENT' if enabled == 'Enabled' else 'NOT_ENABLED'
    except Exception:
        details['object_lock'] = 'UNKNOWN_NO_PERMISSION_OR_UNSUPPORTED'
    return details
