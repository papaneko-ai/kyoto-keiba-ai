"""Standalone offline research playback UI for saved P1 source archives.

Not the public prediction app. No HTTP, secrets, database, paid APIs or bets.
Every result stays LAB even when user uploads genuinely captured race data.
"""
from __future__ import annotations
import json
import streamlit as st
from diagnostics.p8_uploaded_archive_replay_lab import replay_user_supplied_lab_archive

st.set_page_config(page_title="京都競馬AI｜保存原本の研究再現",layout="centered")
st.title("京都競馬AI｜保存原本の研究用再現")
st.warning("研究・診断専用。公式データの真正性、実運用予測、馬券購入は認定しません。")
st.caption("既存P1保存ZIPとLAB_SYNTHETIC_ONLYのモデルJSONを使い、原本照合→期待値→買い目・予算→発走前凍結→任意の払戻精算を独立再実行します。")
source=st.file_uploader("既存P1の原本3点一体ZIP",type=["zip"])
trusted_sha=st.text_input("別途保存された原本ZIPのSHA256（必須）",placeholder="64桁のSHA256")
model=st.file_uploader("研究用・事前固定モデルJSON",type=["json"])
result=st.file_uploader("研究用の結果HTML（任意）",type=["html","htm"])
ticket=st.radio("券種",["馬連","枠連"],horizontal=True)
budget=st.number_input("仮想予算の上限（円）",min_value=0,max_value=1000000,value=1000,step=100)
observed=st.text_input("原本受入UTC","2026-11-13T04:05:00Z")
committed=st.text_input("研究予測の凍結UTC","2026-11-13T04:07:00Z")
result_utc=st.text_input("結果HTML取得UTC（結果を使う場合）","2026-11-14T05:10:00Z")
channel=st.selectbox("原本チャネル",["PC","SP"])
if st.button("研究用に原本から再現",disabled=source is None or model is None or len(trusted_sha.strip())!=64):
    try:
        source_bytes=source.getvalue()
        raw_model=json.loads(model.getvalue().decode("utf-8"))
        raw_result=result.getvalue() if result is not None else None
        report=replay_user_supplied_lab_archive(
            archive_bytes=source_bytes,
            archive_sha256=trusted_sha.strip().lower(),
            observed_utc=observed,channel=channel,
            frozen_model=raw_model,commit_utc=committed,
            ticket_type="QUINELLA" if ticket=="馬連" else "BRACKET",
            daily_budget_yen=int(budget),
            final_result_bytes=raw_result,
            final_result_utc=result_utc if raw_result is not None else None)
    except (ValueError,TypeError,KeyError,UnicodeError,OSError,AssertionError,ImportError):
        st.error("原本・時刻・モデル・結果の検証に失敗したため、再現結果の表示を停止しました。")
        st.stop()
    st.success("研究用再現が完了しました。実運用の真正性は未認証です。")
    st.metric("研究用買い目数",report["selected_ticket_count"])
    st.metric("研究用予算使用額",f'{report["research_stake_yen"]:,} 円')
    st.metric("未使用予算",f'{report["unused_budget_yen"]:,} 円')
    if report["research_result"] is not None:
        st.metric("研究用損益",f'{report["research_result"]["settled_fixture_profit_yen"]:,} 円')
    st.caption("検証レシート SHA256: "+report["replay_sha256"])
    st.caption("発走前の公式予測、公式結果の確認、実購入を保証するものではありません。")
