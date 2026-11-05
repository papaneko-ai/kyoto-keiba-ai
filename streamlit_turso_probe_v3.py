"""Independent Turso v14 atomic 12-race batch probe (v3).

STRICTLY diagnostic. Only the dedicated kyoto-keiba-ai-test DB is accepted.
No real race data, v14 code or production app imports. No automatic SQL writes.
One-shot conditional transaction batch; separate readback. No retry on ambiguity.
"""
from __future__ import annotations

import hmac
import uuid
from urllib.parse import urlsplit

import requests
import streamlit as st

EXPECTED_HOST = 'kyoto-keiba-ai-test-papaneko-ai.aws-ap-northeast-1.turso.io'
TABLE = '__kyoto_v14_compat_v3_race_batch'


def api_endpoint(url: str) -> str:
    parts = urlsplit(url.strip())
    if (parts.scheme not in ('libsql', 'https') or parts.hostname != EXPECTED_HOST
            or parts.username or parts.password or parts.query or parts.fragment
            or parts.path not in ('', '/') or parts.port is not None):
        raise ValueError('Only the designated test database is allowed')
    return 'https://' + EXPECTED_HOST + '/v2/pipeline'


def stmt(sql: str, *args) -> dict:
    values = [{'type': 'integer', 'value': str(v)} if isinstance(v, int)
              else {'type': 'text', 'value': str(v)} for v in args]
    return {'sql': sql, 'args': values, 'want_rows': True}


def ok_step(index: int) -> dict:
    return {'type': 'ok', 'step': index}


def make_batch(batch_id: str, inject_failure: bool) -> list[dict]:
    """Steps: BEGIN(0), inserts(1..12), COMMIT(13), conditional ROLLBACK(14).

    Each insert depends on previous step succeeding. A duplicate race number in
    slot 8 intentionally violates UNIQUE(batch_id,race_no). Any failed insert
    skips subsequent INSERTs + COMMIT, then executes ROLLBACK.
    """
    steps = [{'stmt': stmt('BEGIN IMMEDIATE')}]
    for race_no in range(1, 13):
        actual = 6 if inject_failure and race_no == 8 else race_no
        steps.append({
            'condition': ok_step(len(steps) - 1),
            'stmt': stmt(f'INSERT INTO {TABLE} (batch_id, race_no, marker) VALUES (?, ?, ?)',
                         batch_id, actual, 'diagnostic-only'),
        })
    commit_index = len(steps)
    steps.append({'condition': ok_step(commit_index - 1), 'stmt': stmt('COMMIT')})
    steps.append({'condition': {'type': 'not', 'cond': ok_step(commit_index)},
                  'stmt': stmt('ROLLBACK')})
    return steps


def pipeline(url: str, token: str, requests_list: list[dict]) -> list[dict]:
    response = requests.post(
        api_endpoint(url),
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
        json={'baton': None, 'requests': requests_list + [{'type': 'close'}]},
        timeout=25, allow_redirects=False,
    )
    if response.status_code != 200:
        raise RuntimeError('Transport failed or ambiguous; do not retry blindly')
    body = response.json()
    results = body.get('results')
    if (not isinstance(results, list) or len(results) != len(requests_list) + 1
            or results[-1].get('type') != 'ok'):
        raise RuntimeError('Unexpected pipeline response; do not retry blindly')
    return results[:-1]


def one_result(url: str, token: str, sql: str, *args) -> dict:
    results = pipeline(url, token, [{'type': 'execute', 'stmt': stmt(sql, *args)}])
    if results[0].get('type') != 'ok':
        raise RuntimeError('SQL request not confirmed')
    return results[0]['response']['result']


def setup(url: str, token: str) -> None:
    one_result(url, token, f'''CREATE TABLE IF NOT EXISTS {TABLE} (
        batch_id TEXT NOT NULL, race_no INTEGER NOT NULL CHECK(race_no BETWEEN 1 AND 12),
        marker TEXT NOT NULL, UNIQUE(batch_id, race_no))''')


def count_records(url: str, token: str, batch_id: str) -> int:
    result = one_result(url, token,
                        f'SELECT COUNT(*) FROM {TABLE} WHERE batch_id = ?', batch_id)
    return int(result['rows'][0][0]['value'])


