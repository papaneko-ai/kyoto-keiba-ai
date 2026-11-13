# 京都競馬AI・次チャット完全再開指示／PC-SPハイブリッド・リンク障害対策

更新日：2026-11-13（JST）。本書は過去の正式移行資料を置換せず、今回のチャットで追加確認した最新版を補足する。**新チャットで先にGitHub最新HEADを再取得し、以下のSHAを「作成時点の値」として扱う。**

## 1. 開発識別／固定制約
- Repository: `papaneko-ai/kyoto-keiba-ai`。
- 開発ブランチ `jra-html-diagnostic-20261105`、本書作成直前HEAD `790a067b7e640869ffd970afeddb098a7b5c0af1`。
- 本番保護ブランチ `main`、本書作成時HEAD `87b1f97709d2c6e3b73d6afbd6e43b81842746d9`。
- **修正するたびに開発ブランチへGitHubコミットし、内容・SHAを検証する。本番`main`・Turso・Secrets・Streamlitは事前承認が必要。承認要求は押せるボタンを出す。**
- P1→P8、ALG-01～13、EVO-01～08、R04、CORE-20、過去研究成果・履歴を維持する。資料の新規作成やユニットテストだけで実稼働能力を加点しない。
- 根拠のないSP URL推測生成、既使用HTTPワンショットの無断再取得、取得時点の偽装、最終オッズの発走前転用は禁止。
- 取得準備・研究の歴史的指標を、実開催検証値に読み替えない。実開催接続0/6、実用能力独立検証下限0/100は新しい実証のない限り維持。

## 2. 最優先で読む正本
1. `KYOTO_AI_START_HERE.md`
2. `docs/KYOTO_AI_IMPLEMENTATION15_20261113_END_OF_DAY_CRITICAL_HANDOFF.md`：取得P0不備と2026-11-16再開時の強制手順
3. `docs/KYOTO_AI_PERMANENT_RESEARCH_REUSE_AND_SECTION_HANDOFF_POLICY.md`：重複実装禁止・恒久移行規程
4. `docs/KYOTO_AI_P1_PC_SP_BIDIRECTIONAL_FAILOVER_REQUIREMENTS_20261106.md`：P1-DUAL-01～08
5. `docs/diagnostics/kyoto_feature_reuse_inventory_v1.json`：25機能の既存研究・達成度。関連ソース／テスト／原本を実読
6. `docs/diagnostics/nov14_existing_attempt_safe_stop_20261113.md` と `diagnostics/kyoto_nov14_attempt_guard.py`：既存HTTP試行の防護
7. `docs/KYOTO_AI_ALGORITHM_REQUIREMENTS_REGISTER_v1_20261106.md` と `docs/KYOTO_AI_ALGORITHM_AND_EXECUTION_ROADMAP_20261106.md`

## 3. 既に実装した障害対策を再利用する（「忘れて再設計」しない）
- `diagnostics/jra_official_link_repair.py`：`observed_links`、`unique_observed`、`repair_pc_racecard`。PCリンクが404/410等で壊れた場合、JRA公式「開催選択原本→開催ページ原本」に実際に掲載されたリンクのみを再発見し、候補出馬表と同一レースの真正な出走馬照合が合格するまで採用しない。最大3 GETの既存制約・原本保存あり。万能のHTTP再試行ではない。
- `diagnostics/jra_one_shot_market_capture.py`：`capture_hybrid`、`capture`、`ObservedRaceSpec`、`RequestPacer`、`NoRedirect`。PC/SP両URLが独立観測され、発売・発走時刻・同一レース・安全ゲートが成立したときのみ別系統を最大1回試す。許可・締切・正式な内容矛盾なら再試行せず停止。`independent_crosscheck=True`は主系成功時にももう一方を独立検証するモードだが、現行無人起動には未結合。
- `diagnostics/jra_source_router.py`：PC/SPの証拠・性能評価と安全な切替判断。片系の障害をもう片系の成功で「解消済み」としない。
- `diagnostics/jra_pc_sp_benchmark.py`：保存済みPC/SP原本の`pc_rows`・`sp_rows`、`reconcile_saved_racecards`、今回追加の`assess_dual_channel_experiment`と`observed_sp_race_links_from_saved_navigation`。両チャネル原本・SHA・取得時刻・元ページ上の実在リンク・馬番/枠番/馬名を照合。SP URLはPCのCNAMEから生成しない。
- `diagnostics/kyoto_p1_github_attempt_history_gate.py`：過去Actions履歴から実行済みGETを検知して重複禁止。実行履歴不明なら安全停止。
- `diagnostics/kyoto_nov15_encrypted_evidence.py`：AES-256-GCM暗号化原本・レシート保存。
- `diagnostics/kyoto_nov14_nov15_second_day_handoff.py`：11/14の失敗を後日診断・11/15を独立して扱う既存ハンドオフ。

