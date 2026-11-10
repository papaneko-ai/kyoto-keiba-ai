# 京都競馬AI・P1-04研究開発79％節目／復旧・完全継続指示（2026-11-10）

## 1. 正本・対象
- GitHub `papaneko-ai/kyoto-keiba-ai` 開発ブランチ `jra-html-diagnostic-20261105`。
- 最初に `KYOTO_AI_START_HERE.md`、本書、前回 `docs/KYOTO_AI_20261110_P1_PCSP_FALLBACK_73PCT_MILESTONE.md`、`docs/KYOTO_AI_20261110_RG06_RESEARCH_GRADUATION_100PCT_MILESTONE.md`、`docs/diagnostics/kyoto_progress_rubric_v1.json`、`docs/diagnostics/kyoto_progress_evidence_v1.json`、研究卒業固定12条件と証拠、最新HEAD・Actions・保存済みP1原本Artifact `13482994623` を再確認。既存P1～P8を再設計し直さない。

## 2. 実測得点
- **固定32条件の研究・開発工程認定：79/100、24/32合格、8条件未達**。前回73/100、23/32より**+6点、+1条件**。新規P1-04（元から配点6点）に対する研究用検証合格のみ。
- **研究段階卒業：100.0%、12/12、統合6/6**。前回差±0。固定採点基準の変更なし。
- **独立検証済み実競馬接続：0/6**、**独立検証済み実用能力の下限：0/100**。前回差±0。研究用の受入で実開催の取得成功や適切な購入を主張しない。

## 3. 新実装と再利用
- `diagnostics/p1_atomic_dual_market_handoff.py` は、外部から渡された出馬表・馬連・枠連の原本bytesと申告時刻・URLをまとめ、既存の`diagnostics/jra_p1_offline_handoff.py` と`diagnostics/p1_operator_original_handoff.py`、`diagnostics/p1_three_original_dual_intake.py`を利用して、原本に一致する馬番/枠番/馬名、両券種の価格・発売状態、期限・時刻を検査。合格した場合だけ、原本bundle＋snapshot＋非実用認定レシートの一つのZIPへ保存する。
- ZIP内部の時刻・属性を固定して同じ入力なら完全一致のbytesにする。独立SHA256・入力時刻・券種・チャネル検査をした後でのみ再読込可能。既存archiveは上書き禁止。無許諾HTTPは呼ばない。
- `tests/test_p1_atomic_dual_market_handoff.py` に15件。欠損、馬連/枠連価格偽装、時刻超過、過去の最終オッズ混入、発売停止、URL差替え、保存後の改竄、不正な公式認証フラグ、再起動・冪等性を含める。
- CI run `42765212543`はテスト原本の鮮度時刻が不整合で失敗。修正後run `42765279909`はZIPのデフォルトmember時刻による非決定論を検出。ZIP memberのZipInfo日時と属性を固定して再現性不良を根治。**失敗した実行を成功と記録しない**。
- 15件と全CI成功 run **42765350116** / job **129660437249** / SHA `bb9340d03e22a06523d5de4984d2b593efc5b0f9`。
- `docs/diagnostics/kyoto_progress_evidence_v1.json`にP1-04の前記run/job/SHAと実装・テストを固定登録。次の固定採点success run **42765494129** / job **129660916673** / SHA `8d6ce190d459c28c4176a8d55128f5ca5edabb61`。CIログ `KYOTO_PROGRESS_VERIFIED=79%`、`KYOTO_RESEARCH_GRADUATION=100.0%`、`KYOTO_RESEARCH_TO_LIVE_VERIFIED=0/6`、`KYOTO_OPERATIONAL_VERIFIED=0/100`。
- これらはLAB原本の結合検証であってJRA真正性・発走前実時刻・販売取消等の外部認証ではない。P1-04の工学的受入にのみ加点した。

## 4. バックアップ・復旧
- 本書pushにより`.github/workflows/kyoto-ai-milestone-recovery-archive.yml`を動かす。Git追跡ソースZIPとSHA256SUMS、当該commit manifestをGitHub Artifactで保存し、同一SHAのcontinuity CI成功を確認後に完成として報告する。
- 旧原本Artifact `13482994623`、前回73%バックアップブランチ `backup/kyoto-ai-development-73pct-20261110`、Artifact `13738633615` は削除しない。
- 新しいバックアップrun/job/SHA/digestは実際にAPIで検証してから別途記録する。数字を予想で書かない。

## 5. 次工程
- **優先：許諾・真正性を独立に裏付けられる実開催の公式PC/SP発走前出馬表・馬連/枠連オッズ・取消・発売状態・UTCの取得経路**。認証未達なら停止。過去の確定オッズを発走前価格に偽装しない。
- P1-03 PC/SP切替、今回の原本3点一体検証、P4価格鮮度、P3確率・EV、P5実開催買い目予算、P6事前登録型仮想投資・公式精算、P7未使用時系列検証・悪化復帰、P8スマホ版と接続する。固定32条件の残り8条件に実機能と成功run/job/SHAが揃うまで加点しない。
- ALG-01～13、EVO-01～08、P1～P8、馬連枠連・上限予算・仮想投資・自動進化・時系列未使用・スマホ軽量・原則無料を保持。
- main、Turso、Secrets、旧公開アプリ、実購入機能・公開モデルは無断変更しない。

## 6. 新チャット引継ぎ
「`papaneko-ai/kyoto-keiba-ai`の開発ブランチ`jra-html-diagnostic-20261105`を継続し、`KYOTO_AI_START_HERE.md`と本79％パック・前回73％・固定採点証拠と研究卒業12条件・原本Artifactを実読して最新HEAD/CI/ZIP復旧を確認。研究・開発工程79％(24/32)、研究卒業100％、独立実開催接続0/6、実用能力下限0/100を区別。既存の原本取得・PC/SP切替・P1三原本照合を繰り返さず、許諾済みの本当の発走前データ接続から実モデル/EV/仮想投資/公式結果へ接続。main/Turso/Secrets/旧アプリ/実購入に手を触れず、毎回固定基準の増減理由と成功run/job/SHA・バックアップを保存する。」
