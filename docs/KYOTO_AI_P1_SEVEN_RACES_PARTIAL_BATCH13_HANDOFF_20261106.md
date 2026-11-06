# 京都競馬AI｜P1京都1R〜7R全頭確認・batch13部分停止引継ぎ（2026-11-06）

## 最新状態（最優先）
- 対象2026-11-07京都12R、出馬表148頭。
- **詳細プロフィール87/148頭、未取得／未検証61頭、有効過去走329件。**
- **京都1R〜7R全頭詳細プロフィール確認済み**。京都7Rは11/11頭。バッチ01〜12を完全受入、第13バッチは部分成功・安全停止。
- 正本: `docs/diagnostics/jra_p1_seven_races_partial_20261106/status.json` および `feature_rows_148.json`。
- 以前の84頭正本: `docs/diagnostics/jra_p1_twelve_batches_20261106/`。既存の履歴は上書き禁止。
- **次は `batch_13_BLOCKED_AT_R8_HORSE2`。batch14へ飛ばしたり、成功済みURLを再取得してはならない。** `next_batch_automatically_authorized=false`。
- ALGs 01〜13とP1→P8工程は変更なし。現在P1、予測・学習の本番採用不可。

## CIの実証
1. 第12バッチ（京都7R馬番3〜8の6頭）：run [42170460994](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42170460994)、capture/replay/acceptanceすべてsuccess。84頭／過去走282件／未取得64頭の12バッチ台帳を保存。
2. 第13バッチ（京都7R馬番9〜11、京都8R馬番2〜4）：run [42170611153](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42170611153)、**capture failure、replay/acceptance skipped**。JRAへのGETは4回。京都7R馬番9〜11の3頭はSOURCE_PARSED、京都8R馬番2で`ValueError:invalid_history_rows`。馬番3・4へは未アクセス。そこでノーリトライで停止。
3. 第13バッチの既存Artifact原本3件だけを使う**新規HTTPゼロの独立SHA再解析と部分受入**：run [42170783741](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42170783741)、replay/acceptanceともsuccess。京都7R全11頭、総計87頭、過去走329件、詳細未確認61頭を保存。
4. 第13バッチ取得レシート：`docs/diagnostics/jra_p1_profile_batches_20261106/batch_13_receipt.json`（`state=BLOCKED`）。成功済み3原本の再解析：`docs/diagnostics/jra_p1_profile_batches_20261106/replayed_batch_13_partial/`。第13バッチ全体の成功レシートではない。
5. 元HTMLはGitHub Actions Artifact **3日間だけ**。長期保存・再利用許諾・再取得不要の技術的保証は未完了。特に京都8R馬番2のHTMLは取得時に解析エラーが生じたため、既存プログラムがHTMLファイル保存に到達せず、該当バイト原本の保存は確認できていない。SHA照合可能な3頭以外を検証済みにしていない。

## 停止の理由と影響
- 現象：京都8R馬番2`グラニットピーク`、過去走の行に現在の解析器が未解決とする形式があり`invalid_history_rows`。具体的な行の内容は取得レシートに残っておらず、原本保存も未確認のため**内容・原因の詳細は未特定**。
- 正しい処置：取得済み3頭を原本SHA独立再解析で採用。解析失敗の馬および未試行の残り2頭は`NOT_QUERIED`のまま。第13バッチを完了扱いせず、追加のオンライン取得を停止。時間制限切れや未来原本の遡及利用を禁じる。
- 再開条件：第13バッチの原本保存状況を確認し、失敗行の原因をオフラインで解明して解析器・安全なレシート設計を修正。**同じ公式URLへのGETは追加の明示的な原因判定・重複回避判断なしに行わない**。次にバッチ再開計画を証拠ベースで更新し、オフライン回帰テスト、原本SHA照合、時点保証を通す。変更が必要なら原則P1の停止理由として報告する。
- `main/app.py`、本番Turso・モデル・実馬券記録は変更していない。確認時main SHA `471b60e632d878b52b6dcb4aa1a622becba40882`。

## 守るべき今後の原則
- 第14バッチへ無条件で進まず、まず第13バッチの異常を一次原因から調べる。
- 異常を忘れてチャット移行・再設計・成功済みHTTP再送をしてはならない。
- 今回の到達点は**京都7Rの全馬確認の節目**。P1の完全性・予測性能・期待値・自己学習完成を意味しない。
- 次の具体的工程は、オフライン原本・パーサー・レシートの失敗原因分析と安全な再開策の確立。運用上の再取得許可を勝手に与えない。
