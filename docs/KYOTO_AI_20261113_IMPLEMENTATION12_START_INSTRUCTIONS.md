# 【京都競馬AI開発・実装12】完全移行・初回実行指示（2026-11-13）

以下を新しいチャットの**最初のメッセージとして全文コピー**する。**先に本指示を読ませるだけで実装しないまま終了しない。** 正式文書とGitHub証拠を照合したら、ユーザーの次の「節目まで進める」に従い、実際のコード変更と検証を開始する。

---

**【京都競馬AI開発・実装12／完全移行指示】**

あなたは同じ京都競馬AI開発を、過去の同意・証拠・実装を保持したまま継続する。新規プロジェクトの設計し直しや、既に成功した工程の無意味な再実行、記録だけ作ってプログラムを進めない行為は禁止。

**1. リポジトリと移行正本を必ず実読**：GitHub `papaneko-ai/kyoto-keiba-ai`、開発ブランチ `jra-html-diagnostic-20261105`（保護対象は `main`）。GitHubの実際の最新HEAD、Run/Jobの成功/失敗と関係するコミットを取得。最優先で `docs/KYOTO_AI_20261113_IMPLEMENTATION12_COMPLETE_MIGRATION_PACK.md` を全文読み、`docs/diagnostics/kyoto_20261113_generated_evo_candidate_16tests_checkpoint.json`、`docs/diagnostics/kyoto_20261113_evo02_evo08_shadow_disjoint_holdout_16tests_checkpoint.json`、`docs/diagnostics/kyoto_20261113_hybrid_shadow_evolution_18tests_checkpoint.json`、`docs/diagnostics/kyoto_20261113_nov14_nov15_deep_gap_repair_130tests_checkpoint.json` を照合。文書の古いHEADを最新と誤認しない。最新パック直前の基準HEADは `a777aa93eaa8a6a6f6d052978fb3997b076ef8ea`、CI [Run 43354983177](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43354983177) SUCCESS。以後に作られた移行文書・バックアップコミットも確認する。

**2. 合意要件を省略・再定義しない**：P1→P8の既定工程、ALG-01～13、EVO-01～08、`docs/KYOTO_AI_ALGORITHM_AND_EXECUTION_ROADMAP_20261106.md`、`docs/KYOTO_AI_ALGORITHM_REQUIREMENTS_REGISTER_v1_20261106.md`、`docs/KYOTO_AI_HYBRID_SELF_EVOLUTION_MODEL_ARCHITECTURE_20261112.md`、`docs/KYOTO_AI_20261111_LIVE_PAPER_TRADING_MVP_EXECUTION_CONTRACT.md`、データ取得・管理/実購入と仮想投資の分離/自己進化/独立監査/全見送り/リスク資金配分/初心者用スマホ新UIを守る。馬連と枠連を対象とし、原則2～3R（最大4）、各レース2点（最大3）、1日予算は使い切らない上限、100円単位、手動調整、実データ不足時は見送り。既存公開`app.py`の設計を流用しない。

**3. 進捗の固定表示と根拠**：正式20ゲート正本 `docs/diagnostics/kyoto_final_completion_criteria_v1.json` と `docs/diagnostics/kyoto_final_20_gate_verified_state_20261112.json` を実読。研究32/32=100％、研究卒業12/12=100％、主要21機能群21/21=100％、実開催接続0/6、実用能力0/100、最終20ゲート35/100（F07,F10,F11,F12,F16,F17,F18のみ各5点）。毎回**前回・今回・増減**と研究100％バー・最終35％バーを同じ順で示す。研究LABテストの成功で正式20ゲートを勝手に加点しない。認定が減ったなら必ず証拠と原因を説明。

**4. 11月13日までの研究用節目を再開起点とする**：
- P3/P7登録台帳 `diagnostics/p7_hybrid_model_registry.py`、共通馬連/枠連確率契約 `diagnostics/p3_hybrid_prediction_contract.py`。
- 同一LABレースの予測結果前凍結→結果後評価・不正な重複拒否 `diagnostics/p7_hybrid_shadow_evolution_cycle.py`、18/18 CI [43352810566](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43352810566)。
- EVO-02弱点/EVO-08意外性分析から未使用LABホールドアウトでの二方向研究監査 `diagnostics/p7_evo02_evo08_shadow_bridge.py`、16/16 CI [43353928861](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43353928861)。
- **最新節目**：制約付きで同枠/異枠の確率を補正する12候補から、学習用レースで実際に新しいMODIFYモデルを生成し、研究用台帳登録→未使用レース予測→Brier・対数損失独立評価 `diagnostics/p7_evo_bounded_candidate_constructor.py`、16/16 CI [43354731435](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43354731435)。今回の研究コードを上書き/再実装せず**ADD/ENSEMBLEの制約付き生成**を次段階として実装する。
- ADD/ENSEMBLE生成、独立した真正JRAモデル精度、実P6仮想損益に基づく自己進化、本番の自動昇格/ロールバックは未実証。EVO-07監査の研究PASSを本番採用許可と取り違えない。

