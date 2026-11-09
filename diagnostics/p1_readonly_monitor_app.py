"""Read-only P1 evidence monitor for a SEPARATE diagnostic Streamlit app.

No JRA HTTP, database, secrets, wagering, or production app integration.
Historic 2026-11-07 evidence is never presented as live prediction data.
"""
import json
from pathlib import Path
import streamlit as st
from diagnostics.p1_monitor_viewmodel import summarize, StatusInvalid
from diagnostics.p1_registry_reconcile import reconcile, RegistryConflict

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "docs/diagnostics/jra_p1_batch14_96_profiles_20261106/status.json"
REGISTRY = ROOT / "docs/diagnostics/jra_p1_batch14_96_profiles_20261106/feature_rows_148.json"

st.set_page_config(page_title="京都競馬AI | 取得状況", page_icon="🏇", layout="centered")
st.title("京都競馬AI｜取得状況")
st.caption("診断専用・読み取りのみ。馬券予想や購入を行うアプリではありません。")

try:
    status = json.loads(STATUS.read_text(encoding="utf-8"))
    rows = json.loads(REGISTRY.read_text(encoding="utf-8"))
except (OSError, ValueError) as exc:
    st.error("検証記録を読み取れません。実データを推測して表示することはできません。")
    st.stop()

try:
    summary = summarize(status)
    actual = reconcile(status, rows)
except (StatusInvalid, RegistryConflict, KeyError, TypeError):
    st.error("保存された検証記録に矛盾があります。表示を停止します。")
    st.stop()

total = summary["runner_count"]
verified = summary["verified"]
pending = summary["unqueried"]
st.info("これは2026年11月7日の**終了済み京都競馬**の履歴です。次回開催の発走前情報ではありません。")
a, b, c = st.columns(3)
a.metric("出走馬", f"{total}頭")
b.metric("詳細確認", f"{verified}頭")
c.metric("未取得", f"{pending}頭")
st.progress(verified / total, text=f"プロフィール取得履歴：{verified}/{total}（{verified/total:.1%}）")
st.metric("確認済みの有効過去走", f"{summary["prior_rows"]}件")
st.subheader("レース別の取得状態（148頭の個別記録から再集計）")
for number in range(1, 13):
    r = actual["by_race"][str(number)]
    st.write(
        f"京都{number}R：過去走あり {r['with_history']}頭 / "
        f"履歴なし確認済み {r['verified_empty']}頭 / "
        f"未取得 {r['unqueried']}頭（計{r['total']}頭）"
    )
st.info(
    "詳細確認済み96頭＝過去走あり77頭＋履歴なしを確認済み19頭。"
    "未取得は52頭です。1～8Rは全馬確認済みで、残り5頭の確認分は9～12Rに属します。"
)
st.subheader("予測への利用判定")
st.error("予測不可・見送り")
st.write("発走前の新開催日データ、確定した馬ID、必要な馬場情報、当時の馬連・枠連オッズなどが揃っていません。")
with st.expander("未実証の情報"):
    for key in summary["unverified_groups"]:
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
st.divider()
st.subheader("原本と出馬表・オッズの照合（試験用）")
st.caption("既存のオフラインZIPと、その開催の構造化スナップショットJSONを両方選択した場合だけ、日時・レース・原本SHAを照合します。予測処理には接続しません。")
snapshot_upload = st.file_uploader("同じ開催のスナップショットJSON", type=["json"])
if bundle is not None and snapshot_upload is not None:
    from datetime import datetime, timezone
    from diagnostics.jra_p1_intake_bridge import inspect_bundle_and_snapshot, IntakeRejected
    try:
        raw_snapshot = snapshot_upload.getvalue()
        if len(raw_snapshot) > 250_000:
            raise IntakeRejected("snapshot_size_exceeded")
        snapshot = json.loads(raw_snapshot.decode("utf-8"))
        outcome = inspect_bundle_and_snapshot(
            bundle.getvalue(), snapshot, observed_utc=datetime.now(timezone.utc).isoformat()
        )
        st.success("ファイル間の構造・レース・取得時刻・原本SHAが一致しました。")
        st.write({"対象開催": outcome["meeting_date"], "レース": outcome["race"], "出走馬数": outcome["runner_count"]})
        st.warning("公式原本の真正性やオッズの完全性は未確認です。予測は引き続き停止しています。")
    except (IntakeRejected, ValueError, TypeError, KeyError, UnicodeError):
        st.error("ファイル間の照合に失敗しました。データの利用を許可しません。")
st.caption("本番 main/app.py、Turso、Secretsは参照・更新しません。")
