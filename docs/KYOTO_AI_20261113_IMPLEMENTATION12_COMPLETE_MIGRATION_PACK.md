# 京都競馬AI開発・実装12｜完全移行パック（2026年11月13日）
**対象リポジトリ：** `papaneko-ai/kyoto-keiba-ai`  
**移行元：** 京都競馬AI開発・実装11（11月13日終了時点の研究用開発・JRA取得予備対策）  
**移行先：** 京都競馬AI開発・実装12  
**開発ブランチ：** `jra-html-diagnostic-20261105`  
**パック作成直前に確認した開発HEAD：** `a777aa93eaa8a6a6f6d052978fb3997b076ef8ea`  
**当該HEADの継続CI：** [Run 43354983177](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43354983177)、Job `131654771278`、**SUCCESS**  
**重要：** 本文のHEADは「パック作成前の実装済み基準」。本ファイル・開始指示書・バックアップの保存コミットによりHEADは変わる。**次チャットでは必ずGitHubから最新HEADと最新CI/バックアップを再取得**し、ここに記したSHAを最新と誤認しない。

## 0．このパックが必要な理由・正本の階層

同じ研究の無意味な再実行、既済証拠の見落とし、過去の成功を未実証に戻す説明、合意したALG/EVOの省略、データ取得事故、固定指標の分母変更を防ぐ。

正本の優先順：
1. GitHubの**実際の開発ブランチHEAD、コード、Actions run/job/artifact**。この文書の記述より現在の生証拠を優先し、不一致は差分を明示する。
2. 正式固定の最終20ゲート `docs/diagnostics/kyoto_final_completion_criteria_v1.json` と採点台帳 `docs/diagnostics/kyoto_final_20_gate_verified_state_20261112.json`。要件や採点を再定義しない。
3. 正式アルゴリズムと工程 `docs/KYOTO_AI_ALGORITHM_REQUIREMENTS_REGISTER_v1_20261106.md`、`docs/KYOTO_AI_ALGORITHM_AND_EXECUTION_ROADMAP_20261106.md`、`docs/diagnostics/kyoto_ai_evolution_requirements_manifest_20261106.json`。
4. 仮想投資と新UI `docs/KYOTO_AI_20261111_LIVE_PAPER_TRADING_MVP_EXECUTION_CONTRACT.md`、`docs/KYOTO_AI_VIRTUAL_INVESTMENT_AUTOMATED_FEEDBACK_PERMANENT_POLICY_20261106.md`、`docs/KYOTO_AI_20261111_UNATTENDED_CONTINUOUS_PAPER_TRADING_REQUIREMENT.md`。
5. 自己進化 `docs/KYOTO_AI_HYBRID_SELF_EVOLUTION_MODEL_ARCHITECTURE_20261112.md`、`docs/KYOTO_AI_AUTONOMOUS_EVOLUTION_SIX_CAPABILITIES_REQUIREMENTS_20261106.md`、`docs/KYOTO_AI_INDEPENDENT_EVOLUTION_CERTIFICATION_AUDIT_20261106.md`。
6. 最新実装チェックポイント：`docs/diagnostics/kyoto_20261113_generated_evo_candidate_16tests_checkpoint.json` および本書の「段階別証拠」。
7. 先行引継ぎ `docs/KYOTO_AI_20261112_F17_35POINT_COMPLETE_MIGRATION.md`：歴史的な発走前出馬表、正式結果原本、F17独立監査を継承する資料。現在のHEADや次工程は本書を優先。

## 1．プロジェクトの同一性と保護

趣味の無料運用・スマホ主体の京都競馬AI。GitHub/Streamlit Community CloudとTursoを利用。会社業務用Work/Codex等とは分離。既存公開 `main/app.py` の設計・古いUI/ロジックは新アプリの設計根拠に使わない。

**ユーザーの承認なく変更不可**：本番 `main`、公開Streamlit/アプリ設定、本番Tursoおよび既存DB、GitHub/Streamlit Secrets、実馬券注文・実支出、既存復旧ブランチとオリジナル証拠。開発コード・診断・CIは `jra-html-diagnostic-20261105` にのみ追加。生のHTML原本や鍵を公開GitHubに貼らない。資格教材等の仕事用環境に趣味開発を混ぜない。

**実際に取得できたかどうか**と**テストコードがPASSしたか**、**研究LABの合格**と**実開催の事前凍結証拠**、**GitHub ActionsジョブSUCCESS**と**原本保存成功**を、必ず別々に表示する。

## 2．不変のP1～P8 / ALG-01～13 / EVO-01～08

