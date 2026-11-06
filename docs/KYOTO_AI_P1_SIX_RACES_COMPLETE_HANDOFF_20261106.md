# 京都競馬AI｜P1大節目：京都1R〜6R全馬詳細プロフィール確認（2026-11-06）

## 現在の正本・再開位置
- Repo: `papaneko-ai/kyoto-keiba-ai`; branch: `jra-html-diagnostic-20261105`
- 最新: `docs/diagnostics/jra_p1_eleven_batches_20261106/status.json`、`feature_rows_148.json`
- **京都12R 148頭のうち78頭の詳細プロフィール検証済み、70頭詳細未取得**。京都1R 9/9、2R 15/15、3R 13/13、4R 15/15、5R 8/8、6R 11/11。
- 有効過去走211件（前回189 + batch11の22）。R6の新馬プロフィールは公式原本の履歴0として検証。未取得=0件と混同しない。
- **batch_01〜batch_11 完了。次はbatch_12**、固定バッチ計画に従う。成功済み公式URLへ再取得しない。
- 前回の72頭正本: `docs/diagnostics/jra_p1_ten_batches_20261106/`。今回の78頭正本: `docs/diagnostics/jra_p1_eleven_batches_20261106/`。互いに上書き禁止。
- `next_batch_automatically_authorized=false`。新チャット開始時または次回着手時にHEAD・CI・status・固定計画・未取得馬照合。

## 独立実証と実行条件
- CI: https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42170129115 `completed/success`
- capture, replay, acceptance 全3ジョブsuccess。
- batch11 対象: R6 馬番7〜11の5頭、R7 馬番2の1頭。6/6取得、失敗0。オフライン独立再解析6/6、追加公式GET0。
- 原本取得UTC: 2026-11-06T05:43:58Z〜05:44:14Z。公式HTML SHA-256、馬名・馬番・固定公式URLと原本長を取得レシートへ保存。
- 取得件数上限6、2秒間隔以上、リトライなし、2026-11-07T00:00:00Z以降取得禁止、URL・台帳・バッチSHA・既取得防止。締切時のゼロHTTP停止オフライン検査を事前実施。
- 原本HTMLはGitHub Actions Artifactに3日限定で保存。恒久原本保存と利用許諾の問題は未解決。
- 148頭の正規化台帳、status、batch11 source receipt と replay_receipt はGitHubに保存。
- `main`の確認時SHA `471b60e632d878b52b6dcb4aa1a622becba40882` で変更なし。本番 app.py、Turso、公開モデル、実馬券記録は未変更。

## 継続方針
- 必須アルゴリズム13項目とP1→P8の工程順序は維持、現在はP1。
- 未完了: 騎手/厩舎、調教、当日条件・馬場・天候、取消、発走前馬連枠連オッズ、安定馬ID、長期原本保全、利用条件検証、情報鮮度と時点確証。
- `prediction_ready=false`、`training_ready=false`、`feature_complete=false`。CI成功は予測性能や収益の証明ではない。
- 次回は第12バッチを対象に、最新の証拠と馬同定・NOT_QUERIEDを照合し、独立SHA再解析・期限内GET・台帳受入まで実施。**次の大節目は京都7Rの全馬確認**（第12・第13バッチの受入が必要）。締切や技術障害があれば状態を記録して停止し、未来原本を発走前データと偽らない。
- チャット移行は節目や大幅な肥大化時にこちらから提案。移行だけで工程を変更しない。
