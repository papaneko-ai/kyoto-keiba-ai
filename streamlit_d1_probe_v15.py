"""Independent D1 diagnostic UI. Not a horse-racing prediction application."""
import hmac
import json
import streamlit as st

from d1_connection_probe_v15 import read_only_check, write_once_check, verify_account_token, diagnose_d1_access, ProbeError

st.set_page_config(page_title="京都競馬AI D1認証診断 v15.2")
st.title("京都競馬AI D1認証診断 v15.2")
st.warning("診断用です。実際の馬券・予想・個人情報は保存しません。")

need = ("CF_ACCOUNT_ID", "CF_D1_DATABASE_ID", "CF_D1_API_TOKEN", "PROBE_PASSWORD")
missing = [k for k in need if not st.secrets.get(k)]
if missing:
    st.error("接続設定が未完了です。Streamlit Secretsに4つの設定項目が必要です。")
    st.caption("不足している設定名: " + ", ".join(missing))
    st.stop()

pwd = st.text_input("診断用パスワード", type="password")
if not pwd or not hmac.compare_digest(pwd, str(st.secrets["PROBE_PASSWORD"])):
    st.info("管理者用パスワードを入力してください。")
    st.stop()

config = dict(account_id=str(st.secrets["CF_ACCOUNT_ID"]),
              database_id=str(st.secrets["CF_D1_DATABASE_ID"]),
              token=str(st.secrets["CF_D1_API_TOKEN"]))

st.subheader("① アカウントAPIトークンの有効性確認")
st.caption("Cloudflareの公式トークン検証APIへ読み取りリクエストを1回送ります。データベースは変更しません。")
if st.button("トークン認証を検証", key="verify_account_token"):
    try:
        report = verify_account_token(account_id=config["account_id"], token=config["token"])
        st.json(report)
    except ProbeError as exc:
        st.error("トークンの認証確認に失敗しました。")
        st.code(str(exc))

st.divider()
st.subheader("② D1の2段階認可診断（読み取り専用）")
st.caption("DB情報取得（GET）と SELECT 1（POST）を各1回実行し、HTTP状態とエラー番号だけを表示します。保存処理はありません。")
if st.button("認可エラーの原因を診断", key="access_diag"):
    try:
        st.json(diagnose_d1_access(**config))
    except ProbeError as exc:
        st.error("診断に失敗しました。")
        st.code(str(exc))

st.divider()
st.subheader("③ 読み取り専用のD1接続確認")
st.caption("SELECT 1 のみ実行します。既存テーブルやデータは変更しません。")
if st.button("接続確認を実行", key="read_only"):
    try:
        st.json(read_only_check(**config))
    except Exception as exc:
        st.error("接続確認に失敗しました。秘密情報を守るため詳細は表示しません。")
        st.code(type(exc).__name__ if not hasattr(exc, "args") else
                (str(exc) if str(exc) in (
                    "INVALID_IDS", "MISSING_TOKEN", "NETWORK_ERROR", "NON_200_RESPONSE",
                    "API_REPORTED_FAILURE", "SQL_REPORTED_FAILURE", "INVALID_API_RESPONSE",
                    "HTTP_400", "HTTP_401", "HTTP_403", "HTTP_404", "HTTP_429") else type(exc).__name__))

st.divider()
st.subheader("④ 少量の保存試験（任意）")
st.caption("ボタンを押した場合だけ専用テーブルとランダムな検査記録を1件作ります。削除しません。")
confirmed = st.checkbox("試験用テーブルと1件の記録を保存することを了承します")
if st.button("1件の保存と再読込みを検証", disabled=not confirmed, key="write_once"):
    report = write_once_check(**config)
    st.json(report)
    st.download_button("診断結果JSONを保存", json.dumps(report, ensure_ascii=False, indent=2),
                       file_name="kyoto_d1_probe_result_v15.json", mime="application/json")
st.caption("成功してもバックアップ・改ざん防止・災害復旧・長期保存を証明したことにはなりません。")