## 4. 11月14日・15日の事実と未完成（混同禁止）
- 11/14旧Run `43142384975` は**2026-11-12にGET試行1回**、`FAILED_CLOSED`、有効原本取得は未証明。旧ワンショット再GET・再実行は禁じる。安全に残る原本・レシートのオフライン再解析と根本原因調査を行う。
- 11/15 `main` の `.github/workflows/kyoto-nov15-unattended-observer-launcher.yml` は11/15 11:00 JSTに起動予定、**PC公式ページ中心・最大3 GET・2秒以上の間隔・履歴ゲート・暗号化保存**。SP無人ライブ取得と馬連・枠連両市場取得は**未接続**。起動成功・実データ取得成功・両系統合格は、Actions Run/Job/Artifactの確認前に主張禁止。
- 開発版でPC-onlyを`INCOMPLETE_PC_ONLY_SP_MISSING`と記録する。厳格なPC/SP比較テストは合成・オフライン検証であり、本番JRA取得の実績ではない。
- 11/07のPC/SP出馬表リンク・プロフィール等の保存済み歴史研究成果、96/148プロフィール、84原本再解析、過去走592件、5R実測ベンチマークを再利用する。11/07のURLを11/15に流用することは禁止。

## 5. 新チャットの即時作業順序
1. **開発とmain最新HEADをGitHubコネクタで読み直し**、最後の更新ファイルの内容SHA・最新の同HEAD CI、現存するActions Artifactを調査する。READMEや古い移行資料の固定SHAを現行HEADとみなさない。
2. 11/14と11/15のActions Run/Job/Stepを確認。特に11/15のscheduleが実際に起動したか、HTTPに達したか、保存された原本と暗号化ArtifactのSHA/UTCが整合するか確認。未実行・HTTP前停止・HTTP失敗・真正原本・市場まで成功の5区分で報告する。
3. **既存のPC/SP公式リンク観測・修復・双方向切替機能がどこまで実装済みか再読**し、11/15のSP独立発見・両系統取得の「未配線箇所」だけを最小修正。PC/SPとも公式の実在リンクを原本から確認できなければ推測取得をしない。
4. リンク切れ時の分岐：既存のJRA公式原本から再発見可能な場合は候補を厳格検証。認証済みの別チャネルURLがある場合だけ既存`capture_hybrid`の限定フォールバックを使う。両系統不明・取得期限超過・真正性不明・URL矛盾なら二重HTTPせず失敗レシートを保存する。PC/SP比較実験そのものの合格には両系統の実原本と同一レース照合が必須。
5. 出馬表・馬連・枠連オッズの発走前原本を正確に結び付け、取得できない場合は原因・該当系統・SHA/UTCの有無・次回の改修を保存する。R04市場連動モデル・CORE-20はこの証拠固定後。
6. **変更1件ごとにコミット→SHA確認→対象の回帰テスト→必要なCI確認**。受入根拠のない成功宣言はしない。mainは必ず押せる承認ボタンを示し、承認前変更しない。

## 6. コピーして新しいチャットへ送る開始指示
「京都競馬AI開発の継続です。GitHub `papaneko-ai/kyoto-keiba-ai` の開発ブランチ `jra-html-diagnostic-20261105` を開き、まず `KYOTO_AI_START_HERE.md` と `docs/KYOTO_AI_NEXT_CHAT_GITHUB_HANDOFF_20261113_PC_SP_HYBRID.md` を全文読み、記載された追加正本も確認してください。**過去に実装したPC/SPリンク障害修復、条件付き双方向フォールバック、原本暗号化と重複GET防止を流用し、最初から作り直さない**。11/14の既使用GETを再実行せず、11/15の実行とPC/SP両系統の独立取得・馬連/枠連・UTC/SHAを検証してください。変更ごとに開発ブランチへGitHub保存。main/Turso/Secretsは承認ボタンによる事前承認制。進捗は実証のみで加点。停止前には移行を警告してください。」
