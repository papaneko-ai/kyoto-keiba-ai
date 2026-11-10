# 京都競馬AI開発｜P4-02 原本連動EV比較・研究開発82％節目（2026-11-10）

## 1．最新の正本・基準
- リポジトリ `papaneko-ai/kyoto-keiba-ai`、開発ブランチ `jra-html-diagnostic-20261105`。既存開発の継続であり再設計禁止。
- ルート `KYOTO_AI_START_HERE.md`、本書、前回 `docs/KYOTO_AI_20261110_P1_ATOMIC_THREE_ORIGINALS_79PCT_MILESTONE.md`、`docs/diagnostics/kyoto_progress_rubric_v1.json` と `docs/diagnostics/kyoto_progress_evidence_v1.json`、`docs/diagnostics/kyoto_research_graduation_rubric_v1.json` と研究卒業証拠台帳を確認してから作業する。GitHub HEAD、Actions、旧原本Artifact `13482994623`、バックアップを実際に照合する。
- 固定32項目研究・開発工程 **82/100、25/32合格、残り7条件**。前回79/100、24/32より **+3点、+1条件**。加点項目 **P4-02（固定配点3点）**。採点定義も配点も変更していない。
- 研究段階卒業 **100.0%、12/12、統合6/6**（前回比±0）。実開催接続の独立検証 **0/6**、実用能力の独立検証下限 **0/100**（前回比±0）。数字を相互流用しない。

## 2．今回実装した動く機能
- `diagnostics/p4_source_bound_model_ev_research.py` を追加。既存の `diagnostics/p1_operator_original_handoff.py`、`diagnostics/p4_temporal_market_controls.py`、`diagnostics/p3_p6_research_no_bet.py`、`diagnostics/p4_research_market_risk.py` を再利用する。
- 馬連・枠連の両原本HTML bytes、保存したスナップショット、申告UTC、PC/SP解析の一致を厳格照合。発走前の鮮度、発売状態、取消、馬番・枠番・全市場価格を検証後に研究計算へ渡す。
- 予測モデル入力は **LAB_SYNTHETIC_ONLY** とLABモデル版、凍結UTC、締切UTC、特徴量SHA・名簿一致を厳格要求。実モデルや公式確率と偽装した入力は拒否。
- 既存P3馬連/枠連全組合せ確率とP4の市場期待値・確率誤差/オッズ下落ストレスを同じ原本価格で計算。採点用レシートは原本SHA・スナップショットSHA・モデルSHA・市場監査SHA・券種別リスクSHAを保持。
- 出力は研究用監査であり、実購入・実開催事前登録仮想投資・モデル昇格なし。公式の真正性や発売/取消の外部認証、実モデル較正、運用可能性は **未実証**。
- `tests/test_p4_source_bound_model_ev_research.py` 15件が成功。馬連枠連比較、同一入力再現、異なるLABモデル、名簿不一致、未来凍結時刻、価格改変、鮮度超過、発売停止、NaN、不正ストレス境界、偽りの公式プロビナンス等を確認。

## 3．再現可能なGitHub成功証拠
- 新機能15件・全体CI成功：**run 42766405993 / job 129663813820 / SHA `e2b7ab43eca234b2c7bdf44f73c64dccb7179e11`**。この時点で固定開発79％を維持。
- 固定証拠台帳にP4-02を追加、従来のP1～P8全項目を消さずに保存。
- 固定基準再採点success：**run 42766589224 / job 129664408814 / SHA `67f22f8d6c9759a5fad89dacabb5f52d289f5c92`**。CIログ `KYOTO_PROGRESS_VERIFIED=82%`、`KYOTO_RESEARCH_GRADUATION=100.0%`、`KYOTO_RESEARCH_TO_LIVE_VERIFIED=0/6`、`KYOTO_OPERATIONAL_VERIFIED=0/100`。
- 本書のpushをトリガーに `.github/workflows/kyoto-ai-milestone-recovery-archive.yml` が最新コミットのGitソースZIP、`SHA256SUMS.txt`、復旧manifestを作成する。**最終SHAのバックアップと継続CI成功を実確認するまで作業完了とは言わない**。

## 4．次の重点・禁止事項
- 完成した研究用受入口・取得PC/SP切替・馬連枠連原本解析・厳格時刻検査・P3/P4モデルEVの成果を、正式に許容される実開催発走前の公式データへ接続する。ただし真正性、発走前取得時刻、発売・取消の確証が独立にない限り運用へ開放しない。
- 既存のP5予算・レース順位、P6事前登録型仮想投資、P7未使用時系列の自動進化・悪化復帰、P8スマホUIを維持して連動させる。固定32項目の残り7条件は実装＋テスト＋run/job/SHAが揃うときだけ進捗認定。
- 旧公開app.py、main、Turso、Secrets、実購入機能、公開モデルを無断変更しない。データ未取得時は架空の実開催予測・購入推奨を出さない。趣味プロジェクトを業務用Work/Codexと混同しない。

## 5．新チャット継続指示
「`papaneko-ai/kyoto-keiba-ai` の開発ブランチ `jra-html-diagnostic-20261105` を継続。まず `KYOTO_AI_START_HERE.md`・本82％パック・固定2種類の採点ルーブリックと台帳・原本Artifact・HEAD/Actions/復旧ZIPを照合する。最新研究開発82％(25/32)、研究卒業100％(12/12)、独立実開催接続0/6、独立実用能力下限0/100を区別。既存P1～P8をやり直さず、許可・真正性を裏付けられる実開催発走前データをP1→P3/P4→P5/P6→P7/P8に接続する。実用根拠がなければ停止。main/Turso/Secrets/旧公開アプリ/実購入は無断変更せず、節目は固定点数の増減理由・成功run/job/SHA・復旧ZIPで判定する。」