**5. P1/P6の実用MVPを研究より後回しにしない**：
11/06に翌11/07京都の事前出馬表12R/148頭、過去走日時を取得した既存実績を守る（証拠Run 43139684683）。10/31京都12R/154頭結果、11/07の96/148プロフィール・52件残・592過去走、10/25/11/08の公式確定結果・払戻は保全済み。**発走前の本物の馬連・枠連オッズと時刻をそろえた全過程、実開催の発走前仮想投資凍結→結果確定/払戻の自動照合は未認定**。事後結果や最終オッズを事前時点として後付けするのは禁止。今後の開催で出走馬・オッズ・特性・時刻を真正な公式原本として取り込み、既存P3/P4/P5→P6→P8の実用版へ接続する。研究用F17/F18の通過は実開催の収益を示さない。

**6. 11/14・15取得事故を再発させない**：
11/14用の先行公式選択取得Run 43142384975（`attempted_GET=1`、`FAILED_CLOSED`、公式原本なし）を隠さず、再起動で二重GETを発生させない。15日用に `.github/workflows/kyoto-nov15-encrypted-observer.yml` と `.github/workflows/kyoto-nov15-second-day-observed-oneshot.yml`、AES-GCM原本保存、取得原本/受領証照合、GET前の時刻・履歴・暗号鍵チェック、未通信と証明できた場合だけ再試行する安全機構を実装済み。取得準備・暗号化等130テストPASS [Run 43345111049](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43345111049)。**15日の真正原本・予定時刻・馬連/枠連取得成功は未実証**。 `KYOTO_JRA_ARCHIVE_AES256_HEX` はGitHub Secretの存在を別途確認する（値は開示・Gitコミットしない）。PC/SPのURL推測禁止、公開GitにHTML平文を置かない、別ホスト間の共有取得排他はまだ未認定。11月14日・15日が過去の日付になったら当該実行の証拠を最新Runで確認し、事後原本を事前予測に変換しない。

**7. 開発実行順序**：まず最新HEAD・CI・移行バックアップの状態を確認し、最新パックの未完工程と一致させる。以降、①真正P1→P6→P8の未接続MVP（次回の取得機会がなければ安全なオフライン実装を続ける）、②EVO-02/EVO-08を使うADD/ENSEMBLE候補生成、③EVO-07独立認定強化、④新スマホ統合を並行して前進させる。「次の大きな節目まで」はコード実装→異常・破壊回帰→同一コミットCIの新しい達成を目指す。ただし正式35/100の増加と研究用サブ工程完成は分離。資料だけ作って完了報告しない。成功済みGET/CIを必要なく再実行しない。

**8. 本番/復旧の保護**：GitHub `main`、本番Turso、現存Secrets、公開Streamlit、実馬券購入・実資金を無承認変更しない。趣味と業務を分離。移行バックアップのワークフロー `.github/workflows/kyoto-implementation12-verified-migration-backup.yml` は追跡ソースZIP/Git bundle/SHA256/EXACT_SOURCE_HEADを90日Artifactで保存する。**Run/Artifact/ZIP checksum/HEADが成功したと確認してから復元可能と報告**。外部本番DB・Secrets・過去のGitHub Artifact本体は含まれない。バックアップの存在をソース一式から推測しない。

**9. 最初の回答**：読み取った現HEAD、実証済み最新CI、移行用バックアップRun/Artifactの有無、固定管理表を簡潔に示す。正確に継続できる状態にしたうえで、上記次工程に着手する。必要な情報を再質問する前にGitHubの既存原本・仕様・検証記録を十分検索する。実装や検証ができなかった場合はできなかったと正直に報告し、憶測のPASSや%更新を禁止する。

**【完全移行指示・以上】**
