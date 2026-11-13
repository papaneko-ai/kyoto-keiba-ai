# 京都競馬AI開発・実装13｜完全移行指示・現状固定版
作成日：2026-11-13
対象：個人趣味プロジェクト `papaneko-ai/kyoto-keiba-ai`
作業ブランチ：`jra-html-diagnostic-20261105`
本書は旧版の途中状態（31.25%/CI実行中など）を整理し、**確定済み43.75%を移行基準値として一本化**する。最新HEADと同一SHAの最終CIは新セクション冒頭に再確認する。

## 1. 新セクションの最重要命令
1. 開始時は、**恒久規程** `docs/KYOTO_AI_PERMANENT_RESEARCH_REUSE_AND_SECTION_HANDOFF_POLICY.md` と、**二段階進捗合意** `docs/KYOTO_AI_PRE_DATA_READINESS_PROGRESS_AGREEMENT_20261113.md` を最初に実読する。これらのルールを再度ユーザーに指示してもらわない。
2. **以前の研究成果と現行ソース・テスト・成功/失敗CI・復旧アーティファクトを実読**し、REUSE→REPAIR→INTEGRATE→NEWの順に検討して、同一機能を作り直さない。修理や局所改善は必須なら行う。古い研究台帳の「未実装」は今のコードの事実を保証しない。
3. **取得前準備100%**に至るまで、原則としてJRA実取得の成否を待たず、オフラインで可能なP2～P8の実装・統合を推進する。
4. **固定16項目R01～R16**、現状 **7/16=43.75%**、未認定9件。次の「大きな節目」はこの確定数値を、独立した受入テスト・同一HEAD CI・復旧バックアップで**43.75%より上昇**させること。分母や受入条件を勝手に変更しない。
5. **取得前準備100%認定時に従来の正式評価基準へ復帰**する。旧認定を改変・リセット・流用しない。
6. チャットが長くなって止まる前にアラートし、完全な移行パックを作ることは**セクション共通の恒久義務**。都度ユーザー指示を待たない。

## 2. 確定した定量評価（比較基準）
|指標|前回|今回|増減|
|---|---:|---:|---:|
|取得前準備完成率|31.25%|**43.75%**|**+12.50pt**|
|固定受入項目|16|16|0|
|合格項目|5|**7**|+2|
|未認定項目|11|**9**|-2|

認定済: **R03** 勝馬/2着/敗退馬特徴発見、**R05** 学習・選択・未使用の三期間モデル選択、**R06** 馬連/枠連確率整合、**R09** 日次選択と100円配分、**R11** 発走前LAB凍結と改ざん検出、**R12** LAB確定払戻・返還・訂正採点、**R13** 永続LAB台帳と集計。
未認定: **R01, R02, R04, R07, R08, R10, R14, R15, R16**。ファイルの存在だけで認定しない。全項目の固定受入条件は正本 `docs/diagnostics/kyoto_predata_readiness_rubric_v1.json`。

従来の独立指標は維持：研究・開発工程100%、固定32/32、研究卒業100%、主要21機能群組込100%、**実開催接続0/6、実用能力独立下限0/100、最終20ゲート35/100**。最終認定は7/20項目のオフライン範囲のみ（F07/F10/F11/F12/F16/F17/F18）。これらを真正なJRA運用成功と混同しない。

## 3. 実際の保存成果と証拠（移行資料を更新する直前の確定スナップショット）
- GitHub HEAD: `f1cc8f4fc41cdc4e69cbbde2880422abc3c591b7`。
- 同一HEADの継続CI: **Run 43366298131 / Job 131691386631 = SUCCESS**（成功27ステップ）。採点Artifact `14009939983`。
- 同一HEADのソース・Git履歴・SHA256復旧バックアップ: **Run 43366298055 / Job 131691386468 = SUCCESS**、Artifact `14010761080`（90日保持設定）。
- **注意：本書を修正した新HEADのCIやバックアップは上記の「旧HEADの成功」と区別する。** 本書の更新・最終保存後の新HEAD/CI/backupが同一SHA SUCCESSかを確認し、ユーザーに実際の新しい値を提示すること。移行先でもHEADを再照合する。
- バックアップはトラッキング済みソースZIP、Git bundle、SHA256SUMS、復元指示であり、**外部Turso本番DB、Secrets、JRA過去原本・GitHub Actionsに分散した外部成果物を含まない**。「完全バックアップ」を外部サービス全部の復元と誤認しない。

