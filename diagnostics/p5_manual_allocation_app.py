"""Manual ticket type and stake-ratio planning, strictly NO BET / NO PREDICTION.

Real mobile-friendly Streamlit controls. Does not read or invent race/odds/model
data, place orders, persist user selections, or generate recommendations.
"""
import streamlit as st
from diagnostics.p5_manual_allocation import allocate

st.set_page_config(page_title="京都競馬AI｜予算操作",page_icon="🏇",layout="centered")
st.title("京都競馬AI｜予算・買い目の操作")
st.warning("準備中：実開催日の予測・発走前オッズ・購入機能は未接続です。これは予算配分の操作画面です。")
st.caption("金額は仮の入力値です。実際の購入・仮想投資記録は一切作成しません。")

budget=st.number_input("1日の上限予算（円）",min_value=0,max_value=1000000,value=10000,step=100)
market=st.radio("馬券の種類",("馬連","枠連"),horizontal=True)
races=st.slider("検討するレース数",min_value=1,max_value=4,value=3)
picks=st.slider("1レースの買い目数",min_value=1,max_value=3,value=2)
st.subheader("配分比率の手動調整")
weights=[]
for i in range(races):
 weights.append(st.slider(f"第{i+1}候補の配分比率（相対値）",min_value=0,max_value=100,
                          value=max(10,100//races),key=f"ratio_{i}"))
allocations=allocate(int(budget),weights)
st.subheader("入力内容の確認")
st.write({"選択":market,"候補レース数":races,"1レースの最大買い目数":picks,
          "予算上限":f"{budget:,}円","配分合計":f"{sum(allocations):,}円",
          "未配分":f"{budget-sum(allocations):,}円"})
for i,amount in enumerate(allocations):
 st.write(f"候補{i+1}：{amount:,}円（対象レース・馬番は未確定）")
st.info("実際のレース順位・買い目・期待値は表示しません。実データとモデルの認定後に接続します。")
st.caption("購入ボタンなし／外部HTTPなし／Turso・Secrets・本番アプリへの接続なし")
