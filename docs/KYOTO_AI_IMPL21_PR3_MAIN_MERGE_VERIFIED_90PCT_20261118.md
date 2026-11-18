# 京都競馬AI 実装21：PR #3 本番反映・独立検証・復旧チェックポイント（2026-11-18）

## 実際に行った本番更新
- 明示ユーザー承認によりPR #3 https://github.com/papaneko-ai/kyoto-keiba-ai/pull/3 をmainへマージ。
- マージコミット: `e2ff146b93b16ee9b1c06d6f5318226993701268`
- 本番CI旧固定SHAの履歴テストを更新した現在main HEAD: `8b55870e826cec0cd0f07efc800394717d08fb55`（チェックポイント作成時に再照合）。
- マージした元からの差分: ワークフロー `.github/workflows/kyoto-20261121-22-two-source-production-observer.yml` の固定取得器SHA6か所を `c96df31542cb94435ca36cb4a1b8bd6de938233f` → `a96a249250cb074c451e746228a6775169c025ed` に置換。8 cron/PC/SP job/Secrets参照/Turso変数/暗号化/concurrencyは不変。main SHAの再照合とワークフローファイルのバイト単位比較で確認。
- 追加のテスト保守コミット `8b55870e826cec0cd0f07efc800394717d08fb55` は `tests/test_kyoto_weekend_main_release_guard.py` の固定SHA検証を新SHAへ更新。旧SHAは歴史的承認レジスタに残し、真正性を改変しない。

## 独立検証
- マージ時のmain CI `44253940318` はFAIL。唯一の根本原因は旧固定SHAを要求する `test_both_dated_jobs_use_fixed_sha_and_fault_injection` の不整合。取得器の本番回帰および設定危険チェックはSUCCESS。
- テストを局所更新して再実行したmain CI: https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/44254215980 **SUCCESS**、4/4 jobs: settings hazard; fixed collector fault rehearsal; main source-only release contract; five-condition pre-experiment acceptance。
- 正味のmain取得ワークフローの8 cron: 11/21 `15 0`, `15 1`, `5 2`, `50 2`; 11/22 `15 0`, `15 1`, `10 2`, `55 2` (UTC)。既存の日本時間9:15、10:15、11:05/11:10、11:50/11:55に対応。
- 取得器候補そのものの独立CI: https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/44252070334 **343/343 PASS**。
- アクセス拒否の回避、発走後価格の転用、架空原本の生成を禁止。実開催での取得証拠未確認は変更なし。

## 進捗（固定分母）
| 指標 | 前回 | 今回 | 増減 |
|---|---:|---:|---:|
| 既存12工程 | 6/12 | 6/12 | ±0 |
| 予備実験9工程 | 6/9 | 6/9 | ±0 |
| ハイブリッド復元6工程 | 4/6 | 4/6 | ±0 |
| 実開催独立検証 | 0/6 | 0/6 | ±0 |
| 実用能力独立検証下限 | 0/100 | 0/100 | ±0 |
| **11/21–22事前準備完成率** | **8/10=80％** | **9/10=90％** | **＋1項目＝＋10ポイント** |

①「本番固定SHA・予約・設定照合」: **PASS**（本番反映・main独立4/4検証まで完了）。②③④⑤⑥⑧⑨⑩: 従来PASS維持。
⑦「異ホスト間共有予約」: **PARTIAL**。SQLite2プロセスとローカルHTTP跨ぎはPASS、Turso v2模擬7件PASS、G06 runtime opt-in接続も試験済。ただし実際の別ホストTurso競合試験は未実証。隔離テストDB Secretsが見つからなかったため、試験 `44253060020` は `SKIPPED_TEST_DB_SECRETS_NOT_CONFIGURED`。ユーザーの明示承認なくTurso操作/Secrets変更しない。

## 保存と復旧
- 本報告が実験ブランチへ記録されたら、GitHub Actionsの5ブランチ完全ソースアーカイブを実行し、そこに**反映後main HEADおよびテスト修正コミット**が含まれること、git bundle verify、SHA256とArtifact保存を再確認する。
- 保存対象: main / jra-html-diagnostic-20261105 / experiment/multisource-hybrid-20261117 / release-candidate/nov21-22-g06-full12-20261118 / release-review/nov21-22-full12-g06-20261118。
- GitHub SecretsおよびTurso本番DBは含まない。復旧時に資格情報を捏造・再作成しない。