- P1：JRA公式PC/SPの実掲載リンクから安全に実データを取得。出走馬・馬ID・枠/馬番・過去走・騎手・馬場・発走時刻・馬連と枠連の**発売時点**オッズ、原本SHA、取得UTC、取消/除外、鮮度・欠損を記録。PC/SPは独立確認し、SP URLをPCの文字列から推測生成しない。ユーザーとは「公式ホームページを合理的な取得元として利用する」方針で合意済み。ドメインの記載を自動取得の法的許可の証明だと断定しない一方、許容された安全な公式ページ利用を理由なく永遠に停止させない。
- P2：勝馬と連対馬の特徴・距離/コース適性・休養/成長・脚質/展開・馬場・騎手・過去走を、自動的に探索・反証。未来情報混入は禁止。
- P3：ベースラインから複数モデル、較正、同一時点の勝率・連対組合せ確率を比較。候補を改良/新規追加/統合し、独立した未使用時系列で実証する。
- P4：真正な同時点馬連・枠連オッズを使い組合せ期待回収率・歪みを計算。終了後の最終オッズを事前オッズに偽装しない。
- P5：原則2～3レース、最大4。順位と期待値・信頼度・鮮度の短い根拠。買い目は各レース原則2点、最大3、馬連/枠連を選択、100円単位、日次予算は**上限で使い切る必要なし**。レース選択・配分調整・上位集中、全見送りと損失制御を実装する。
- P6：事前登録型の**仮想投資**を発走前に凍結（原本SHA/UTC・出馬表・モデル/特徴版・確率・買い目・単価・配分・時刻）。公式結果の速報/確定/訂正・払戻・返還・取消で自動採点し、仮想的中率/損益/回収率/最大損失・モデル比較を永続管理。未確定を的中なしと確定計上しない。実購入と厳密に分離。
- P7：自己進化と反例、独立監査、比較数調整、改善候補採用審査、劣化検知、旧モデルへの復帰。基準モデルを保護。**研究用PASSだけで本番モデルを自動切替しない。**
- P8：初心者でもスマホで使える新UI、開催日/券種/予算/見送り/順位/馬券/仮想投資/結果/モデル履歴・データ鮮度表示。新しい独立アプリで実装する。旧 `app.py` の画面・設計を流用禁止。

合意済み正式アルゴリズム **ALG-01～13** と進化能力 **EVO-01～08** は全件残す。EVO-01情報価値、02弱点発見、03影モデル、04反実仮想、05劣化検知、06制約付き改善、07独立進化認定、08意外性/反証発見。研究内の仮説番号 **HYP-01～08** をEVO能力の番号と混同しない。

研究→実運用の優先順は**真正な発走前原本→予測/推奨/仮想凍結→公式結果・払戻→自動採点→自己診断・候補→独立監査→採用/復帰→スマホ公開**。発走前情報の取得を追加研究のために先延ばししない。

## 3．固定進捗：改変禁止（2026-11-13移行基準）

| 指標 | 前回 | 今回 | 増減 |
|---|---:|---:|---:|
| 研究・開発工程認定率 | 100％ | **100％（32/32）** | ±0 |
| 固定32項目の合格数 | 32/32 | **32/32** | ±0 |
| 研究段階卒業達成率 | 100％ | **100％（12/12）** | ±0 |
| 主要21機能群工程組込率 | 100％ | **100％（21/21）** | ±0 |
| 実開催接続の独立検証 | 0/6 | **0/6** | ±0 |
| 実用能力の独立検証下限 | 0/100 | **0/100** | ±0 |
| 最終20ゲート独立認定下限 | 35/100 | **35/100** | ±0 |

正式20ゲート：F07/F10/F11/F12/F16/F17/F18 の7件が各5点、**計35/100**。残13件は未認定。採点根拠 `docs/diagnostics/kyoto_final_20_gate_verified_state_20261112.json`、固定ルーブリック `docs/diagnostics/kyoto_final_completion_criteria_v1.json`。研究LABの追加18件・16件・16件PASSによる新たな加点は不可。研究用％と実運用％を取り違えない。以降も**表の順・分母・両方のバー（研究100％、最終35％）を固定**し、変化があれば独立証拠と該当Fゲートを示す。最終スコア増減と研究の実装節目は別。

## 4．真正なJRA証拠として保存・継承するもの

