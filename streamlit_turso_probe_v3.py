"""Kyoto Keiba AI - integrated Turso test-only storage diagnostic v3.1.

REPLACE ONLY the diagnostic streamlit_turso_probe_v3.py file in GitHub.
Never import production code or modify production tables. No automatic writes.
One authenticated, consented run; append-only isolated test tables.
Existing v1/v2/v3 results are historical evidence, NOT rerun or claimed fresh.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import hmac
import json
import uuid
from urllib.parse import urlsplit

import requests

EXPECTED_HOST = 'kyoto-keiba-ai-test-papaneko-ai.aws-ap-northeast-1.turso.io'
PREFIX = '__kyoto_v14_integrated_v31_'
TIMEOUT_SECONDS = 20


def endpoint(database_url: str) -> str:
    p = urlsplit(database_url.strip())
    if (p.scheme not in ('libsql', 'https') or p.hostname != EXPECTED_HOST
            or p.username or p.password or p.query or p.fragment
            or p.path not in ('', '/') or p.port is not None):
        raise ValueError('Only the designated kyoto-keiba-ai-test database is permitted')
    return f'https://{EXPECTED_HOST}/v2/pipeline'


def sql_stmt(sql: str, *args: object) -> dict:
    def encode(value: object) -> dict:
        if value is None:
            return {'type': 'null'}
        if type(value) is int:
            return {'type': 'integer', 'value': str(value)}
        return {'type': 'text', 'value': str(value)}
    return {'sql': sql, 'args': [encode(x) for x in args], 'want_rows': True}


def pipeline(url: str, token: str, actions: list[dict]) -> list[dict]:
    # Mutations are intentionally not retried: a timeout could mean committed.
    try:
        r = requests.post(endpoint(url),
                          headers={'Authorization': 'Bearer ' + token,
                                   'Content-Type': 'application/json'},
                          json={'requests': actions + [{'type': 'close'}]},
                          timeout=TIMEOUT_SECONDS, allow_redirects=False)
        if r.status_code != 200:
            raise RuntimeError('HTTP response not successful; commit state unknown')
        body = r.json()
        results = body.get('results')
        if not isinstance(results, list) or len(results) != len(actions) + 1:
            raise RuntimeError('Unexpected response size; state unknown')
        if results[-1].get('type') != 'ok':
            raise RuntimeError('Stream close unconfirmed; state unknown')
        return results[:-1]
    except requests.RequestException as exc:
        raise RuntimeError('Transport outcome ambiguous; no automatic retry') from exc


def execute(url: str, token: str, sql: str, *args: object) -> dict:
    result = pipeline(url, token, [{'type': 'execute', 'stmt': sql_stmt(sql, *args)}])[0]
    if result.get('type') != 'ok' or result.get('response', {}).get('type') != 'execute':
        raise RuntimeError('SQL request did not succeed; manual inspection needed')
    return result['response']['result']


def rows(result: dict) -> list[list[object]]:
    return [[c.get('value') for c in row] for row in result.get('rows', [])]


def count(url: str, token: str, table: str, key: str) -> int:
    return int(rows(execute(url, token, f'SELECT COUNT(*) FROM {table} WHERE run_id = ?', key))[0][0])


def run_concurrent(url: str, token: str, run_id: str) -> dict:
    table = PREFIX + 'concurrency'
    execute(url, token, f'CREATE TABLE IF NOT EXISTS {table} (run_id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    # Two independent HTTP requests with different payloads and the SAME primary key.
    def contender(payload: str) -> int:
        result = execute(url, token,
            f'INSERT INTO {table}(run_id, payload) VALUES (?, ?) ON CONFLICT(run_id) DO NOTHING',
            run_id, payload)
        return int(result['affected_row_count'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(contender, 'writer-A')
        f2 = pool.submit(contender, 'writer-B')
        affected = [f1.result(), f2.result()]
    persisted = rows(execute(url, token, f'SELECT payload FROM {table} WHERE run_id = ?', run_id))
    if sorted(affected) != [0, 1] or len(persisted) != 1 or persisted[0][0] not in ('writer-A', 'writer-B'):
        raise AssertionError('Two-writer uniqueness contract failed')
    return {'status': 'PASS', 'detail': 'Two simultaneous insert requests; exactly one writer won',
            'affected_rows': affected, 'row_count': len(persisted)}


def run_idempotence(url: str, token: str, run_id: str) -> dict:
    table = PREFIX + 'idempotence'
    execute(url, token, f'CREATE TABLE IF NOT EXISTS {table} (run_id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    payload = 'synthetic-' + uuid.uuid4().hex
    first = execute(url, token,
        f'INSERT INTO {table}(run_id,payload) VALUES (?,?) ON CONFLICT(run_id) DO NOTHING', run_id, payload)
    if int(first['affected_row_count']) != 1:
        raise AssertionError('Initial idempotent write not confirmed')
    # Deliberately discard the successful result in a LOCAL simulation of a lost acknowledgement.
    # This is NOT an actual induced internet timeout or outage.
    readback = rows(execute(url, token, f'SELECT payload FROM {table} WHERE run_id=?', run_id))
    if readback != [[payload]]:
        raise AssertionError('Reconciliation did not identify the existing record')
    duplicate = execute(url, token,
        f'INSERT INTO {table}(run_id,payload) VALUES (?,?) ON CONFLICT(run_id) DO NOTHING', run_id, payload)
    if int(duplicate['affected_row_count']) != 0 or count(url, token, table, run_id) != 1:
        raise AssertionError('Retry duplicated or changed the original record')
    return {'status': 'PASS_SIMULATION', 'detail': 'Simulated lost acknowledgment; read-by-ID and idempotent retry succeeded. Actual network timeout not tested.'}


def digest(records: list[list[object]]) -> str:
    raw = json.dumps(records, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def run_copy_restore(url: str, token: str, run_id: str) -> dict:
    source = PREFIX + 'archive_source'
    dest = PREFIX + 'archive_reconstruction'
    for table in (source, dest):
        execute(url, token, f'''CREATE TABLE IF NOT EXISTS {table} (
            run_id TEXT NOT NULL, item_no INTEGER NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(run_id, item_no))''')
    expected = [[str(i), 'synthetic-record-' + str(i)] for i in range(1, 5)]
    for i, payload in expected:
        execute(url, token, f'INSERT INTO {source}(run_id,item_no,payload) VALUES (?,?,?)', run_id, i, payload)
    source_rows = rows(execute(url, token,
        f'SELECT item_no,payload FROM {source} WHERE run_id=? ORDER BY item_no', run_id))
    if source_rows != expected:
        raise AssertionError('Isolated source readback differs')
    for i, payload in source_rows:
        execute(url, token, f'INSERT INTO {dest}(run_id,item_no,payload) VALUES (?,?,?)', run_id, int(i), payload)
    dest_rows = rows(execute(url, token,
        f'SELECT item_no,payload FROM {dest} WHERE run_id=? ORDER BY item_no', run_id))
    if dest_rows != source_rows or digest(dest_rows) != digest(source_rows):
        raise AssertionError('Isolated reconstruction content/hash mismatch')
    return {'status': 'PASS_LIMITED', 'detail': 'Diagnostic rows copied to separate table and SHA-256 matched. NOT a full DB export, restore, or independent offsite backup.',
            'rows': len(dest_rows), 'sha256': digest(dest_rows)}


def run_all(url: str, token: str) -> dict:
    report = {
        'version': 'integrated-v3.1', 'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'database': 'kyoto-keiba-ai-test', 'run_id': str(uuid.uuid4()),
        'prior_evidence': 'v1/v2/v3 passed in earlier screenshots; not rerun here',
        'tests': {},
        'not_verified': ['Actual network outage or ambiguous remote commit',
                         'Full database export and restore', 'Independent audit archive',
                         'Whole v14 integration', 'Prediction accuracy or real data ingestion'],
    }
    tests = [('concurrent_writers', run_concurrent),
             ('lost_acknowledgment_simulation', run_idempotence),
             ('isolated_copy_and_hash', run_copy_restore)]
    for label, fn in tests:
        try:
            report['tests'][label] = fn(url, token, report['run_id'])
        except Exception as exc:
            # A failed transport leaves ambiguous state: NEVER automatically retry.
            report['tests'][label] = {'status': 'INCONCLUSIVE',
                'detail': f'{type(exc).__name__}: test did not complete; check test-only rows privately before rerun'}
            break
    report['overall'] = ('PASS_LIMITED' if len(report['tests']) == len(tests)
                         and all(t['status'].startswith('PASS') for t in report['tests'].values())
                         else 'INCONCLUSIVE')
    return report


def main() -> None:
    import streamlit as st
    st.set_page_config(page_title='Kyoto Keiba AI | Consolidated Turso test', page_icon='🧪')
    st.title('Turso consolidated diagnostic v3.1')
    st.caption('Same v3 Streamlit app. Test-only records; no v14 or production app changes.')
    st.warning('Only kyoto-keiba-ai-test. One click runs 3 additional checks. Results are limited; not production readiness.')
    try:
        url = str(st.secrets['TURSO_DATABASE_URL']).strip()
        token = str(st.secrets['TURSO_AUTH_TOKEN']).strip()
        password = str(st.secrets['TURSO_PROBE_PASSWORD'])
        endpoint(url)
        if not token or len(password) < 12:
            raise ValueError('Missing Secrets')
    except Exception:
        st.error('Diagnostic Secrets missing or wrong DB. No values displayed.')
        st.stop()
    supplied = st.text_input('Diagnostic access password', type='password')
    if not hmac.compare_digest(supplied, password):
        st.info('Password required to show controls.')
        st.stop()
    st.success('Authorized for dedicated test DB.')
    consent = st.checkbox('I agree to create isolated test-only records. No source data will be modified.')
    if not consent:
        st.stop()
    if st.button('Run all remaining automated checks (once)', type='primary'):
        st.session_state['integrated_report'] = run_all(url, token)
    report = st.session_state.get('integrated_report')
    if report:
        st.subheader('Automatic test report')
        for name, outcome in report['tests'].items():
            if outcome['status'].startswith('PASS'):
                st.success(name + ': ' + outcome['status'])
            else:
                st.error(name + ': ' + outcome['status'])
            st.caption(outcome['detail'])
        st.write('Overall: ' + report['overall'])
        st.info('Not tested: actual network outage, full DB recovery, independent audit archive, full v14 integration.')
        st.download_button('Download result JSON',
            data=json.dumps(report, ensure_ascii=False, indent=2),
            file_name='kyoto_turso_diagnostic_v31_result.json', mime='application/json')
        st.caption('Do not re-run an INCONCLUSIVE test without inspecting the test-only run ID privately.')


if __name__ == '__main__':
    main()
