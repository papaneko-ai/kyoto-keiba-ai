"""Integrated mobile-first diagnostics + manual budget workflow (NO BET).

Read-only historical data and interactive manual budget plan share one screen.
Never labels historical data as current, invents races, or creates predictions.
"""
import json
from pathlib import Path
import streamlit as st
from diagnostics.p1_monitor_viewmodel import summarize,StatusInvalid
from diagnostics.p5_manual_allocation import allocate
from diagnostics.rg06_repeatable_mobile_e2e_lab import repeatable_research_e2e, ReproducibilityRejected

ROOT=Path(__file__).resolve().parents[1]
STATUS=ROOT/"docs/diagnostics/jra_p1_batch14_96_profiles_20261106/status.json"
st.set_page_config(page_title="京都競馬AI｜モバイル準備画面",page_icon="🏇",layout="centered")
st.title("京都競馬AI｜モバイル準備画面")
st.error("実際の予想・購入・仮想投資は停止中。以下は保存済み過去データの診断と手動予算計画です。")
try:
 historical=summarize(json.loads(STATUS.read_text(encoding="utf-8")))
except (OSError,ValueError,StatusInvalid,KeyError,TypeError):
 st.error("履歴原本の確認記録が無効です。数値の推測表示を停止します。")
 st.stop()
st.subheader("実データ取得の確認状況")
st.caption("2026年11月7日京都競馬・終了済み12R。現在の出馬表や発走前オッズではありません。")
a,b=st.columns(2)
a.metric("保存済み出馬表",f"{historical['runner_count']}頭")
b.metric("プロフィール確認",f"{historical['verified']}頭")
st.progress(historical["verified"]/historical["runner_count"],
            text=f"履歴確認率：{historical['verified']}/{historical['runner_count']}")
st.info(f"未取得：{historical['unqueried']}頭。実開催日・当時のオッズは未認証。")
st.subheader("手動予算計画")
st.caption("候補は仮の番号です。レース順位・買い目・期待値を推奨していません。")
budget=st.number_input("1日上限予算（円）",min_value=0,max_value=1_000_000,value=10000,step=100)
market=st.radio("券種",("馬連","枠連"),horizontal=True)
race_count=st.slider("候補数（最大4）",min_value=1,max_value=4,value=3)
pick_count=st.slider("候補あたりの買い目数（最大3）",min_value=1,max_value=3,value=2)
weights=[st.slider(f"候補{i+1}の相対配分",0,100,100//race_count,key=f"weight_{i}")
         for i in range(race_count)]
amounts=allocate(int(budget),weights)
st.write({"券種":market,"買い目数上限":pick_count,"配分計":f"{sum(amounts):,}円",
          "未配分":f"{int(budget)-sum(amounts):,}円"})
for i,amount in enumerate(amounts):
 st.write(f"候補{i+1}：{amount:,}円")
st.subheader("研究用E2E再現性診断")
st.caption("仮想モデル・模擬オッズ・模擬払戻による独立した2回の再実行です。保存済み過去の確認記録の原本SHAを紐付けますが、実競馬予測や仮想投資の実開催実績ではありません。")
try:
 audit=repeatable_research_e2e(
  budget_yen=int(budget),
  ticket_type="QUINELLA" if market=="馬連" else "BRACKET",
  historical_status_bytes=STATUS.read_bytes())
 st.success("研究用の同一入力・同一結果：2回一致")
 st.write({"研究用券種":market,
           "研究用E2E再現":f"{audit['independent_replays']}回一致",
           "研究用配分額":f"{audit['fixture_market_spent_yen']:,}円",
           "実開催データ検証":"未実施"})
 st.caption("研究E2E SHA256："+audit["receipt_sha256"])
except (OSError,ValueError,KeyError,TypeError,ReproducibilityRejected):
 st.error("研究用E2Eの再現検証に失敗したため、検証結果の表示を停止します。")
 st.stop()
st.warning("未接続：実際のレース選定、発走前価格、モデル、仮想投資、払戻精算。")
st.caption("読み取り専用・外部通信なし・購入ボタンなし・本番アプリ変更なし")
