"""Independent, password-gated Turso compatibility probe for Kyoto Keiba AI v14.

Run against kyoto-keiba-ai-test only. No imports from production or v14.
No automatic writes: explicit button + typed confirmation required.
This probe does NOT claim atomic 12-race registration, concurrency safety, or tamper resistance.
"""
from __future__ import annotations

import hmac
import re
import uuid
from urllib.parse import urlsplit

import requests
import streamlit as st

PREFIX = '__kyoto_v14_compat_v2_'
EXPECTED_DB = 'kyoto-keiba-ai-test'
EXPECTED_HOST = 'kyoto-keiba-ai-test-papaneko-ai.aws-ap-northeast-1.turso.io'


def api_endpoint(db_url: str) -> str:
    parsed = urlsplit(db_url.strip())
    if parsed.scheme not in ('libsql', 'https') or not parsed.hostname:
        raise ValueError('Invalid connection URL')
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise ValueError('Unexpected URL parts')
    if not parsed.hostname.endswith('.turso.io'):
        raise ValueError('Not a Turso host')
    if parsed.hostname != EXPECTED_HOST:
        raise ValueError('This probe is restricted to the dedicated test database')
    return 'https://' + parsed.netloc + '/v2/pipeline'


def execute_pipeline(db_url: str, token: str, statements):
    """Execute in one HTTP stream; do not mistake this for an atomic transaction.

    A result's 'type=error' is kept so expected constraint violations can be tested.
    All SQL is constant in callers; parameter values are bound, never interpolated.
    """
    requests_list = []
    for sql, values in statements:
        args = []
        for value in values:
            if value is None:
                args.append({'type': 'null'})
            elif isinstance(value, int):
                args.append({'type': 'integer', 'value': str(value)})
            else:
                args.append({'type': 'text', 'value': str(value)})
        requests_list.append({'type': 'execute', 'stmt': {'sql': sql, 'args': args, 'want_rows': True}})
    requests_list.append({'type': 'close'})
    response = requests.post(
        api_endpoint(db_url),
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
        json={'requests': requests_list},
        timeout=20,
        allow_redirects=False,
    )
    if response.status_code != 200:
        raise RuntimeError('Turso transport failed (HTTP status %s)' % response.status_code)
    body = response.json()
    results = body.get('results', [])
    if len(results) != len(requests_list):
        raise RuntimeError('Unexpected response length')
    if results[-1].get('type') != 'ok':
        raise RuntimeError('Stream close failed')
    return results[:-1]


def require_ok(item, description):
    if item.get('type') != 'ok':
        raise RuntimeError(description + ' failed')
    return item['response']['result']


def cell(result):
    return result['rows'][0][0]['value']


def immutable_test(url, token):
    """New random isolated table; rejects UPDATE and DELETE and verifies original."""
    table = PREFIX + 'immutable'
    # One-time shared diagnostic table; a UUID ensures each inserted row is distinct.
    setup = execute_pipeline(url, token, [
        (f'CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, payload TEXT NOT NULL)', ()),
        (f"CREATE TRIGGER IF NOT EXISTS {table}_no_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'immutable'); END", ()),
        (f"CREATE TRIGGER IF NOT EXISTS {table}_no_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'immutable'); END", ()),
    ])
    for i, result in enumerate(setup):
        require_ok(result, 'Schema setup step ' + str(i+1))
    key = str(uuid.uuid4())
    responses = execute_pipeline(url, token, [
        (f'INSERT INTO {table} (id, payload) VALUES (?, ?)', (key, 'original')),
        (f'UPDATE {table} SET payload = ? WHERE id = ?', ('changed', key)),
        (f'DELETE FROM {table} WHERE id = ?', (key,)),
        (f'SELECT payload FROM {table} WHERE id = ?', (key,)),
    ])
    require_ok(responses[0], 'Insert')
    if responses[1].get('type') != 'error' or responses[2].get('type') != 'error':
        raise AssertionError('UPDATE or DELETE was not rejected')
    if cell(require_ok(responses[3], 'Integrity readback')) != 'original':
        raise AssertionError('Persisted record was unexpectedly modified')
    return True


