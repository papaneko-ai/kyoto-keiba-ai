# 京都競馬AI｜開発再開の唯一の入口（2026年11月9日以降）

**このファイルはチャット移行・開発再開の最初に必ず読む。** 静的な移行パックの「原本未発見」「次のバッチ番号」を、そのまま現在の事実と解釈しない。

## 1. 最初に読む正本
- `docs/diagnostics/kyoto_ai_resume_evidence_registry_v1.json`：固定済み原本、Artifact、保存済みSHAと参照先の機械可読台帳
- `docs/KYOTO_AI_20261109_REAL_HTML_84_REPARSE_AND_RECOVERY_MILESTONE.md`：再発見・再解析済みの**本物のHTML84頭・過去走485件・特徴量335項目**
- `docs/KYOTO_AI_20261106_FINAL_BACKUP_VERIFIED_RECEIPT.md`：既存復旧用Artifact `13482994623` の発見・保存事実
- `docs/diagnostics/jra_p1_batch14_96_profiles_20261106/status.json`：歴史的累積96頭／未取得52頭／592件
- `docs/KYOTO_AI_ALGORITHM_REQUIREMENTS_REGISTER_v1_20261106.md`、`docs/KYOTO_AI_ALGORITHM_AND_EXECUTION_ROADMAP_20261106.md`、`docs/KYOTO_AI_CONTINUITY_AND_STAGE_GATE_RULES_20261106.md`：ALG-01～13、P1～P8、EVO-01～08を維持

## 2. 開発開始前の必須実行
対象：`papaneko-ai/kyoto-keiba-ai`、ブランチ `jra-html-diagnostic-20261105`。現在HEADは毎回GitHubに実問い合わせを行う。古いドキュメント記載HEADを最新値として使わない。

GitHub保存済みのアーティファクトの存在を **GitHub APIから毎回** 再確認し、保存したJSONを使って以下を実行：

```bash
gh api repos/papaneko-ai/kyoto-keiba-ai/actions/artifacts/13482994623 > /tmp/kyoto_recovery_metadata.json
python -m diagnostics.kyoto_resume_gate --root . --artifact-json /tmp/kyoto_recovery_metadata.json --out /tmp/kyoto_resume_receipt.json
```

API上のArtifactを利用できない場合は、保存済みの復旧ZIPを指定して独立SHA照合できる（ZIPは保管先から取り出す必要がある）：

```bash
python -m diagnostics.kyoto_resume_gate --root . --local-recovery /path/to/KYOTO_AI_P1_REAL_ORIGINAL_84_REPLAY_VERIFIED_20261109.zip --out /tmp/kyoto_resume_receipt.json
```

**ゲート終了コード2なら新規実装・再収集へ進まない。** 記録された原因を確認し、既存原本・正本の所在を修復する。実行レシートの「合格」は既知資料の参照整合だけを意味し、JRAライブ自動取得や予測を許可しない。

CIも `.github/workflows/kyoto-ai-resume-evidence-gate.yml` で同じ処理を行う。CIログ・run IDが実際に確認されない段階ではGitHub Actions成功と主張しない。

## 3. 再調査禁止ではなく、**無駄な再調査禁止**
- 「HTML原本がない」と即断しない。まず復旧Artifact ID `13482994623` とダウンロード済み別保全ZIPの照会。
- 2026-11-07京都の148頭：96詳細確認済み。そのうち**84頭の原本を復旧・再解析済み**、残る**12頭（各レース1番）の元PC原本は未復元**。未取得52頭は別分類。
- 原本84頭の有効過去走485件、残る12頭の台帳記録107件、合計592件。335特徴量の再計算一致。
- 原本が見つかったことを「発走前の新開催日データ取得」「公式オッズ取得」「予測準備完了」とは混同しない。
- 完了済みURL・バッチを重複してGETしない。JRAの利用許可未確認の自動アクセス禁止。
- **新しい問題**が見つかったら対象・証拠・原因・修正・検証・残りの問題を保存し、同根の事故を検索。復旧したバックアップは消さない。

## 4. 次の実開発位置
P1は未完了。**新開催日の許容されたデータ取得経路と発走前の馬連／枠連オッズを確立する工程**が優先。過去に解決したZIP復旧・84頭の再解析・研究用P6数理テストを、証拠なしに繰り返して進捗とみなさない。P1の未完がある間、P3～P6は研究用コードであり実用運用完了ではない。

## 5. 安全保護
本番 `main/app.py`、Turso、Secrets、公開モデル、実購入履歴はユーザー承認なしに変更しない。無料／スマホ中心を維持し、趣味を業務用Work/Codexと分ける。

## 6. チャット移行時に貼る短文
「京都競馬AI既存開発を継続。まずGitHubの `KYOTO_AI_START_HERE.md` を読み、`kyoto_ai_resume_evidence_registry_v1.json` と `kyoto_resume_gate.py` で原本・バックアップ・最新進捗を照合。84頭の実原本再解析と485過去走・335特徴量は既達で繰り返さない。Artifact 13482994623と携帯用復旧ZIPを先に探し、原本不在と誤認しない。P1～P8・ALG01～13・EVO01～08を維持。現在の未完P1（新開催日の合法的な出馬表と発走前馬連/枠連オッズ）から進め、本番main/Turso/Secretsは保護する。ゲートの証拠確認なしに工程を進めない。」