1. 2026-11-06に**翌11月7日の京都開催出馬表**を発走前に取得した既存実績がある。京都12R/148頭、過去走日付396件、正規化スナップショット20テスト[Run 43139684683](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43139684683)。**「発走前出馬表を全く取得したことがない」は誤り**。ただし当該時点の馬連・枠連オッズ、必要全項目、実開催の仮想投資凍結は未証明。
2. 2026-10-31京都12レース/154頭の公式確定結果HTMLやプロフィールリンクを取得した既存実績。2026-11-07京都12レース/148頭、詳細プロフィール96件、未取得52件、過去走592件、京都8R馬番2の`invalid_history_rows`を保存。既存原本・Artifactを先に調べ、成功したHTTPを無駄に再実行しない。
3. 公式終了後結果の別原本：2026-10-25京都10Rと2026-11-08京都11R、合計31頭・馬連/枠連計4件の払戻を別々の公式HTMLから照合。[Run 43140647764](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43140647764) 16テストPASS。追記型SQLite台帳で別Run [43141692999](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43141692999) と [43141831772](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43141831772) の照合成功。**事後原本を発走前の予想や仮想利益として使わない**。
4. 正式自己進化EVO-01～08の研究データ連動・別式独立監査の成功：F17 [Run 43148780887](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43148780887) と [43148970085](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43148970085)、`docs/diagnostics/kyoto_f17_independent_eight_evo_certification_20261112.json`。過去の初期スクリーニング25件ではなく、原本計算と第二監査が受入根拠。F18の研究用復帰も真のJRA自動モデル切替ではない。

## 5．11月14日・15日の二段構え取得対策：現況を正確に引継ぐ

**11月14日の既存事故は消さない。** 先行ワークフロー [Run 43142384975](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43142384975) は2026-11-12 11:34 JSTに `attempted_GET=1` で `FAILED_CLOSED`。真正な`official_selection.html`取得成功の証拠なし。原因を「未掲載」と推測してはいけない。同一14日用one-shotを根拠なく再実行・起動フラグ作成しない。診断正本 `docs/diagnostics/nov14_existing_attempt_safe_stop_20261113.md`。

**11月15日の独立予備経路はコードに実装済みだが、真正な取得の受入は未達。**
- 公式PC選択原本→実際に掲載された15日京都開催リンクの観測、最大2 GETで失敗を保存：`diagnostics/kyoto_nov15_two_original_observer.py` と `.github/workflows/kyoto-nov15-encrypted-observer.yml`。
- 公開GitHubへの平文HTML保存を避け、AES-256-GCMで二原本と受領証をArtifactへ封印し、次ワークフローへ復元：`diagnostics/kyoto_nov15_encrypted_evidence.py`。
- 15日の観測原本・レースID・同一レースの真正出馬表・予定発走UTCを照合してPC発走前の出馬表/馬連/枠連を一回だけ取りに行く：`.github/workflows/kyoto-nov15-second-day-observed-oneshot.yml`、`diagnostics/kyoto_nov14_nov15_second_day_handoff.py`。
- 原本＋受領証SHA/バイト数の照合・偽のSUCCESS拒否：`diagnostics/kyoto_nov15_capture_acceptance.py`。公開Artifactには原本一式の暗号化版：`diagnostics/kyoto_nov15_full_capture_seal.py`。
- 取得前の入力・時刻・結果原本の異常系、GitHub ActionsのGET未実行だった失敗のみ再挑戦可：`diagnostics/kyoto_nov15_readiness_check.py`、`diagnostics/kyoto_p1_github_attempt_history_gate.py`。既存の別手動取得フローから15日を重複実行しない。SP URLの推測禁止。
- [Run 43345111049](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43345111049)：P1通信ゼロの取得準備・暗号化・二段階縦断など**130件の対象テストPASS**。証拠 `docs/diagnostics/kyoto_20261113_nov14_nov15_deep_gap_repair_130tests_checkpoint.json`。
- **残る重大な条件**：GitHub Actions Secret `KYOTO_JRA_ARCHIVE_AES256_HEX`（ランダム32バイトの64桁HEX）の安全設定は未確認、15日公式原本・レース別spec／roster／予定UTCと観測Run ID未認定、実開催当日のワークフロー一連動作未実証、GitHub/Streamlit/別ホストにまたがる共有取得排他は未証明。Secret値をChatGPT・Git・ログに貼らない。14日の取得事故はそのまま保存する。利用条件とHTTP発行回数・容量・時刻・エラー停止を守る。
- 最新の正本 `docs/KYOTO_AI_20261113_SOURCE_FAILURE_GAPS_REMEDIATION_AND_REMAINING_GATES.md` を照合。文書の旧方式（公開HTMLをあらかじめ5点置く案）は**後続の暗号化Artifact経路で置換**された部分があり、古い方式を復活させない。

