"""One-click Streamlit Cloud network test; NOT a production racing-data feed.

Only a fixed, real, publicly listed JRA race page is fetched on user request.
No automatic polling, arbitrary URL inputs, redirects, storage of HTML or odds.
Availability does not establish permission for automated commercial reuse.
"""
import datetime as dt
import json
import re
import time
from urllib.parse import urlsplit

import requests
import streamlit as st

APP_VERSION = '2026-11-02-cloud-probe-v3'
TARGETS = {
    'JRA公式（トップ）': 'https://www.jra.go.jp/',
    'JRAスマートフォン版（トップ）': 'https://sp.jra.jp/',
    'GitHub公開データ配信': 'https://raw.githubusercontent.com/',
}
# A verified Oct 31 2026 Kyoto race 8 official entry page, not generated URL.
RACE_URL = ('https://sp.jra.jp/JRADB/accessD.html?'
            'CNAME=sw01dde0108202604100820261031%2FD2')
MAX_BYTES = 256 * 1024


def safe_target(url):
    parsed = urlsplit(url)
    return (parsed.scheme == 'https' and parsed.username is None and
            parsed.password is None and parsed.port is None and
            (url in TARGETS.values() or url == RACE_URL))


def probe_head(url, session=None):
    if not safe_target(url) or url == RACE_URL:
        raise ValueError('許可されていない接続先です')
    client = session or requests
    start = time.monotonic()
    with client.head(url, timeout=7, allow_redirects=False,
                     headers={'User-Agent': 'KyotoRacingConnectivityCheck/2.0'}) as r:
        code = int(r.status_code)
        return {'接続先': urlsplit(url).hostname, 'HTTP': code,
                '結果': ('応答あり（データ取得は未検証）' if code == 200 else
                       'リダイレクト（追跡なし）' if code in (301,302,303,307,308) else
                       '制限（403/429）' if code in (403,429) else '要確認'),
                '所要ms': round(1000 * (time.monotonic() - start))}


def classify_probe(status, location='', size=0):
    """Backward-compatible classification for the original probe tests."""
    if status in (403, 429):
        return 'アクセス制限'
    if status in (301, 302, 303, 307, 308):
        return 'リダイレクト（追跡なし）'
    if status == 200:
        return '応答あり（データ取得は未検証）'
    return '要確認'


def probe(url, session=None):
    """Legacy test API; one HEAD request without following redirects."""
    if not safe_target(url) or url == RACE_URL:
        raise ValueError('許可されていない接続先です')
    client = session or requests
    response = client.head(url, timeout=7, allow_redirects=False,
                           headers={'User-Agent': 'KyotoRacingConnectivityCheck/2.0'})
    try:
        status = int(response.status_code)
        return {'result': classify_probe(status),
                'redirect': status in (301, 302, 303, 307, 308),
                'status': status}
    finally:
        response.close()