## 【最新】2026-11-09 新チャットへの確定移行入口

- **最優先で読む完全移行パック**：`docs/KYOTO_AI_20261109_COMPLETE_MIGRATION_PACK_FINAL.md`
- **そのまま新チャットへ渡す指示書**：`docs/KYOTO_AI_NEXT_CHAT_START_20261109.md`
- **今回のP1市場全組合せ受入証拠**：`docs/diagnostics/p1_market_completeness_CI_verified_20261109.json`。実行ID `42569049451`、8+16=24件PASS。18頭153組は**模擬数値の構造検証**であり、実際のJRA発走前オッズ取得成功ではない。
- GitHubでの最新HEAD・現在のCI・復旧Artifact・本番mainを照合してから開発再開。保存済みの旧HEADがその時点の最新だと推測しない。
- P1～P8／ALG-01～13／EVO-01～08を保持し、過去の成功・失敗記録と未達の公式発走前市場を区別する。

## 7. 2026-11-09 後発の確定済み実測・CI調査（**新チャットで必読**）
- `docs/diagnostics/kyoto_ai_full_resume_ci_reconciliation_20261109.json`：GitHub REST APIで**push時のActions実行**まで列挙し、各ジョブ／ログを確認した最新のCI実測台帳。以前のPR限定APIやcombined statuses空配列で「CI成功未確認」と判断しない。
- **再開ゲート** run `42568017053` success（13件、必須原本・進捗24ファイル照合）。
- **実HTML原本再解析** run `42565633708` success（84頭／485過去走／335特徴量）。
- **全12R実出馬表と過去オッズ遮断** run `42567681829` success（12件、148頭、過去走日付396件）。`diagnostics/p1_historical_day_handoff.py` と `docs/diagnostics/JRA_ODDS_READINESS_ACCEPTANCE_20261106.json` は既存の11月6日13:05のPC/SP未発表画面を確認。過去10/31馬連120組・枠連36組は**最終オッズ**であり11/07の発走前価格に代用禁止。
- **P3～P6の収支計算** run `42567612106` success（20+18+15=53件、発走前凍結・訂正・再起動研究用）。それ以前のrun `42564668348` は失敗、原因は合計賭け金変数を最後の買い目額で上書きした不具合。修正済み。失敗履歴を無視しない。
- **P6ソース同一性** run `42567627196` success（15件）。
- **診断用Streamlit AppTest** run `42567945287` success（11+12+10+14+7+13=67件、画面テスト）。以前の15回失敗はPython3.11非互換のf-stringとAppTestの不存在属性参照を修正した。正確な現況は上記成功runのログを参照。
- 最新の「HTML原本保全84頭」と「出馬表全12レース取得148頭」と「詳細プロフィール96頭（原本未復元12頭）」は**異なる範囲を数える**。合算や再取得は禁止。
- **最新の引継ぎ台帳には現在24件の必須ファイルSHA**を登録。出馬表12本、PC/SPの未発表オッズ・10/31最終オッズ証拠、解析器を含む。GitHub Actionsは実通信を認可するものではない。
- 新チャットではまずGithub Actions RESTの `/repos/papaneko-ai/kyoto-keiba-ai/actions/runs?branch=jra-html-diagnostic-20261105&per_page=30` に相当する実行履歴を確認し、対象のjob/step/logを辿る。問題を再分析する前に**既存の失敗と修正済みrun**を照合する。


## 2026-11-09 P1 dual-market offline integration checkpoint (next larger milestone)
- Read `docs/KYOTO_AI_20261109_P1_DUAL_MARKET_OFFLINE_INTEGRATED_MILESTONE.md` and `docs/diagnostics/kyoto_ai_p1_dual_offline_integration_checkpoint_20261109.json` before repeating any quinella/bracket coverage work.
- `diagnostics/jra_p1_intake_bridge.py` now exposes `inspect_bundle_and_dual_snapshot` connecting source-byte/time checks and strict dual market structure; 13 isolated plus 10 integration regression cases were added. This is **not** a JRA-authenticated or prediction-ready path.
- New push CI must be verified with actual Actions run/job/log. A PR-only workflow API empty response is not evidence of missing push CI. Do not promote checkpoint to PASS without the actual run.
- Historical 84 original profiles and all former successful Actions are unchanged. Main/Turso/Secrets remain protected.