**日付注意**：移行パック作成日は2026-11-13。14日と15日はまだ実開催の独立取得が終わったと認定されていない。次のチャットで暦日が進んでいた場合は本当に行われたRun/Artifact/原本の時刻を再確認し、開催終了後の原本を発走前データへ改名しない。

## 6．実装11で進めたハイブリッド自己進化：段階別コード・テスト・未完了境界

**基本方針**：MODIFY（既存改良）、ADD（新しいモジュール）、ENSEMBLE（複数統合）、KEEP/ROLLBACK（証拠不十分なら維持・劣化時復帰）。共通レースの同一原本/同一時刻に対する確率・資金配分・公式結果・仮想収支を比較し、EVO-07の別監査で初めて採用可否を判断。研究用候補の自動本番昇格は不可。

**基盤（完了した研究範囲）**：
- `diagnostics/p7_hybrid_model_registry.py`：BASELINE/MODIFY/ADD/ENSEMBLEの4種類、親モデル、特徴量/設定SHA、研究／認定境界、追記型履歴。
- `diagnostics/p3_hybrid_prediction_contract.py`：同一原本・時刻・馬番/枠番・馬連/枠連組合せ確率の共通契約。
- `diagnostics/p7_hybrid_shadow_evolution_cycle.py`：同一LABレースの基準/候補予測を結果前に凍結し、後続の合成結果から対数損失を算出、P7安全判定の採否を追記。偽造・同じ結果の重複利用を拒否。**新規18/18テスト** [Run 43352810566](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43352810566) SUCCESS。チェックポイント `docs/diagnostics/kyoto_20261113_hybrid_shadow_evolution_18tests_checkpoint.json`。
- `diagnostics/p7_evo02_evo08_shadow_bridge.py`：既存F17の弱点/意外性発見から、登録済み改善候補の研究計画をSHA固定し、別の未使用レース群でP7 Brier/対数損失の2評価。研究用**新規16/16テスト** [Run 43353928861](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43353928861) SUCCESS。 `docs/diagnostics/kyoto_20261113_evo02_evo08_shadow_disjoint_holdout_16tests_checkpoint.json`。
- `diagnostics/kyoto_f17_executable_lab_streams.py`：F17と新P7間の弱点・驚き事例分析を共通化した。新実装で重複した分析ロジックを作らない。
- **今回の最新節目** `diagnostics/p7_evo_bounded_candidate_constructor.py`：6件以上のLAB学習レースから同枠/異枠の非自明な倍率**12候補**を事前固定の範囲で探索し、対数損失が所定改善なら実行可能な**MODIFY研究用新モデル**を登録。同じモデル版・設定SHAから別期間の馬連/枠連確率を算出し、10件以上の未使用LABレースでP7独立Brier＋対数損失の両方を審査。12回の多重比較数を1回と偽装できない。**新規16/16テスト** [Run 43354731435](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43354731435) SUCCESS。チェックポイント `docs/diagnostics/kyoto_20261113_generated_evo_candidate_16tests_checkpoint.json`。
- 上記の最終チェックポイント保存済みHEAD `a777aa93eaa8a6a6f6d052978fb3997b076ef8ea` に対する継続CI [Run 43354983177](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/43354983177) / Job `131654771278` **SUCCESS**。必ず該当SHAを使う。新たな文書コミットの成功は別Runで確認する。

**未実装・未実証**：今回のモデル候補生成は枠間補正型MODIFYの研究用実装。制約付き**ADD／ENSEMBLEの実候補生成**、本当の馬・騎手・コース特徴を使う多数の実モデル、真正JRA同一事前時点・公式払戻を使ったモデル改善実証、外部独立の署名付きEVO-07認定、無人本番昇格/復帰は未完成。EVO-08の「意外な結果」を訓練データの中で発見したことを実際の新しい勝ち馬法則と認定しない。

## 7．再開順序：次に本当に作るもの

**第一優先：実開催P1→P6→P8のMVPを遅らせない。** 次の発走前時点が得られるときの公式出馬表・馬連/枠連、取得UTC・原本SHA・キャンセル/除外・発走予定UTCを保存し、既存の予測→期待値→予算→仮想投資凍結→公式結果/払戻確定→累積成績を実行する。未証明の出所がある場合は予測を捏造せず、オフラインでのP3/P7継続とP1不具合修正を並走する。真正な出走馬・予測・払い戻しを後付けで構成しない。

**第二優先：ADD/ENSEMBLEの制約付き候補生成**：現在の `p7_evo_bounded_candidate_constructor.py` を拡張または別のプラグインで、共通予測契約・同一発走前時点・12回等の比較数管理・結果リーク拒否を維持して実装。EVO-02/08探索結果→候補→凍結→独立検査を再利用し、既存MODIFYを作り直さない。

