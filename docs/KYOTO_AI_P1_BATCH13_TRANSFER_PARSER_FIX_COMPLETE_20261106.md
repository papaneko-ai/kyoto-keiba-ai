# 京都競馬AI｜P1 第13バッチ解析バグ修正・完全照合引継ぎ（2026-11-06）

## 現在の確定チェックポイント
- GitHub `papaneko-ai/kyoto-keiba-ai` 開発ブランチ `jra-html-diagnostic-20261105`。
- 正本：`docs/diagnostics/jra_p1_batch13_reconciled_90_profiles_20261106/status.json` と `feature_rows_148.json`。
- 対象京都2026-11-07、12R・148頭。**詳細90頭、未確認58頭、有効過去走414件**。
- 京都1R〜7Rは全頭詳細確認済み。京都8R馬番1〜4の4頭も個別詳細確認済み。
- 第13バッチ6頭の証拠が3経路で合致し、受入完了：R7馬番9〜11は失敗バッチの成功済み原本3件、R8馬番2は再診断時に取得した別時点の公式原本、R8馬番3・4は初回のsource-first取得原本2件。
- **次はバッチ14**。ただし`next_batch_automatically_authorized=false`、次回は必ず最新HEAD・status・既取得馬を事前確認。バッチ01〜13の成功済みURLを再取得してはならない。
- `main` SHA確認時 `471b60e632d878b52b6dcb4aa1a622becba40882`、本番・Turso・公開予測モデル・実購入記録は変更なし。

## 根本原因：レース一覧に含まれる所属変更行政イベント
- 第13バッチ公式HTML取得で京都8R馬番2「グラニットピーク」が`invalid_history_rows`。
- 原因切り分けは1回限りの新たな公式HTML取得。取得時刻2026-11-06T05:56:31.422342Z、SHA-256 `02673c9e62fa49e6d781abdd14c7ffe8e3993ebed3e479192f336c11f506bf5d`。
- 28行の過去走表のうち、17行目2024-03-13「JRAへ転入」、23行目2023-06-16「JRAより転出」は**レースではない**。距離、出走頭数、着順は空欄。従来`COURSE`の正規表現へ渡され誤ってinvalidに分類された。
- `diagnostics/jra_prior_form_offline.py`を修正。厳密に「JRAへ転入」「JRAより転出」かつ距離・頭数・着順が空欄の形だけ、`administrative_events`へ隔離し、`excluded_rows`に`administrative_transfer_not_a_race`を記録。曖昧な距離や不明ラベルは今までどおりinvalidで停止。未来日・失格・中止の判定は維持。
- 原本独立SHA照合を行った再解析で、**通常過去走26、行政イベント2、invalid0**。この原本は最初に失敗したGETの原本とは別物で、過去のHTTP取得時刻に偽装していない。
- 証拠：`docs/diagnostics/jra_p1_r8h02_diagnosis_20261106/receipt.json`、`course_cells.json`、`replayed_fixed_parser/replay_receipt.json`。
- 固定修正CI [42171578170](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42171578170)：6種の合成ケースを含む単体テスト、現物HTML原本SHA再解析、88頭時点受入の全ジョブ成功。

## 二つ目の根本原因：取得した原本を解析前に保存していなかった
- 旧`jra_p1_batch13_guarded.py`では`parse_horse_history`とinvalidチェックを通った後に原本HTMLをファイル保存していたため、バグに遭遇すると失敗元原本が残らない設計であった。
- 修正パターン`diagnostics/jra_p1_batch13_source_first_remaining_two.py`：HTTP 200・公式ホスト・容量・時刻検査後、**先に生HTMLバイト列を保存しSHA/取得UTCを確定**、その後で解析。失敗時も原本・行単位のinvalid理由・レシートを保存して停止。自動リトライなし、取得上限・2秒間隔・UTCハードカットオフを維持。
- `tests/test_jra_batch13_source_first.py`では合成HTMLを使い、解析に失敗しても原本が保存され、公式GETは1件のみで停止することを検証済み。
- 新方式でバッチ13の未試行R8馬番3「トーアモルペウス」24件、馬番4「メイショウアツイタ」35件を取得。公式GET各1回、失敗なし。原本を独立SHAで再解析した後、148頭台帳へ反映。
- 修正方式CI [42171828383](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42171828383)：capture/replay/acceptance全ジョブsuccess。90頭、過去走414件、未取得58頭を確定。
- **今後のバッチ14以降は必ず「原本保存→解析→失敗理由記録」順序の新方式を使用すること。旧バッチ13などの歴史的実装をコピーして旧手順へ戻してはならない。** 原本をGitHubリポジトリへ無制限に公開せず、保管先の利用許諾と恒久性を別途検討する。
- 元HTMLはActions 3日限定Artifact。SHA、UTC、正規化結果、バッチ証拠はGitHubに保存。恒久保存は未達。

## 次回の実行順序
1. 最新ブランチHEAD・batch13 reconciled `status.json`・既取得90頭・計画バッチ14を照合。
2. `jra_p1_batch13_source_first_remaining_two.py`と新規テストの原本先行保存方式を次回バッチへ転用（2件固定の仕様は6件用に明示的に直す）。合成の失敗試験、締切試験、重複検知、原本SHAオフライン独立再解析を必須にする。
3. 当日以前の原本と未来の確定情報を混ぜない。保存済みの原本は再取得せず、未取得の馬だけ進める。予測用完成を宣言しない。
4. ALG-01〜13およびP1→P8ロードマップ順序は変更しない。現在はP1。現段階は`training_ready=false`、`prediction_ready=false`。
5. SP版は出馬表の一致と取得性能で過去の検証例があるが、本件はPC版の行政イベント分類バグを直接再現・修正して解決したため、SP版への無検証自動切替は行っていない。
