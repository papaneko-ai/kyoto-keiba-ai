# 京都競馬AI・RG-05B研究卒業91.7％節目／完全継続復旧パック（2026-11-10）

## 0. 再開時にまず確認する正本
`KYOTO_AI_START_HERE.md`、本書、`docs/KYOTO_AI_20261110_COMPLETE_MIGRATION_PACK_61PCT.md`、`docs/diagnostics/kyoto_progress_rubric_v1.json`、`docs/diagnostics/kyoto_research_graduation_rubric_v1.json`、`docs/diagnostics/kyoto_research_graduation_integration_claims_v1.json`、最新HEAD・成功GitHub Actions・P1原本Artifact `13482994623` の順で確認。

## 1. 実測得点（基準変更なし）
- 研究・開発工程認定率：**64／100**（固定32条件中21合格）。前回64％→64％（±0）。
- 研究段階卒業基準達成率：**91.7％**（固定12条件中11合格）。前回83.3％→91.7％（+8.4ポイント）。研究個別6/6、研究統合5/6。残り **RG-06Bのみ**。
- 独立検証済み実競馬接続 **0／6分野**、独立検証済み実用能力の下限 **0／100**。研究成果と実開催成果は独立して扱う。
- 次回も、前回値・現在値・合格項目数・得点増減と理由を同じ固定基準で示す。

## 2. 今回の実装 RG-05B
- `diagnostics/rg05_original_market_safe_pipeline_lab.py` を追加。既存の`diagnostics/p1_operator_original_handoff.py`→`diagnostics/p1_three_original_dual_intake.py`でPC/SP出馬表・馬連・枠連保存済み原本のバイト照合とパーサー照合。
- その結果、取消馬・停止市場・価格改変・原本改変・名簿不一致・期限不正を研究用仮想投資の**書込み前**に拒否する。
- P3馬連・枠連確率とP4市場下方リスク評価を両券種について実行し、両方に問題がなければ既存 `diagnostics/rg01_prediction_freeze_settlement_lab.py` の発走前研究用凍結に渡す。
- 結果追記時は外部保存済みジャーナルヘッドと元の凍結記録を照合し、初回研究用精算のみ実行。既存ファイルへの二重精算・上書き禁止。
- `tests/test_rg05_original_market_safe_pipeline_lab.py` に、正常動作と欠損・改変・取消・未来市場・重複書込みを拒否する17件のテストを追加。
- これらは**LAB限定**で、HTML原本のバイト整合と自己申告の状態を確認してもJRA真正性、外部時刻証明、正式な発売状態・取消、法令/規約に沿う取得許可、実モデルの較正を証明するものではない。実購入なし。

## 3. GitHub Actions認定証拠
- 統合17件と全体CI成功：run **42762265925** / job **129650502031** / SHA `343c66fb8dc5cb7d7a5f0e6220cad6c5616f4005`。
- RG-05B証拠を `docs/diagnostics/kyoto_research_graduation_integration_claims_v1.json` に記録。採点器はGitHub API照会によるrun/job/SHA、一致する過去workflow内テスト指定、現HEADの同じテストの再実行を必須とする。
- 固定基準再採点 success：run **42762389354** / job **129650913067** / SHA `00baf76984935fbf34ad81d285246ced5527239d`。
- ログ：`KYOTO_PROGRESS_VERIFIED=64%` / `KYOTO_RESEARCH_GRADUATION=91.7%` / `KYOTO_RESEARCH_GRADUATION_CONDITIONS=11/12` / `KYOTO_RESEARCH_GRADUATION_INTEGRATED=5/6` / `KYOTO_RESEARCH_TO_LIVE_VERIFIED=0/6` / `KYOTO_OPERATIONAL_VERIFIED=0/100`。
- 不要な再開発禁止。既存REG-01B〜04Bの全証拠を保持。

## 4. 過去の引継ぎ穴と復旧
- 前回83.3％：run `42761944598` / job `129649449063` / SHA `4c7a74a92e2c15bd2c33462518c6ac14fa4de13a` でsuccessを確認済み。
- 83.3％節目の個別文書は作成途中で中断した可能性があるため、本91.7％パックが前回からの経緯・実装・証拠を明示的に引き継ぐ。旧来の未完成ファイルを無条件に完成と呼ばない。
- 前回までの復旧ブランチ `backup/kyoto-ai-research-graduation-66p7-20261110` とP1原本アーティファクトは変更しない。
- 本書追加をトリガーに`.github/workflows/kyoto-ai-milestone-recovery-archive.yml`でHEADソースZIP・`SHA256SUMS.txt`・`RECOVERY_MANIFEST.txt`をアップロードし、同一HEADの継続CI successも確認する。未確認のArtifact ID/runを捏造しない。

## 5. 次の節目と実競馬への接続
- 研究卒業基準の残り **RG-06B：同じ原本・同じ入力・同じモデル条件でのE2E再現性と、既存スマホ画面の操作が一貫して機能することを統合検証**。
- 研究卒業100％達成と、実競馬予測の独立実証は別。研究機能を再設計し直さず、既存P1に許諾済み真正JRA実開催原本、発走前オッズ・取消・発売・時刻証明を接続し、P3〜P6の既存経路で予測・仮想投資・結果照合する。
- ALG-01〜13、EVO-01〜08、P1〜P8、自動進化、悪化時復帰、時系列検証、馬連・枠連、仮想投資・実購入分離、スマホ優先、追加費用0円方針を維持。
- main、Turso、Secrets、旧公開app.py、公開モデル、実購入機能を無断変更しない。

## 6. 新しい会話への完全指示
「既存`papaneko-ai/kyoto-keiba-ai`・開発ブランチ`jra-html-diagnostic-20261105`を継続。ルート`KYOTO_AI_START_HERE.md`と本91.7％節目パック、固定2種類の採点基準、保存P1原本・最新HEAD/Actions/バックアップを照合し、繰り返しやゼロからの設計禁止。研究開発64％、研究卒業91.7％（11/12、統合5/6）、実競馬接続0/6、実用能力下限0/100を明示的に区別。RG-06Bを統合・CI認定し、研究と実競馬接続の一体開発を継続する。main/Turso/Secrets/旧アプリ/実購入機能を無断変更せず、節目ごとに同一SHAの成功run/jobと復旧ZIPを保全。」