def inspect_race_html(html):
    """Return only bounded boolean diagnostics, not horse data or raw HTML."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.get_text(' ', strip=True)
    date_ok = bool(re.search(r'2026\s*年\s*10\s*月\s*31\s*日', content))
    kyoto_ok = '京都' in content
    race_ok = bool(re.search(r'8\s*(?:R|レース)', content))
    entries_likely = bool('ミサビスケッツ' in content and 'ストラテージュ' in content)
    return {'対象日一致': date_ok, '京都開催を確認': kyoto_ok,
            '8Rを確認': race_ok, '実在の馬名を2件確認': entries_likely,
            'ページ構造検出': bool(soup.find('table'))}


def probe_race(session=None):
    client = session or requests
    start = time.monotonic()
    with client.get(RACE_URL, timeout=(5, 10), stream=True, allow_redirects=False,
                    headers={'User-Agent': 'KyotoRacingConnectivityCheck/2.0'}) as r:
        code = int(r.status_code)
        result = {'HTTP': code, '検査対象': '2026-10-31 京都8RのJRA公式出馬表',
                  'コンテンツ取得': False, '判定': 'データ未取得'}
        if code != 200:
            result['判定'] = ('リダイレクト停止' if code in (301,302,303,307,308)
                            else 'アクセス制限' if code in (403,429) else 'HTTPエラー')
            return result
        content_type = r.headers.get('Content-Type', '').lower()
        if 'html' not in content_type:
            result['判定'] = 'HTML以外の応答'
            return result
        received = bytearray()
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                received.extend(chunk)
                if len(received) > MAX_BYTES:
                    result['判定'] = 'サイズ超過で中止'
                    return result
        if not received:
            result['判定'] = '内容が空'
            return result
        # Streaming responses must not access r.apparent_encoding after iter_content:
        # requests can raise RuntimeError('content already consumed').
        # Detect encoding directly from the received byte buffer instead.
        from bs4 import UnicodeDammit
        decoded = UnicodeDammit(bytes(received), is_html=True).unicode_markup
        if decoded is None:
            decoded = bytes(received).decode('utf-8', errors='replace')
        flags = inspect_race_html(decoded)
        result.update(flags)
        result['コンテンツ取得'] = True
        result['判定'] = ('対象の出馬表らしきHTMLを確認（再利用許可とは別）'
                          if all([flags['対象日一致'], flags['京都開催を確認'],
                                  flags['8Rを確認'], flags['実在の馬名を2件確認']])
                          else '応答は取得したが対象情報が不完全')
        result['所要ms'] = round(1000 * (time.monotonic() - start))
        return result


def main():
    st.set_page_config(page_title='京都競馬AI｜クラウド実データ接続試験', page_icon='🏇', layout='centered')
    st.title('🏇 京都競馬AI｜クラウド接続・実ページ試験')
    st.caption('版：' + APP_VERSION)
    st.info('診断専用アプリです。競馬予想・データの継続収集は行いません。')
    st.write('① 通常の通信確認（各サイトにHEAD通信を1回）')
    if st.button('通信を確認', use_container_width=True):
        results = []
        for name, url in TARGETS.items():
            try:
                record = probe_head(url)
                record['接続先'] = name
                results.append(record)
            except requests.RequestException as err:
                results.append({'接続先': name, 'HTTP': '-', '結果': type(err).__name__})
        st.session_state['network'] = results
    if 'network' in st.session_state:
        st.dataframe(st.session_state['network'], hide_index=True, use_container_width=True)
    st.divider()
    st.write('② 2026年10月31日 京都8R・公式出馬表への実際のGET通信（1回だけ）')
    st.caption('レスポンスの内容は保存せず、対象日・京都8R・馬名2件を確認するだけです。')
    if st.button('京都8Rの実ページを確認', type='primary', use_container_width=True):
        try:
            st.session_state['race_probe'] = probe_race()
        except requests.RequestException as err:
            st.session_state['race_probe'] = {'判定': type(err).__name__, 'HTTP': '-'}
        except Exception as err:
            st.session_state['race_probe'] = {
                '判定': '試験失敗: ' + type(err).__name__,
                '原因の手がかり': str(err)[:180],
                'HTTP': '未確定（結果の組み立て前に例外）',
            }
    if 'race_probe' in st.session_state:
        st.json(st.session_state['race_probe'])
    if 'network' in st.session_state or 'race_probe' in st.session_state:
        payload = {'version': APP_VERSION,
                   'run_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                   'network': st.session_state.get('network'),
                   'race_probe': st.session_state.get('race_probe')}
        st.download_button('診断結果JSONを保存', json.dumps(payload, ensure_ascii=False, indent=2),
                           file_name='kyoto_cloud_probe_result.json', mime='application/json')
    st.warning('通信成功は、JRA等からの自動収集・再利用が許諾された証明ではありません。')
    st.caption('元のapp.pyは変更不要です。無料の継続データ供給と馬連オッズ取得は別途検証が必要です。')


if __name__ == '__main__':
    main()