def inspect_batch_response(response: dict, inject_failure: bool) -> bool:
    if response.get('type') != 'ok' or response.get('response', {}).get('type') != 'batch':
        raise RuntimeError('Batch execution result unavailable')
    result = response['response'].get('result', {})
    successes = result.get('step_results')
    errors = result.get('step_errors')
    if not isinstance(successes, list) or not isinstance(errors, list) or len(successes) != 15 or len(errors) != 15:
        raise RuntimeError('Invalid batch result arrays')
    if not inject_failure:
        if any(s is None or e is not None for s, e in zip(successes[:14], errors[:14])):
            raise AssertionError('Success-path transaction did not complete')
        if successes[14] is not None or errors[14] is not None:
            raise AssertionError('Unexpected rollback after successful COMMIT')
        return True
    if (any(s is None or e is not None for s, e in zip(successes[:8], errors[:8]))
            or successes[8] is not None or errors[8] is None):
        raise AssertionError('Expected duplicate failure at slot 8 was not observed')
    if any(s is not None or e is not None for s, e in zip(successes[9:14], errors[9:14])):
        raise AssertionError('Later inserts or COMMIT unexpectedly executed')
    if successes[14] is None or errors[14] is not None:
        raise AssertionError('ROLLBACK was not confirmed')
    return True


def run_atomic_test(url: str, token: str, inject_failure: bool) -> tuple[str, int]:
    setup(url, token)
    batch_id = str(uuid.uuid4())
    steps = make_batch(batch_id, inject_failure)
    results = pipeline(url, token, [{'type': 'batch', 'batch': {'steps': steps}}])
    inspect_batch_response(results[0], inject_failure)
    count = count_records(url, token, batch_id)
    expected = 0 if inject_failure else 12
    if count != expected:
        raise AssertionError('Readback count mismatch; expected %d, got %d' % (expected, count))
    return batch_id, count


def main() -> None:
    st.set_page_config(page_title='Kyoto Keiba AI | Turso atomicity v3', page_icon='🧪')
    st.title('Turso 12-race atomicity diagnostic (v3)')
    st.caption('Independent probe only: no production app.py or v14 modifications.')
    st.warning('Only test against kyoto-keiba-ai-test. Uses synthetic identifiers, never real races.')
    try:
        url = str(st.secrets['TURSO_DATABASE_URL']).strip()
        token = str(st.secrets['TURSO_AUTH_TOKEN']).strip()
        password_secret = str(st.secrets['TURSO_PROBE_PASSWORD'])
        api_endpoint(url)
        if not token or len(password_secret) < 12:
            raise ValueError('Missing required credentials')
    except Exception:
        st.error('Dedicated diagnostic Secrets are incomplete. Values will not be shown.')
        st.stop()
    supplied = st.text_input('Diagnostic access password', type='password')
    if not hmac.compare_digest(supplied, password_secret):
        st.info('Password required to display diagnostic controls.')
        st.stop()
    st.success('Access authorized for dedicated test DB (credential values hidden).')
    consent = st.checkbox('I understand that these isolated tests create diagnostic-only records.')
    if not consent:
        st.stop()
    if st.button('Test C1: Commit exactly 12 synthetic race records'):
        try:
            identifier, count = run_atomic_test(url, token, inject_failure=False)
            st.success(f'PASS: COMMIT confirmed; {count} records read back')
            st.caption('Diagnostic batch ID (not secret): ' + identifier)
        except Exception:
            st.error('FAIL / INCONCLUSIVE. Do not click again automatically; inspect privately.')
    if st.button('Test C2: Inject duplicate at race 8; verify full ROLLBACK'):
        try:
            identifier, count = run_atomic_test(url, token, inject_failure=True)
            st.success(f'PASS: ROLLBACK confirmed; {count} records remain')
            st.caption('Diagnostic batch ID (not secret): ' + identifier)
        except Exception:
            st.error('FAIL / INCONCLUSIVE. Do not click again automatically; inspect privately.')
    st.caption('Not yet validated: concurrent writers, network timeout ambiguity, recovery/export, independent audit archive, full v14 integration.')


if __name__ == '__main__':
    main()
