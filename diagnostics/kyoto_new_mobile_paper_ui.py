"""Kyoto AI NEW mobile-first paper-trading UI (development preview).

Legacy app.py is NOT imported, referenced, or used. No invented races, odds,
AI signals or results. No external requests, betting API or real-money actions.
"""
from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from diagnostics.p5_manual_allocation import allocate

st.set_page_config(
    page_title="京都競馬AI｜新スマホ実践画面",
    page_icon="🏇",
    layout="centered",
    initial_sidebar_state="collapsed",
)
st.markdown(
    """<style>
.block-container {max-width:720px; padding:1rem .8rem 2rem}
[data-testid="stMetricValue"] {font-size:1.7rem}
@media(max-width:480px) {
h1 {font-size:1.65rem!important}
div[data-testid="stTabs"] button {font-size:.72rem!important;padding:.35rem .25rem!important}
}
</style>""", unsafe_allow_html=True
)
st.title("🏇 京都競馬AI")
st.caption("新開発スマホ画面｜仮想投資優先・開発プレビュー")
st.warning(
    "実開催の発走前情報・予測・永続仮想通帳・公式払戻は未接続です。"
    "現在は操作画面の試作版で、実際の馬券購入は行いません。"
)

tab_budget, tab_races, tab_results, tab_evolution, tab_mode = st.tabs(
    ["予算", "予想", "成績", "AI進化", "運用設定"]
)
with tab_budget:
    st.subheader("仮想資金の設定")
    budget = st.number_input(
        "1日予算の上限（仮想円）", min_value=0, max_value=1_000_000,
        value=10_000, step=100,
        help="予算は上限です。使い切る必要はありません。",
    )
    market = st.radio("券種", ("馬連", "枠連"), horizontal=True)
    st.metric("仮想予算上限", f"{budget:,}円")
    st.caption(f"現在選択中：{market}／仮想購入は未登録")
    st.info("予算と券種だけを設定できます。実データ未接続のため購入登録はできません。")
    with st.expander("資金配分の操作練習（実レースではありません）"):
        count = st.slider("配分先の数", 1, 4, 3)
        reserve = st.slider("配分する予算の割合", 0, 100, 60, step=10)
        weights = [st.slider(f"配分先{i+1}の相対比", 0, 100, 100//count,
                             key=f"new_ui_weight_{i}") for i in range(count)]
        limit = (int(budget) * int(reserve) // 10_000) * 100
        try:
            allocation = allocate(limit, weights)
            for i, amt in enumerate(allocation):
                st.write(f"操作練習の配分先{i+1}：{amt:,}円")
            st.metric("未配分の仮想予算", f"{int(budget)-sum(allocation):,}円")
        except (ValueError, TypeError, ZeroDivisionError):
            st.error("比率が不正です。予測・仮想購入は行いません。")

with tab_races:
    st.subheader("推奨レース・買い目")
    st.info("発走前データの真正性が未確認のため、推奨レース・順位・買い目は表示しません。")
    st.caption("接続後は順位・推定確率・期待値・データ時刻・推奨理由を表示します。")
    st.button("仮想馬券を登録", disabled=True,
              help="実開催の発走前原本と永続記録が検証できるまで無効")

with tab_results:
    st.subheader("仮想投資の成績")
    st.info("正式な仮想投資記録と公式払戻は未接続です。")
    a, b = st.columns(2)
    a.metric("的中率", "未確定")
    b.metric("回収率", "未確定")
    st.metric("累積損益", "未確定")
    st.caption("速報・確定・返還・訂正を区別。未確定をゼロ円にしません。")

with tab_evolution:
    st.subheader("AIの自己進化")
    st.info("独立進化認定・ロールバックの実開催統合は未接続です。")
    st.write("使用モデル：未認定")
    st.write("候補モデル：未評価")
    st.write("進化判定：未実施")
    st.caption("モデルの採否には未使用期間の独立評価を必要とします。")

with tab_mode:
    st.subheader("運用モード")
    st.radio("現在利用できるモード", ("仮想投資のみ",), disabled=True)
    st.success("実購入機能は無効です。自動で実投資に切り替わることはありません。")
    st.markdown("**実投資への移行を検討できる条件（完成要件ではありません）**")
    st.write(
        "仮想投資の事前凍結・公式照合が正常に運用され、"
        "十分なサンプルで収益性・最大損失・較正を独立評価し、"
        "本人が資金上限を決めて明示的に選択した場合に限り検討します。"
    )
    st.warning(
        "実馬券の自動購入・自動切替は設計しません。"
        "仮に実投資をする場合も、20歳以上の利用者本人がJRAの正規窓口で手動購入し、"
        "アプリでは別の実購入記録を任意入力する方式です。"
    )
    st.caption(
        "リアルモードは未実装・未有効化。実購入は仮想投資の完成・利用に必須ではありません。"
    )
st.caption("開発用プレビュー｜旧公開app.pyの予測・画面を一切使用していません。")
