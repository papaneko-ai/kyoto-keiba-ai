# 京都競馬AI｜P1節目：京都1R〜5R全馬プロフィール証拠確認（2026-11-06）

## 最優先の再開位置
- 開発ブランチ `jra-html-diagnostic-20261105`、P1を継続。
- **batch_01〜batch_10 完了、次は batch_11**。公式GETの成功済み馬を再取得しない。
- 正規化最新状態：`docs/diagnostics/jra_p1_ten_batches_20261106/status.json`。
- 同148頭台帳：`docs/diagnostics/jra_p1_ten_batches_20261106/feature_rows_148.json`。
- 過去66頭時点の証拠：`docs/diagnostics/jra_p1_nine_batches_20261106/`（保存先修正により復元済み）。
- 固定取得順：`docs/diagnostics/JRA_PENDING_136_PROFILES_PLAN_20261106.json`。次バッチは実行前に最新HEAD・CI・台帳と照合すること。
- 第11バッチを自動承認しない。UTC締切以降の取得を開催前原本と扱わない。

## 確認済み到達点
- 対象2026-11-07京都：12R・148頭。
- プロフィール詳細 **72頭**、詳細未取得 **76頭**。
- 京都1R 9/9、2R 15/15、3R 13/13、4R 15/15、**5R 8/8**の全馬公式詳細を検証済み。
- 過去走有効着順 **189件**。batch09とbatch10に今回新たな有効過去走はなく、新馬の履歴0と未取得を混同しない。
- 追加batch09：京都5R馬番2〜7、6頭取得成功・失敗0。独立原本SHA再解析6頭成功。
- 追加batch10：京都5R馬番8、京都6R馬番2〜6、6頭取得成功・失敗0。独立原本SHA再解析6頭成功。
- 元HTMLの原本はGitHub Actionsの**3日限定Artifact**。恒久保存は未達。GitHubには原本SHA、UTC、正規化履歴、検証レシートを保存。
- 未来情報を予測へ混ぜない。prediction_ready=false、training_ready=false、本番運用不可。

## 今回のGitHub Actions
- batch09 取得→独立再解析→148頭台帳反映：run **42169512445**、completed/success。
- batch10 取得→独立再解析→148頭台帳反映：run **42169692197**、completed/success。
- 各バッチ6件上限・2秒以上間隔・リトライなし・事前時点のUTCハードカットオフ・対象馬IDと計画SHA照合。
- 第10バッチのCI初版は保存先名を `jra_p1_nine_batches_20261106` としていた。**検出後、72頭の最新成果をten_batchesに分離保存し、nine_batchesの66頭原本チェックポイントを履歴コミットから復元、CI定義も修正**。双方status/148頭台帳を再読込で検証済み。取得HTTPや成功済みCIは再実行していない。
- 本番main SHA：`471b60e632d878b52b6dcb4aa1a622becba40882`（当節目の照合時に変更なし）。Turso・本番モデル・実購入履歴には一切書込んでいない。

## 合意の保護と未完了
- `docs/KYOTO_AI_ALGORITHM_REQUIREMENTS_REGISTER_v1_20261106.md`のALG-01〜13維持。
- `docs/KYOTO_AI_ALGORITHM_AND_EXECUTION_ROADMAP_20261106.md`のP1→P8順序維持。現在はP1。
- 騎手、厩舎、調教、馬場、当日条件、取消、発走前オッズ、馬ID安定化、合法的かつ恒久的な原本保全は引き続き未検証。P2〜P8の採用/性能を宣言しない。
- 次に一度だけ最新ブランチHEADと `status.json`・CI・batch11対象公式URLを突合し、全頭NOT_QUERIEDなら上限6件、締切、原本SHA、UTC、独立オフライン再解析を守り継続。
- チャット移行は現時点では不要。次の大きな節目、またはチャットの肥大化・技術的停止を認めた時にこちらから案内する。
