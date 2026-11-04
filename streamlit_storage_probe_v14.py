"""Separate Streamlit Cloud diagnostic app; DO NOT deploy as existing app.py.
Requires streamlit, boto3 and secured Streamlit secrets; write only on click.
"""
import hmac
import json
import streamlit as st

st.set_page_config(page_title='京都競馬AI 外部保存診断 v14')
st.title('京都競馬AI 外部保存診断 v14')
st.warning('診断専用です。公開中の予想アプリには影響しません。個人情報・馬券データは送信しません。')
st.caption('書込テストではランダムな小さな検査記録を1件保存します。削除はしません。')

required = ('PROBE_PASSWORD', 'S3_BUCKET', 'S3_ACCESS_KEY_ID', 'S3_SECRET_ACCESS_KEY', 'S3_REGION')
missing = [key for key in required if not st.secrets.get(key)]
if missing:
    st.error('未設定のシークレットがあります。管理者がStreamlit Secretsを設定してください。')
    st.stop()

password = st.text_input('診断用パスワード', type='password')
if not password or not hmac.compare_digest(password, str(st.secrets['PROBE_PASSWORD'])):
    st.info('設定済みの診断パスワードを入力してください。')
    st.stop()

st.success('診断用アクセス確認済み')
st.write('書込みはボタンを押した場合のみ実行されます。')
if st.button('外部保存を1回検証する', type='primary'):
    from storage_live_probe_v14 import probe_storage, read_bucket_controls
    try:
        import boto3
    except ImportError:
        st.error('boto3 がありません。診断アプリ用の依存関係設定が必要です。')
        st.stop()

    bucket = st.secrets['S3_BUCKET']
    def factory():
        kwargs = dict(aws_access_key_id=st.secrets['S3_ACCESS_KEY_ID'],
                      aws_secret_access_key=st.secrets['S3_SECRET_ACCESS_KEY'],
                      region_name=st.secrets['S3_REGION'])
        if st.secrets.get('S3_ENDPOINT_URL'):
            kwargs['endpoint_url'] = st.secrets['S3_ENDPOINT_URL']
        return boto3.client('s3', **kwargs)
    try:
        result = probe_storage(client_factory=factory, bucket=bucket,
                               prefix='kyoto-ai/healthchecks')
        if result['status'] == 'PASS_CONNECTIVITY_ONLY':
            result.update(read_bucket_controls(factory(), bucket))
        st.json(result)
        st.download_button('診断結果JSONを保存',
                           data=json.dumps(result, ensure_ascii=False, indent=2),
                           file_name='kyoto_storage_probe_v14.json',
                           mime='application/json')
    except Exception as exc:
        st.error('設定または接続に失敗しました（機密情報を保護するため詳細は非表示）。')
        st.code(type(exc).__name__)
