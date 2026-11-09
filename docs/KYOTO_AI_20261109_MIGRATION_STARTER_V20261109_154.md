# 京都競馬AI｜新チャット開始指示書 v2026-11-09-154

この指示書は以下の全文を新しいChatGPTチャットの最初のユーザーメッセージに貼り付けることを目的とする。GitHubに保存した移行正本と一致させること。旧指示文・過去チャットでの推測より最新の独立証拠を優先する。

---

## 【新しいChatGPTに貼り付ける指示文】

**京都競馬AI開発・既存実装の継続依頼（ゼロからの再設計禁止）**

あなたはGitHubリポジトリ `papaneko-ai/kyoto-keiba-ai` の既存京都競馬AIプロジェクトを継続して開発してください。これは個人趣味であり業務用Work/Codexとは分離します。旧公開アプリを新設計の参考にせず、本番の `main/app.py`、公開アプリ、Turso、実馬券台帳、Secretsを無承認変更しないでください。原則追加費用0円。実践投入を最優先にしてください。

**最初にGitHubの最新HEADとCIを確認してください。** 開発ブランチは `jra-html-diagnostic-20261105`。必ず以下をGitHubから**実際に取得・読了し、作業を開始**してください。

**最初に読む5資料**
1. `docs/KYOTO_AI_20261109_COMPLETE_MIGRATION_PACK_V20261109_154.md`【最新・完全移行正本】
2. `docs/KYOTO_AI_20261109_STAGE5_154TEST_CLOCK_SCHEDULER_MILESTONE_AND_HANDOFF.md`【最新実装受入】
3. `docs/diagnostics/jra_p1_fb_stage5_observed_clock_154tests_20261109.json`【機械可読合格証拠】
4. `docs/diagnostics/jra_p1_batch14_96_profiles_20261106/status.json`【公式データ取得実績】
5. `docs/diagnostics/kyoto_ai_evolution_requirements_manifest_20261106.json`【全工程・EVOの保持】

**続いて必読の要件資料**
- `docs/KYOTO_AI_ALGORITHM_REQUIREMENTS_REGISTER_v1_20261106.md`（ALG-01～13）
- `docs/KYOTO_AI_ALGORITHM_AND_EXECUTION_ROADMAP_20261106.md`（P1～P8）
- `docs/KYOTO_AI_P1_P8_ENHANCEMENTS_AND_WINNING_TICKET_SETTLEMENT_20261106.md`
- `docs/KYOTO_AI_VIRTUAL_INVESTMENT_AUTOMATED_FEEDBACK_PERMANENT_POLICY_20261106.md`
- `docs/KYOTO_AI_AUTONOMOUS_EVOLUTION_SIX_CAPABILITIES_REQUIREMENTS_20261106.md`（EVO-01～06）
- `docs/KYOTO_AI_INDEPENDENT_EVOLUTION_CERTIFICATION_AUDIT_20261106.md`（EVO-07）
- `docs/KYOTO_AI_INSIGHT_SURPRISE_DISCOVERY_HYPOTHESIS_ENGINE_20261106.md`（EVO-08）
- `docs/KYOTO_AI_CONTINUITY_AND_STAGE_GATE_RULES_20261106.md`
- `docs/KYOTO_AI_P1_PC_SP_BIDIRECTIONAL_FAILOVER_REQUIREMENTS_20261106.md`

**前チャットでの最新実装節目（2026-11-09時点）**
GitHub Actions run `42549866841`、job `128942805561` で、オフラインPC/SP模擬取得・通信予約・観測時計・原本保存・障害隔離の**154件がすべて成功**。実際に2秒以上の待機をするテストを含む。ただし、**JRAへの実HTTP GETは0件**、本番HTTP自動取得・異ホスト予約同期・公式SPリンク全馬実証・法的/利用条件の確認は**未達**である。成功を誇張してはいけない。

公式実データの確定時点：2026-11-07京都12レース・計148頭。保存・検証済みプロフィール96頭、未取得52頭、有効過去走592件。**本日は11月7日より後なので、残52頭を事後に取得して発走前の予想情報として扱ってはいけない**。保存済み原本を保護し、既成功URLの再GETはせず、新しい開催について発走前の新規証拠が必要。GitHub上の初期資料に残る「詳細12頭・未取得136頭」は古い履歴値である。

**再開地点はP1-FB第5段階の残り（実通信安全・公式PC/SPリンク独立同定・異ホストの共通予約・利用条件確認）**。P1全体は未完。P2～P8へ飛ばさず、工程どおりに進める。PC単一路線を安全な実践投入への暫定優先案として検討できるが、PC/SP双方向要件自体は消さない。

**必須の開発習慣**
- まずソース・原本SHA/UTC・ログ・HEAD・CIを確認し、「実証済み／オフラインのみ成功／合意済み未実装／未証明」を明確に区別。
- 安全な診断ブランチ上の実装・テストは、必要以上の質問で止めず、次の大きな節目まで進める。**本番操作・実HTTPへの切替・新課金・規約上不明な通信は無承認で行わない**。
- P6の発走前凍結仮想投資、公式馬連/枠連の的中組番・確定払戻・返還/訂正、P7 EVO-07の独立進化認定、EVO-08の「閃き」の反証試験を必ず保持する。実投資と仮想は厳密分離。
- 実践投入できる縦断機能を優先。新しい複雑な設計や反復する模擬テストだけでデータ取得と予測の実装を遅らせない。
- 変更したコード・合格/不合格CI・原本・未証明事項・次の工程をGitHubに記録し、独立バックアップを作成。**新しいチャットでも既存実装を作り直さない**。
- チャットが長くなり履歴の取り違えが起きそうなら、適切な大きな節目で移行を提案し、最新の移行パックと指示書を更新する。

**開始時の返答では、読み込んだ正本、実際のHEAD、154件CI、96/148頭、P1-FB第5段階の未完ゲートを確認した結果を簡潔に示し、そのまま実装へ着手してください。**

---

## この指示書の管理
- 上記指示文は内容全体をコピーする。ユーザーへの短縮案内を別途表示しても、GitHub上の本ファイルは削除しない。
- 正本 `docs/KYOTO_AI_20261109_COMPLETE_MIGRATION_PACK_V20261109_154.md` と必ずセットで扱う。
- 154件という結果と2026-11-09という現在地は作成日時点のスナップショット。次のセクションで新しいCIやコミットがあれば実物を照合し、独立証拠により更新する。
