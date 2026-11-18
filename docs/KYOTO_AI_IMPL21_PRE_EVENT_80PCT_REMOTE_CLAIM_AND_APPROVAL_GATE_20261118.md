# 京都競馬AI開発・実装21｜2026年11月18日 事前準備80%・実環境移行直前の検証記録

## 数値を勝手に増やさない固定進捗
| 指標 | 前回 | 今回 | 増減 |
|---|---:|---:|---:|
| 既存12工程 | 6/12 | 6/12 | ±0 |
| 予備実験9工程 | 6/9 | 6/9 | ±0 |
| 新ハイブリッド復元6工程 | 4/6 | 4/6 | ±0 |
| 実開催独立検証 | 0/6 | 0/6 | ±0 |
| 実用能力独立検証下限 | 0/100 | 0/100 | ±0 |
| **11/21-22 事前準備完成率** | **8/10=80%** | **8/10=80%** | **±0** |

## 今回実際に行った技術作業
1. `diagnostics/kyoto_turso_capture_claims.py` : 実際のTurso HTTP v2プロトコル向け単一SQL UPSERT/RETURNINGによる取得権の原子的確保、世代付きフェンシング、失敗時即時解放、次スロットの独立確保。現在の共有台帳は2つの厳格分離テーブル（`OPERATIONAL` と `ISOLATED_LAB`）。
2. `diagnostics/kyoto_g06_all12_capture.py`: G06 12Rの実際の取得入口へ「共有claim→取得→証拠SHAのcommit／失敗ならabandon」を接続。過去の取得結果だけで別のスロットや市場を止めない。未設定なら従来の取得器をそのまま使用。
3. `diagnostics/kyoto_weekend_remote_claim_runtime.py`: 11/21・22の8回の正規cron文字列とスロット0..3を厳格対応。実験用Tursoの固定ホスト以外は拒否。オプトインで有効化した場合のみ稼働し、デフォルトでは追加制限なし。
4. 本番固定SHAから派生した `release-candidate/nov21-22-g06-full12-20261118` にコードを反映し、94件の既存本番＋81件のG06・リモート調停＋168件の原本・暗号化 = **343/343 CI PASS**。候補SHA `a96a249250cb074c451e746228a6775169c025ed`。
5. 本番mainとのレビュー差分は固定SHAの**6箇所のみ**。8回予約、PC/SP、AES-GCM、Secrets参照、concurrency等は無変更。復帰時に元の本番YAMLへバイト完全一致。ドラフトPR #3の更新済みレビュー `44252232432` SUCCESS。
6. 隔離TursoテストDBの操作は本番DBと異なる別表 `__kyoto_ai_weekend_claims_isolated_lab_v1` を使う。独立2 GitHubランナーを争わせる**明示承認後だけの**実HTTP試験 `.github/workflows/kyoto-weekend-turso-manual-two-runner-proof.yml` を作成、実行はしていない。default branch外ではworkflow_dispatchメニューの制約があるため、実験ブランチの承認ファイル1件のみをトリガーにするpush方式も実装。ユーザー承認前の承認ファイル作成は禁止。
7. `kyoto-weekend-turso-readonly-preflight.yml` によりGitHub Actionsから**実際の隔離テストDBへREAD ONLY接続**できるか確認。Run **44253060020** SUCCESSだが、受領証は `SKIPPED_TEST_DB_SECRETS_NOT_CONFIGURED`。**実Turso接続成功ではない**。GitHub Secretsの`TURSO_DATABASE_URL`、`TURSO_AUTH_TOKEN`が現環境で供給されていない。ユーザーの秘密値は閲覧・変更していない。

## 今回の固定10項目判定
1. **PARTIAL** — 本番固定SHA、予約、Secrets参照、改修候補、完全復帰は合格。**mainへの実反映は未実施**。
2. PASS — PC修復／SP独立リンク探索の既存事前検証。
3. PASS — 本番固定取得器から派生した全12R馬連・枠連取得／市場単位の補完／暗号化／受渡しに関する開催前E2E。
4. PASS — 障害・異常・通信停止。
5. PASS — AES-GCM原本暗号化／別ジョブ復旧。
6. PASS — 21日の失敗・部分成功を22日まで持ち越す際の新枠継続。
7. **PARTIAL** — G06本番派生入口にTurso SQL予約が接続され模擬HTTPで認証/原子競合/所有者フェンスを確認。**GitHub ActionsとStreamlit等異なる実ホストから同じ実Tursoへ接続した競合試験は未実施**。Credentials未供給。勝手にPASSに変更しない。
8. PASS — GitHub独立CI。
9. PASS — 本番切替候補と完全ロールバックの事前検証（main未マージ）。
10. PASS — G07/P4/P5/P6の入力受渡し。

## GitHub根拠
- Release candidate full regression: https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/44252070334 （343件全件PASS、artifact 14404043005）
- Main exact diff and rollback: https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/44252232432 （PASS、artifact 14403359395）
- Manual cross-runner test offline rehearsal: https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/44252855565 （13件PASS、artifact 14403664346）
- Actual isolated test Turso read-only preflight: https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/44253060020 （SKIPPED TEST DB SECRETS MISSING、artifact 14404657587）
- Production review PR #3 (DRAFT, unmerged): https://github.com/papaneko-ai/kyoto-keiba-ai/pull/3
- Production HEAD on last read `669124c020e627bcba186228b20fb1721cc688e1`. The 11/21–22 scheduled run is **still pinned to the original collector** `c96df31542cb94435ca36cb4a1b8bd6de938233f` (unless pre-existing Nov22 variable overrides).

## 90% / 100%に必要な最終作業
A. ①の実反映には、ユーザーによる本番PR #3 mainマージの明示承認が必要。その後8 cron固定SHA実設定・保護面と安全回帰を再検証する。
B. ⑦の実証には、隔離テストDB用の2 GitHub Actions Secretsが必要で、隔離ラボ表に合成請求・予約のみを書く試験をユーザーが明示承認すること。承認後、こちらが実験ブランチに承認トリガーファイルをコミットして4ジョブの本物の別ランナー競合試験を実施できる。**Turso本番・Secretsを書換えない**。
C. 実際の公式開催データが公開されたかどうかは11/21・22の取得時点で別評価。今は本番接続のための事前準備の完成率を測っている。不要な起動回数制限を追加しない。

## 復旧
GitHub実験HEAD、release candidate SHA、review PR #3、main SHA、上記Run 4件と各Artifactを引継ぎ時に再読する。復旧用ZIPは最新の5ブランチGit bundleが入る方式へ変更済み。Turso本番データ・GitHub Secretsはバックアップに含めない。
