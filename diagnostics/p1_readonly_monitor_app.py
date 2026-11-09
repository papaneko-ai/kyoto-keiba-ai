"""Read-only P1 evidence monitor for a SEPARATE diagnostic Streamlit app.

No JRA HTTP, database, secrets, wagering, or production app integration.
Historic 2026-11-07 evidence is never presented as live prediction data.
"""
import json
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "docs/diagnostics/jra_p1_batch14_96_profiles_20261106/status.json"

st.set_page_config(page_title="京都競馬AI | 取得状況", page_icon="🏇", layout="centered")
st.title("京都競馬AI｜取得状況")
st.caption("診断専用・読み取りのみ。馬券予想や購入を行うアプリではありません。")

try:
    status = json.loads(STATUS.read_text(encoding="utf-8"))
except (OSError, ValueError) as exc:
    st.error("検証記録を読み取れません。実データを推測して表示することはできません。")
    st.stop()

expected = "jra_kyoto_p1_96_profiles_eight_complete_races.v1"
if status.get("schema_version") != expected:
    st.error("記録の版が想定と異なります。表示を停止しました。")
    st.stop()

total = status["runner_count"]
verified = status["profile_details_source_verified"]
pending = status["detailed_profiles_unqueried"]
if (total, verified, pending) != (148, 96, 52) or verified + pending != total:
    st.error("保存された実績値に矛盾があります。確認できるまで表示を停止します。")
    st.stop()

st.info("これは2026年11月7日の**終了済み京都競馬**の履歴です。次回開催の発走前情報ではありません。")
a, b, c = st.columns(3)
a.metric("出走馬", f"{total}頭")
b.metric("詳細確認", f"{verified}頭")
c.metric("未取得", f"{pending}頭")
st.progress(verified / total, text=f"プロフィール取得履歴：{verified}/{total}（{verified/total:.1%}）")
st.metric("確認済みの有効過去走", f"{status['total_finished_prior_rows']}件")
st.subheader("詳細確認済みのレース")
races = status.get("completed_race_runner_counts", {})
for number in range(1, 13):
    if str(number) in races:
        st.write(f"京都{number}R：詳細 {races[str(number)]}頭確認")
    else:
        st.write(f"京都{number}R：全馬の詳細確認は未完了")

st.subheader("予測への利用判定")
st.error("予測不可・見送り")
st.write("発走前の新開催日データ、確定した馬ID、必要な馬場情報、当時の馬連・枠連オッズなどが揃っていません。")
with st.expander("未実証の情報"):
    for key in status.get("unverified_groups", []):
        st.write(f"・{key}")
if not status.get("permanent_html_archive_completed"):
    st.warning("公式HTML原本の期限外長期保全は完了していません。")

st.divider()
st.subheader("オフライン受渡しZIPの整合性検査")
st.caption("ご自身が適切に保存したファイルのみ使用してください。ZIPの整合性検査はJRAの正式認証ではありません。")
bundle = st.file_uploader("P1のオフライン受渡しZIP", type=["zip"])
if bundle is not None:
    from datetime import datetime, timezone
    from diagnostics.jra_p1_offline_handoff import import_bundle
    try:
        result = import_bundle(bundle.getvalue(), observed_utc=datetime.now(timezone.utc))
        st.success("ZIP内部の形式・ハッシュは整合しています。")
        st.write({"対象日": result["meeting_date"], "原本数": result["source_count"]})
        st.warning("公式原本の真正性・取得権限・開催前の予測利用は未証明のため、予測不可です。")
    except (ValueError, OSError, KeyError):
        st.error("ZIPの整合性を確認できません。取込を拒否しました。")
st.caption("本番 main/app.py、Turso、Secretsは参照・更新しません。")