## 4. 既存研究の正本・先行機能の再利用ルート
- `docs/KYOTO_AI_ALGORITHM_REQUIREMENTS_REGISTER_v1_20261106.md` と `docs/KYOTO_AI_ALGORITHM_AND_EXECUTION_ROADMAP_20261106.md`：ALG01-13、P1-8、券種、時点、進行順。
- `docs/KYOTO_AI_HYBRID_SELF_EVOLUTION_MODEL_ARCHITECTURE_20261112.md`：EVO01-08、MODIFY/ADD/ENSEMBLE/KEEP・ROLLBACK、独立監査。
- `docs/diagnostics/kyoto_feature_reuse_inventory_v1.json`、`docs/diagnostics/kyoto_change_intent_v1.json` と `diagnostics/kyoto_development_preflight.py`：既存機能と修正の事前棚卸し。関連する実装とテストの**実読**が必要。
- P2: `diagnostics/p2_first_second_feature_discovery_lab.py`、`diagnostics/p2_p3_p5_offline_feature_bridge.py`、既存P2三群発見系。
- P3: `diagnostics/p3_offline_model_tournament.py`、`diagnostics/p3_three_window_selection_lab.py`、`diagnostics/p3_lab_calibration_audit.py`、`diagnostics/p3_p6_research_no_bet.py`。PL/Harville基準、5候補比較、三期間モデル選択、馬連120組/枠連同枠確率。Bolton–Chapman/Benter/ML混合は本格フィット済みと偽らない。
- P4/P5: `diagnostics/p4_source_bound_model_ev_research.py`、`diagnostics/p5_source_bound_race_ranking_lab.py`、`diagnostics/p5_bounded_risk_capital_lab.py`、`diagnostics/p3_p5_p6_synthetic_day_lab.py`。馬連・枠連、市場EV、最大4R、最大3点、予算上限・見送り。
- P6: `diagnostics/p6_source_bound_ranked_freeze_lab.py`、`diagnostics/p6_virtual_settlement_fixture_lab.py`、`diagnostics/p6_fixture_durable_ledger.py`、`diagnostics/p6_fixture_temporal_aggregate.py`。ハッシュ付き事前凍結、追記型台帳、訂正の差替え再計算、累積ROI/最大ドローダウン。固定受入 `tests/test_r11_predata_freeze_acceptance.py`（14件）、`tests/test_r13_predata_durable_accounting_acceptance.py`（12件）。
- P7: `diagnostics/p7_hybrid_shadow_evolution_cycle.py`、`diagnostics/p7_evo_bounded_candidate_constructor.py`、`diagnostics/p7_add_ensemble_candidate_constructor.py` と認定済みF17/F18の研究監査。既存モデル生成・独立評価を作り直さずR14統合を優先。
- P8: `diagnostics/kyoto_new_mobile_paper_ui.py`、`diagnostics/p8_uploaded_archive_shadow_app.py`、既存RG06モバイルChromiumテストとローカル再起動テスト。旧 `main/app.py` の設計/コードを流用しない。
- 修理・再現・復旧履歴はGitHubの対象ファイルに紐づくコミット/テスト/CIで直接照合し、変更後の影響範囲だけ独立の回帰証拠を揃える。

## 5. 次に進める実装の優先順位
1. 未認定9項目のうち**R01/R08**の真正な原本に偽装できないオフライン受入契約・馬連/枠連市場完全性/時刻/欠落停止を既存P1/P4部品から再利用・統合。
2. **R02**の発走前特徴量・欠損・未来漏洩、**R07**の較正母数/不確実性（少数合成レースの実績を過大評価しない）を検証。
3. **R04**のモデル拡充、**R10**リスク戦略の比較、**R14**自己進化部品の全体統合、**R15**スマホの仮想収支までの操作、**R16**全工程の固定LAB E2E/復旧を進める。
4. 目標は、実データ取得後に追加の大規模開発なしで安全な仮想投資稼働実験を開始できる**オフライン準備100%**。その後の真正実開催証拠による稼働認定は別基準。

## 6. 失敗防止・保護対象
- 取得済み公式HTML（2026-10-31京都154頭、2026-11-07京都148頭・詳細96頭・過去走592件）、PC/SPリンク独立検証等の過去研究は記録を実読して再利用し、終了済みの結果・最終オッズを発走前時点データと誤認しない。新しいJRA GETが失敗しても取得前準備のオフライン作業は続ける。
- 同一実行環境以外のTurso/SQLite接続・本番稼働の実証は未認定。ネットワークで許可を推定せず、取得原本の来歴とタイミングを実証する。
- **保護**：`main`、本番Turso/Secrets、公開Streamlit、ユーザーの実馬券購入、業務Work/Codex。一切無承認変更しない。
- 安全な進化のみ。自己進化候補を研究用の成功だけで本番へ自動採用しない。採用は未使用時系列と独立監査、劣化時復帰が必要。
- **早期移行アラートは恒久運用**。セクションが重くなり停止・文脈誤認する前に警告と完全移行資料を自律作成する。

## 7. 実装13開始指示（全文）
> 京都競馬AI開発・実装13として、`papaneko-ai/kyoto-keiba-ai` の開発ブランチ `jra-html-diagnostic-20261105` で継続してください。まず `docs/KYOTO_AI_IMPLEMENTATION13_MIGRATION_AND_PRE_DATA_PROGRESS_20261113.md` と恒久運用規程、二段階進捗合意書、固定16評価台帳、研究正本、機能棚卸しをGitHubの**最新HEADで実読**し、当該HEADのCI/Job/Artifactと復旧バックアップがSUCCESSであるか照合してください。取得前準備の確定基準値は**43.75%=7/16**、未認定9項目（R01,R02,R04,R07,R08,R10,R14,R15,R16）です。次の節目は**43.75%を超える**こと。重複を避けて既存研究成果のREUSE/REPAIR/INTEGRATEを優先し、実データ取得待ちを理由に止めず、合格テスト・CI・復旧バックアップまで完了させてください。固定指標の前回/今回/増減と残作業を毎回報告し、取得前準備100%達成時は元の正式評価基準に戻してください。`main`、Turso本番、Secrets、公開Streamlit等は変更禁止です。セクションが長くなる**前に**ユーザーへ移行警告を出し、完全な引継ぎパックと開始指示を準備してください。この2つの恒久ルールは再指示不要です。