**第三優先：EVO-07独立認定を強化**：候補/基準を同一母集団・同一実価格で比較し、未使用時系列・多重比較・予算配分/見送り/ドローダウンと戻し判断・外部証拠の強度を追加する。自己署名した研究PASSを本番モデル承認としない。P6からの本当の仮想損益が揃うまで実用効果を宣言しない。

**第四優先：P8スマホ統合**：`diagnostics/kyoto_new_mobile_paper_ui.py`等の新設計を使い、研究/本番のモデル状態、推薦順位、見送り、予算、仮想累積、原本不足、時刻を表示。旧公開アプリのデザイン流用なし。

**第五優先：安全な復旧と継続性**：既存で成功したCIテストは、変更による回帰検証時を除き繰り返さず、疑わしい根本原因を調査し新しい反例テストを追加。成功したソース原本を無意味に再GETしない。CIの長時間待ちが必要なら、既存確認済み成果と現在の未完項目を随時報告する。

**節目の解釈**：実装・テストで新しいサブ工程が完成した事実は節目として記録するが、ユーザーが固定指標での進展を要求した場合は正式20ゲートの受入下限が35を超えたかを厳密に区別する。研究だけの合格で「40/100」を表示しない。成果は実装コード/差分/CI run/job/source SHAを添えて報告し、資料作成だけを節目にしない。

## 8．移行時の開始ゲート（実際の順序）

1. GitHubから `jra-html-diagnostic-20261105` HEADを読み、`main`と混同しない。HEAD差異があれば先頭から変更差分を評価。
2. 本書と `docs/KYOTO_AI_20261113_IMPLEMENTATION12_START_INSTRUCTIONS.md`、正式ロードマップ、固定20ゲート、最新3自己進化チェックポイント、11/14事故、11/15取得補強、直近CIを**すべて実読**。
3. 当該HEADの最新Actions Run/Jobを確認。テスト失敗は該当エラーのみ修正し、成功済み無関係試験をやり直す目的の変更をしない。
4. 実用化阻害要因（真正事前オッズ、発走前凍結、公式結果/P6仮想収支の一本化）を固定指標に照らして優先する。ADD/ENSEMBLE研究は並行して進めるがMVP実証を妨げない。
5. 新機能を開発ブランチにのみ書き、オフライン異常系＋既存CIの変更影響を検証。レース取得のHTTPは追加の明示実行条件の下だけに限定。
6. 最新HEAD/成功CI/未完/固定指標/復元証拠を一つのチェックポイントに保存。バックアップartifactのHEADと内容一致を検証してから「完全バックアップ」と報告する。

## 9．完全バックアップと復元の厳格な境界

- 今回 `.github/workflows/kyoto-implementation12-verified-migration-backup.yml` を追加。移行パック文書が開発ブランチに保存されると、**追跡ソース全体のZIP、全Git refsを含むGit bundle、SHA256SUMS、HEAD、復元説明**を作成し、ZIP検査・bundle verify・SHA検査の成功を確認してActions Artifactに保存する。保存期間90日。**実際のRun成功／Artifact ID／HEAD／チェックサムが確認できるまでは作成済みと宣言しない**。
- ZIPは指定HEADの追跡ファイルで、Git bundleはcheckout時点で取得されたrefsの履歴。いずれも外部のTurso本番DB、GitHub/Streamlit Secrets、過去のActions原本Artifact、利用者PCの未追跡DB、Streamlit設定を含まない。これらを含む「全システムの完全バックアップ」と偽称しない。
- 原本、DB、シークレットの個別バックアップは過去の保護した記録に従い別保管。Actions Artifactは期限切れで消えるため、必要ならZIP/bundleをローカルへ保管。
- 復元時：`sha256sum -c SHA256SUMS.txt` → `git bundle verify` / `unzip -t` → 記録されたHEADで開発ブランチを復元 → 同一コミットCI検証 → 外部DB/原本/Secretsは別途安全照合。mainを上書きしない。

## 10．移行後の初回指示

次のチャットは「**京都競馬AI開発・実装12**」とし、必ず `docs/KYOTO_AI_20261113_IMPLEMENTATION12_START_INSTRUCTIONS.md` の全文を貼り付ける（本書URLも添付）。GitHubで実際のHEAD、最新CI、バックアップアーティファクトを確認した後、完成した基盤を前提に**本当に未完成の次工程**から開始する。過去データ・アルゴリズム合意・採点表示・機密保護を省略しない。