## 2026-11-09 P1 three-independent-originals upgrade (v2 authoritative continuation)
- Continue from `docs/KYOTO_AI_20261109_P1_DUAL_THREE_ORIGINALS_MILESTONE_V2.md` and `docs/diagnostics/kyoto_ai_p1_dual_three_original_checkpoint_v2_20261109.json` **instead of stopping at the earlier two-original dual-market checkpoint**.
- `inspect_three_original_dual_intake` requires separate racecard, quinella and bracket market originals with distinct SHA256 and UTC bindings. The older two-source entry point remains non-production for compatibility. 14 more tests added; 37 new cases in this wider integration cycle.
- Actual live GitHub push run/log for these new commits has **not yet been independently confirmed**; do not say CI passed merely because workflows are present. Do not promote fixture completeness to authenticated JRA data or `prediction_ready=true`.
- Next P1 gate: authorized real future-race sources, independent official origin and sales/withdrawal evidence, CI proven, forward-only paper trade. Never repeat the 84 historic HTML original recovery.


## 2026-11-09 Continuity root-cause repair — MUST CHECK BEFORE NEW FEATURE WORK
- **Authoritative incident and end criteria:** `docs/KYOTO_AI_CONTINUITY_ROOT_CAUSE_AND_FINITE_DELIVERY_20261109.md`.
- **Existing-code inventory:** `docs/diagnostics/kyoto_feature_reuse_inventory_v1.json`; **work intent:** `docs/diagnostics/kyoto_change_intent_v1.json`.
- Always-run action: `.github/workflows/kyoto-ai-always-run-continuity.yml`. It checks existing feature code/evidence paths, rejects duplicate-`NEW` declarations, reruns the historical `kyoto_resume_gate.py`, and has **no push path filter**. Verify actual same-commit GitHub push run/job/log before declaring PASS.
- PC/SP acquisition, odds parsing and P3-P6 research **already have source code**; do not say they are unimplemented. Inspect those modules' actual code before changing them. Treat historic final odds as not current prerace odds.
- **Enforcement boundary:** CI does not physically block pushes without required status check/branch protection. GitHub ruleset listing is empty and branch protection read currently returns 403. Do not claim an unbypassable lock.
- P1–P8 are unchanged, but judge completion by actual end-to-end acceptance gates C0–C6, not by mock test count or isolated wrapper count.


## 2026-11-09 PC/SP actual existing parser reuse milestone (continue here)
- Read `docs/KYOTO_AI_20261109_PC_SP_EXISTING_PARSERS_REUSED_MILESTONE.md` before designing acquisition or SP fallback again.
- Previously existing `diagnostics.jra_multi_capture_20261106.parse` is now future-date parameterized; previously existing `diagnostics.jra_pc_sp_benchmark.pc_rows` and `sp_rows` feed `reconcile_saved_racecards` for offline source-byte SHA/UTC, roster parity and SP fallback.
- Both channels already matched frozen real 2026-11-07 racecards in a historical five-race benchmark. Initial 11R SP 0-row failure was repaired; use `JRA_SP_RUNNER_PARITY_FIXED_20261106.json` not the old broken parity record.
- Current GitHub Actions run `42575107672`, job `129020946710`: 13+8=21 tests PASS on the source-refactor workflow at commit `9512b6b096364467e7fb671d97387654c9e3477c`. Later commits require same-commit continuity CI revalidation.
- This was no JRA GET; live PC/SP retrieval, fresh official prerace quinella/bracket quotes and official scratch feeds are still not integrated. No predictions or real tickets authorized.


## 2026-11-10 客観的進捗率（初回実測31％）
- 正本 `docs/KYOTO_AI_PROGRESS_MEASUREMENT_POLICY_20261110.md`、固定32条件 `docs/diagnostics/kyoto_progress_rubric_v1.json`、成功CI根拠 `docs/diagnostics/kyoto_progress_evidence_v1.json`、減少理由台帳 `docs/diagnostics/kyoto_progress_regressions_v1.json` を読む。
- `diagnostics/kyoto_progress_metrics.py` は GitHub run/job/HEAD祖先/既存ファイルを実検証し、証拠に紐づく合格条件のみ採点。2026-11-10初回 GitHub Actions run `42730742998`、HEAD `7449fea43086bd39e270eb97a694c0dbcdc0e8ed` で31/100点・8/32件合格、未達24件。P1 12/25、P2 3/10、P3 4/15、P4 3/10、P5 2/5、P6 4/15、P7 0/10、P8 3/10。
- 従来の45％は主観的見積もりであり、31％との差を実装後退と見なさない。次回から同一32条件・同一100点配点で比較する。減少時は実装回帰または以前の合格誤判定について証拠・復旧条件を必須とする。
- `.github/workflows/kyoto-ai-always-run-continuity.yml` に既存再開ゲートと進捗採点を一体化。進捗実測の成功run/job/logと `kyoto-ai-progress-report` Artifactの存在を毎回照合する。アプリの予測精度や実稼働を示す数値ではない。

- 2026-11-10進捗計測の永続基準：`docs/diagnostics/kyoto_progress_baseline_20261110.json`。GitHub Actionsの90日Artifactが失効しても、実測31％（run `42730742998`）を起点として差分比較できる。採点器の `persistent_baseline()` は旧45％への改ざんを拒否する。以後、終了時はrun/job/logと今回/前回/差分/未達を必ず確認。