def foreign_key_test(url, token):
    """Verify FK enforcement on the same HTTP stream with PRAGMA enabled."""
    parent = PREFIX + 'parent'
    child = PREFIX + 'child'
    setup = execute_pipeline(url, token, [
        (f'CREATE TABLE IF NOT EXISTS {parent} (id TEXT PRIMARY KEY)', ()),
        (f'CREATE TABLE IF NOT EXISTS {child} (id TEXT PRIMARY KEY, parent_id TEXT NOT NULL REFERENCES {parent}(id))', ()),
    ])
    for i, result in enumerate(setup):
        require_ok(result, 'FK schema setup step ' + str(i+1))
    p = str(uuid.uuid4())
    good = str(uuid.uuid4())
    orphan = str(uuid.uuid4())
    answers = execute_pipeline(url, token, [
        ('PRAGMA foreign_keys = ON', ()),
        ('PRAGMA foreign_keys', ()),
        (f'INSERT INTO {parent} (id) VALUES (?)', (p,)),
        (f'INSERT INTO {child} (id, parent_id) VALUES (?, ?)', (good, p)),
        (f'INSERT INTO {child} (id, parent_id) VALUES (?, ?)', (orphan, 'absent-' + p)),
        (f'SELECT COUNT(*) FROM {child} WHERE id = ?', (orphan,)),
        (f'SELECT COUNT(*) FROM {child} WHERE id = ?', (good,)),
    ])
    require_ok(answers[0], 'PRAGMA set')
    if cell(require_ok(answers[1], 'PRAGMA readback')) != '1':
        raise AssertionError('foreign_keys is not enabled on this connection')
    require_ok(answers[2], 'Parent insert')
    require_ok(answers[3], 'Valid child insert')
    if answers[4].get('type') != 'error':
        raise AssertionError('Orphan child was not rejected')
    if cell(require_ok(answers[5], 'Orphan count')) != '0':
        raise AssertionError('Orphan child persisted')
    if cell(require_ok(answers[6], 'Valid child count')) != '1':
        raise AssertionError('Valid child did not persist')
    return True


st.set_page_config(page_title='Kyoto Keiba AI | Turso compatibility v2', page_icon='🧪')
st.title('Turso v14 compatibility diagnostic (v2)')
st.caption('Separate diagnostic only. No change to production app.py or v14 source.')
st.warning('Only run against kyoto-keiba-ai-test. Results do not prove atomicity, security, or production readiness.')

# This app is public by default. Do not render controls until an explicit access gate is configured.
try:
    url = str(st.secrets['TURSO_DATABASE_URL']).strip()
    token = str(st.secrets['TURSO_AUTH_TOKEN']).strip()
    access = str(st.secrets['TURSO_PROBE_PASSWORD'])
    if not url or not token or len(access) < 12:
        raise ValueError('Required secrets are missing or access password is too short')
    api_endpoint(url)  # Reject production or unknown databases before any query.
except Exception:
    st.error('Configuration incomplete. Check dedicated app Secrets privately; no token should be shared.')
    st.stop()

password = st.text_input('Diagnostic access password', type='password')
if not hmac.compare_digest(password, access):
    st.info('Password required to display diagnostic controls.')
    st.stop()

st.success('Authorized for the dedicated test database (values hidden).')
st.info('Do not test on another database. All test tables begin with __kyoto_v14_compat_v2_.')
confirmation = st.checkbox('I understand that these tests create isolated test-only tables and records.')
if not confirmation:
    st.stop()

if st.button('Test A: Reject UPDATE and DELETE'):
    try:
        immutable_test(url, token)
        st.success('PASS: UPDATE and DELETE rejected; original row unchanged')
    except Exception:
        st.error('FAIL/INCONCLUSIVE: see local verification report; no secrets displayed')

if st.button('Test B: Enforce FOREIGN KEY'):
    try:
        foreign_key_test(url, token)
        st.success('PASS: valid relationship accepted, orphan rejected')
    except Exception:
        st.error('FAIL/INCONCLUSIVE: foreign-key behavior not proven; no secrets displayed')

st.caption('Not yet tested: atomic 12-race batch, concurrent writes, ambiguous timeout, restore, independent audit archive.')
