"""Kyoto AI production entrypoint. Legacy UI/predictor is intentionally removed.

The acquisition pipeline runs independently in GitHub Actions. This interface
does not invent races, odds, forecasts, or actual trading results.
"""
import streamlit as st

st.set_page_config(page_title="京都競馬AI", page_icon="🏇", layout="centered", initial_sidebar_state="collapsed")
st.markdown("""<style>
.block-container{max-width:760px;padding:1.1rem .9rem 2rem}
@media(max-width:480px){h1{font-size:1.7rem!important}}
</style>""", unsafe_allow_html=True)
st.title("🏇 京都競馬AI")
st.caption("新システム専用画面｜馬連・枠連｜スマートフォン対応")
st.info("発走前の実データと予測結果は、表示用の真正なデータ連携が確認できるまで公開しません。")
tab_budget, tab_forecast, tab_results, tab_evolution, tab_status = st.tabs(
    ["予算", "予測", "仮想成績", "AI進化", "取得状況"]
)
with tab_budget:
    st.subheader("仮想予算の上限")
    budget = st.number_input("1日の上限（仮想円）", min_value=0, max_value=1_000_000, value=10_000, step=100)
    market = st.radio("対象券種", ["馬連", "枠連"], horizontal=True)
    st.metric("予算上限", f"{budget:,}円")
    st.caption(f"{market}を選択中。予算は使い切る必要はありません。")
    st.warning("真正な発走前データを検証できていないため、買い目生成と仮想投資登録は無効です。")
with tab_forecast:
    st.subheader("推奨レース・買い目")
    st.write("推奨順位：未認定")
    st.write("発走前データ：未接続")
    st.write("買い目・オッズ：表示不可")
    st.button("仮想馬券を登録", disabled=True)
with tab_results:
    st.subheader("仮想投資の成績")
    st.write("的中率：未確定")
    st.write("回収率：未確定")
    st.write("累積損益：未確定")
    st.caption("未登録・未取得を0円の収支とは扱いません。")
with tab_evolution:
    st.subheader("AIの自己進化")
    st.write("採用モデル：実開催で未認定")
    st.write("独立監査・ロールバック：実運用未接続")
with tab_status:
    st.subheader("自動取得の状況")
    st.write("取得器：GitHub Actionsで別実行（この画面から手動起動しません）")
    st.write("2026年11月21日・22日：発走前実データの取得を計画")
    st.warning("この画面はGitHub Actionsの稼働状態をリアルタイムで検査していません。成功表示を推測で行いません。")
    st.caption("研究・開発工程 32/32｜研究卒業 12/12｜取得前準備 16/16（引継ぎ認定値）")
    st.caption("実開催接続 0/6｜実用能力の独立検証下限 0/100")
st.caption("実際の馬券購入機能はありません。旧app.pyのハッシュ予想・固定オッズは使用しません。")
