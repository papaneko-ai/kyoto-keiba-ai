# 京都競馬AI｜完全移行パック・正本 v2026-11-09-154

**目的**：新しいChatGPTチャット（セクション）が過去チャットの会話記憶に頼らず、GitHub保存済みの実証情報と承認済み要件を同じ順序で読み、過去の実績を壊さずに継続実装できるようにする。
**作成日**：2026-11-09。**状態**：確定済み履歴と最新テスト結果を統合した移行正本。新機能の実装完了宣言ではない。
**対象**：個人趣味の京都競馬AI。業務用Work/Codexとは分離。

## A. 一番最初に行う事実確認（必須・省略禁止）
1. GitHub `papaneko-ai/kyoto-keiba-ai` に接続し、**`jra-html-diagnostic-20261105`** の現行HEADと `main` のHEADをそれぞれ読み取る。読み取れない場合は未確認と明記し、推測で更新しない。
2. 本ファイル、同じフォルダの `KYOTO_AI_20261109_MIGRATION_STARTER_V20261109_154.md`、`docs/diagnostics/jra_p1_fb_stage5_observed_clock_154tests_20261109.json`、`docs/diagnostics/jra_p1_batch14_96_profiles_20261106/status.json`、`docs/diagnostics/kyoto_ai_evolution_requirements_manifest_20261106.json`を**実際にfetch**する。記憶や以前の回答だけで読んだことにしない。
3. 指定した要件／工程／証拠の正本一覧（後述）を読み、文書中の**時点の異なる数字・停止条件**を比較する。
4. Actions run `42549866841`（job `128942805561`）の最終状態をGitHubで確認する。2026-11-09時点で154件すべて成功。旧ランの成功/失敗は削除・改ざんせず履歴として扱う。
5. 実装前に「実証済み」「設計合意済み」「オフラインのみ検証済み」「未実装・未証明」を区別し、未完のP1-FB第5段階からのみ着手する。
6. もし本パック作成以降に新コミットや新しい受入証拠が存在すればそれを読み込んだうえで差分を照合する。**本パック内のHEADや154件は2026-11-09時点のスナップショット**であって永久に最新とは限らない。

## B. プロジェクトの恒久的な目的・運用制約
- 初心者でもスマホで簡単に使えるStreamlit Community Cloudの予想アプリ。内部ロジックは実データ・確率・期待回収率・リスク制御・独立検証で本格化。
- 馬連・枠連に対応。単純人気順や一般的ChatGPT予想を越える有用性を目標にするが、**的中率・利益の保証は禁止**。
- 追加費用は原則0円。GitHub＋Streamlit Community Cloud、DBはTurso採用。ただし**本番Tursoへのスキーマ変更・接続・書込みは無承認禁止**。Cloudflare D1の401調査は保留。旧公開 `main/app.py` のUI/モデル/構造は新アプリの設計参考にしない。
- **実践投入最優先**：機能設計を無限に増やさない。安全に実データ→予想→仮想投資→結果採点できる最小縦断機能を先に完結し、進化型研究は該当工程で段階的に高度化。ただし合意した必須EVO/ALGは削除しない。
- 1日の予算は上限で使い切り不要。原則推奨2～3レース、最大4レース。各レース買い目原則2点、最大3点。100円単位。馬連/枠連切替、ランキング、根拠・信頼度・鮮度・手動の金額比率調整、見送りを重視。
- 本番実購入と仮想投資は完全に分離。仮想は明示的に発走前凍結し、過去の払戻・結果から事後的に買い目を作らない。
- 予想、結果、払戻、オッズは**取得時点・原本SHA・版**を分離保存する。事後確定結果や最終オッズを事前予測に逆流させない。
- **常に診断ブランチで実装・テスト**。本番`main`、公開アプリ、Turso、本番Secrets、実馬券台帳は無断変更しない。既存の成功済みJRA URLを再GETしない。利用条件・レート・通信回数・証拠保全を優先する。

## C. 工程順序と合格条件（P1→P8を変更しない）
| 工程 | 必須内容 | 現在の事実 |
|---|---|---|
| **P1** | 公式出馬表、全馬プロフィール、過去走、騎手・調教・馬場・条件・発走前馬連/枠連オッズを必要な範囲で収集。取消・欠損・原本・UTC・SHA・時点保証。PC/SP比較と安全な切替 | **一部実証**。P1-FB第5段階のオフラインサブゲートまで、全体未完 |
| **P2** | 勝馬・連対馬と敗退馬の特徴差、交互作用、条件・時系列外挿、意外性仮説の発見 | 未実装 |
| **P3** | 人気順基準、Harville、Plackett–Luce、Bolton–Chapman型、Benter型、統計/MLモデル比較。較正・対数損失・Brier | 未実装 |
| **P4** | 発走前に時点固定した馬連/枠連オッズ、控除・取消・相関・確率から期待値計算 | 一部事後オッズ解析のみ。予想用は未完 |
| **P5** | 推奨レース・買い目・100円単位予算・見送り・手動微調整 | 未実装 |
| **P6** | 発走前凍結のペーパートレード、公式結果・的中組番・100円当り払戻・返還/訂正の自動採点、買わないレースも評価 | 部品のみ。縦断運用未完成 |
| **P7** | 自動で改善候補を発見/作成、時系列ホールドアウトで新旧モデル比較、独立EVO-07認定、劣化時ロールバック | 未実装 |
| **P8** | 新スマホUI、根拠・データ鮮度・累積仮想収支・進化レポート、障害時停止・無償運用 | 新UI本番未統合 |

**各工程は証拠・試験・負例・受入レシートなしにPASSにしない。** P4の取得部品などをP1と並行準備することは可だが、P1未PASSなのにP2～P8の本番採用を前倒ししない。

## D. 保全が必須の13アルゴリズムと追加8機能
原番号の名前・意図を無断変更しない。詳細は後記の原本を優先する。
- ALG-01 時点保証された特徴量取得
- ALG-02 勝馬／連対馬の特徴自動発見
- ALG-03 コース適性・展開・成長・休養・距離変更
- ALG-04 確率モデル群と基準モデル比較
- ALG-05 馬連/枠連の組合せ確率（同枠ゾロ目・取消等を含む）
- ALG-06 発走前市場価格・歪み・期待回収率
- ALG-07 確率品質・較正・損失・母数検証
- ALG-08 予算上限・リスク・見送り・配分
- ALG-09 事前凍結した仮想投資と実購入の分離
- ALG-10 公式結果/確定払戻による自動採点
- ALG-11 時系列分離の学習・自己進化・ロールバック
- ALG-12 PC/SP・データ源・安定性・通信制御・原本保全
- ALG-13 スマホUI・保守運用
追加EVOは**既存13項目とP1～P8の横断補強ID**であり工程やALGを増やさない。
- EVO-01 情報価値を計量した追加データ優先順位
- EVO-02 弱点／改善課題の自動発見
- EVO-03 同時点の影モデル選手権（新旧/市場基準）
- EVO-04 事前登録した購入方法・見送り・資金配分の反実仮想比較
- EVO-05 環境変化・性能劣化検知
- EVO-06 制約付きの自律的改善案研究・候補生成
- EVO-07 **EVO-06とは独立**の進化認定監査。事前登録試験、触れていない時系列ホールドアウト、同一レース比較、確率/リスク/収支/母数/多重比較、採用後劣化監視。証拠不備なら進化未認定。
- EVO-08 **意外性・閃き型発見**。常識の逆転、意外な条件の交互作用、予想外の外れ/人気敗退/見送りから反証可能な仮説を生成。単発大穴は仮説であり証明ではない。EVO-07で未知期間の独立反証後のみ採用候補。
**EVO-01～08は設計・正式合意済みであって、自己進化エンジン本体が実装されたという意味ではない。**

## E. 2026-11-09時点の実データの確定値とその解釈
- 対象 **2026-11-07京都、12レース、出走馬148頭**。公式出馬表からPCプロフィールへのリンクが確認された。代表的な実原本とソース証拠に基づき、**詳細プロフィール96頭、未取得52頭、有効過去走592件**。京都1～8Rの全馬分の詳細が揃ったとするstatusあり。
- 固定ソース：`docs/diagnostics/jra_p1_batch14_96_profiles_20261106/status.json`。このJSONの`next_batch:"batch_15"`は当時の計画上のラベルに過ぎず、`next_batch_automatically_authorized:false`である。**11月9日以降に11月7日の残52頭を取得しても発走前証拠として扱えないため、無断でbatch_15を実行しない**。
- 京都8R馬番2「グラニットピーク」の`invalid_history_rows`問題は、独立診断原本による再解析・移籍履歴の処理を記録済み。一方、当初失敗したHTTP GET原本自体が復元できたわけではなく、関連batch13は完全復元と断言しない。
- **公式結果HTML/過去の馬連・枠連の表構造抽出成功**は過去の検証。11/07当日の発走前の最新オッズの取得・固定、予想的中・実収益の証拠ではない。
- HTML原本の長期・期限外バックアップは`permanent_html_archive_completed:false`。GitHub Actions artifactsは保存期限があり、保全済みと誤らない。
- 古い台帳/工程表の「詳細12頭・残136頭」「約40％」は**作成当時の歴史的記述**。現在の進捗に置き換える際は**数字だけを編集して原本を書き換えず、後発受入レシートを優先**。

## F. 直近の実装済み機能・154件検証（**P1-FB stage5のオフライン下位ゲートに限る**）
最新の独立証拠：`docs/KYOTO_AI_20261109_STAGE5_154TEST_CLOCK_SCHEDULER_MILESTONE_AND_HANDOFF.md`、`docs/diagnostics/jra_p1_fb_stage5_observed_clock_154tests_20261109.json`。
- **GitHub Actions run `42549866841` / job `128942805561`**：154件成功。対象スイートは19+10+14+8+13+15+16+17+16+11+15の計154件。CIの実際の`time.monotonic`と`time.sleep`を使い2秒以上の**模擬PC→SP間隔**を確認。JRA追加GETは**0件**。
- `diagnostics/jra_p1_fb_stage5_registry_binding.py`：公式出馬表台帳148頭から、未取得52頭のPC版既観測URLを推測せず同定。SPリンクをPCトークンから生成しない。
- `diagnostics/jra_p1_fb_stage5_guarded_replay.py`：馬・URL・出馬表原本SHA・時点と締切チェック、HTML原本の排他・原子的保存、SHA照合、receipt原子的保存。
- `diagnostics/jra_p1_fb_stage5_global_attempt_registry.py`：**同一永続SQLiteファイルを共有する複数プロセス間**でURL事前予約・重複GET防止・予約の取り消し禁止、2秒の論理時刻間隔、通信回数上限。異なるホスト間で共有・安全とは未証明。
- `diagnostics/jra_p1_fb_stage5_ledger_replay.py`：予約台帳とPC/SPの**模擬応答**を連結し、取得失敗・原本・障害レシートを保全。
- `diagnostics/jra_p1_fb_stage5_live_preflight_disabled.py`：厳格な公式URL/UTC/単調時計/予想カットオフのオフライン検証、**ネットワーク処理は常時拒否**。
- `diagnostics/jra_p1_fb_stage5_offline_http_envelope.py`：メモリ上の模擬HTTP200/MIME/容量/リダイレクト/エンコード/原本の検証。実HTTP接続機能なし。
- `diagnostics/jra_p1_fb_stage5_scheduled_offline_replay.py`：固定メモリの模擬応答に対して取得直前に時計を再読込し、PC→SPの最低2秒と待機中の期限超過/時計逆行を検証。
- `diagnostics/jra_p1_fb_stage4_mock_adapter.py`および旧フェイルオーバー安全ガードは回帰テスト実施済み。
- 実運用HTTP、現実のDNS/TLS/リダイレクトや利用条件、複数ホストに共有する予約台帳、将来の実在するSP全馬公式URL、次の未発走開催の発走前原本を**実証したものではない**。自己進化・実馬券購入・本番予測は未実装。

## G. 未完問題を優先順位付きで引き継ぐ
### G1 最優先（次のP1-FB第5段階安全ゲート）
1. 公式サイトでの取得・保存・自動化の**利用条件と適法性**。確認できない事項は推測せず保留。アクセス制限の回避はしない。
2. **実HTTPクライアントの安全設計と独立した実証**：権限・適切なUA、許容接続先、TLS・DNS・タイムアウト・厳格な転送先禁止、サイズ/形式上限、発走締切、サーバー負荷を抑えた通信間隔、原本先行保存・エラー隔離。**現段階では実ネットワーク禁止**。
3. PCの証明済み公式リンクによる**限定単一路線**を実践投入向け候補として優先検討。SPのリンクが独立公式原本で証明できない馬はSP自動切替しない。PC/SP双方向フェイルオーバー要件は削除せず後続へ残す。
4. StreamlitとGitHub Actionsなど**異なるホスト**での同時URL重複取得・レート共有を、無料・低コスト・本番Turso保護を前提に実証。単一SQLiteパスのローカル成功をクラウド共有証明と混同しない。
5. 新しい未発走開催の**公式出馬表・発走時刻・原本SHA/UTC・馬ID・オッズ**を証拠付きで確定。11/07の事後データは発走前に混入させない。

### G2 P1完了へ
- 実用上必要な馬・騎手・調教・過去走/地方・馬場・出走取消・オッズ取得の成功/欠損/鮮度ゲート。原本期限外保全。予想前に不十分なら見送り。
- データ量が増えないまま無料のオフライン安全ゲートだけを無限増殖させない。上記制約の下で実践投入可能な最小縦断切片を優先。
### G3 後続P2～P8
- P2特徴/閃き、P3ベースライン/確率、P4時点オッズ、P5買い目、P6凍結仮想投資・公式結果/払戻の再現・自動採点、P7EVO-07独立認定・ロールバック、P8新スマホUI。
- 結果速報は正式利益ではない。`UNSETTLED`を0円/外れと誤集計しない。返還/取消/同着/複数的中組番の端数、二重受信と訂正を扱う。
- EVO-08の「閃き」は発見仮説の研究であり、反証できる未使用期間評価なしに昇格しない。

## H. 最も重要な技術的リスクと停止条件
- 事後取得値が事前予測へ混入する、取得UTCが不明、公式URLの同定に失敗、悪意/誤ったリダイレクト、過去に使用したURLの再訪、解析で誤った馬・レースID、公式払戻未確定の損益計上、無承認の本番DB更新があれば**停止・隔離・証拠保存**。
- CI 154件PASSはオフラインテストの品質証拠であり、的中率・回収率・モデル改善率・本番予測可能性ではない。
- 買い目を賭博的に保証したり、実購入を自動実行したりしない。仮想の成績と実購入は完全に別の台帳。
- 実データ取得困難なら原因・利用条件・無料APIの有無を整理して、可能な範囲でユーザーへ代替案を示す。公式制限を迂回しない。
- 本番移行・課金・外部連携・法的意味のある仕様変更は承認前に行わない。コードの小さな安全改良と検証は診断ブランチ上で継続可。

## I. 必読ソース一覧（ファイル単位で内容を取得）
**工程・要件の優先資料**
1. `docs/KYOTO_AI_ALGORITHM_REQUIREMENTS_REGISTER_v1_20261106.md`（ALG-01～13、初期数値は歴史）
2. `docs/KYOTO_AI_ALGORITHM_AND_EXECUTION_ROADMAP_20261106.md`（P1～P8）
3. `docs/KYOTO_AI_P1_P8_ENHANCEMENTS_AND_WINNING_TICKET_SETTLEMENT_20261106.md`
4. `docs/KYOTO_AI_VIRTUAL_INVESTMENT_AUTOMATED_FEEDBACK_PERMANENT_POLICY_20261106.md`
5. `docs/KYOTO_AI_AUTONOMOUS_EVOLUTION_SIX_CAPABILITIES_REQUIREMENTS_20261106.md`（EVO-01～06）
6. `docs/KYOTO_AI_INDEPENDENT_EVOLUTION_CERTIFICATION_AUDIT_20261106.md`（EVO-07）
7. `docs/KYOTO_AI_INSIGHT_SURPRISE_DISCOVERY_HYPOTHESIS_ENGINE_20261106.md`（EVO-08）
8. `docs/KYOTO_AI_P1_PC_SP_BIDIRECTIONAL_FAILOVER_REQUIREMENTS_20261106.md`
9. `docs/KYOTO_AI_CONTINUITY_AND_STAGE_GATE_RULES_20261106.md`
10. `docs/KYOTO_AI_ENGINEERING_PROACTIVE_RISK_REGISTER_20261106.md`
11. `docs/diagnostics/kyoto_ai_evolution_requirements_manifest_20261106.json`
**事実・証拠の優先資料**
12. `docs/diagnostics/jra_p1_batch14_96_profiles_20261106/status.json`
13. `docs/KYOTO_AI_20261109_STAGE5_154TEST_CLOCK_SCHEDULER_MILESTONE_AND_HANDOFF.md`
14. `docs/diagnostics/jra_p1_fb_stage5_observed_clock_154tests_20261109.json`
15. `docs/KYOTO_AI_20261109_STAGE5_HTTP_ENVELOPE_138TEST_MIGRATION_HANDOFF.md`（旧ゲートの履歴）
16. `docs/diagnostics/jra_p1_fb_stage5_http_envelope_offline_acceptance_20261109.json`
17. `.github/workflows/jra-p1-fb-stage5-offline.yml`
18. `docs/KYOTO_AI_20261106_FINAL_BACKUP_VERIFIED_RECEIPT.md`（期限付きArtifactの注意）
19. `docs/KYOTO_AI_20261106_END_OF_DAY_BACKUP_AND_RESUME.md`（旧受入時点の履歴）
20. `docs/KYOTO_AI_COMPLETE_MIGRATION_PACK_20261106.md`（歴史的追加記録。**本パックを最新優先**）
21. `docs/KYOTO_AI_NEW_CHAT_STARTER_20261106.md`（旧指示。新指示は本パック付属の別ファイルが優先）
**実装コード**
22. `diagnostics/jra_p1_fb_stage5_guarded_replay.py`
23. `diagnostics/jra_p1_fb_stage5_global_attempt_registry.py`
24. `diagnostics/jra_p1_fb_stage5_ledger_replay.py`
25. `diagnostics/jra_p1_fb_stage5_live_preflight_disabled.py`
26. `diagnostics/jra_p1_fb_stage5_offline_http_envelope.py`
27. `diagnostics/jra_p1_fb_stage5_scheduled_offline_replay.py`
28. `diagnostics/jra_p1_fb_stage5_registry_binding.py`
29. `diagnostics/jra_p1_fb_stage4_mock_adapter.py`
30. `tests/test_jra_p1_fb_stage5_scheduled_offline_replay.py` と関連回帰テスト群。
**全件の実読が一度に困難な場合は、工程台帳・直近レシート・次工程で変更するコードとテストを必読し、未読を明示してから段階的に補完。** 未読を読了と偽らない。

## J. チャット移行後の実行契約
1. 新チャット冒頭で `docs/KYOTO_AI_20261109_MIGRATION_STARTER_V20261109_154.md` の**指示文を実行**。
2. GitHub HEAD/Actions/原本実証statusを照合し、**読んだファイル名・現在地・4つの未解決項目**を簡潔に明示。
3. ユーザーが「次の大きな節目まで」と言った場合は、原則**改めて承認を求めず**、許可済みの診断ブランチ上で実装→テスト→レシート→バックアップまで継続。高リスクの実通信・本番接続・課金・権限変更は別の明示許可なしに進めない。
4. 該当ステージのPASS条件を満たせなければ、部分達成・未達理由・次の具体的な修正を報告し、勝手にP2へ進まない。
5. チャットが長くなり、重複説明、履歴の取り違え、重要な要件欠落が起きそうなら**大きな区切りで新セクション移行を先に提案**。最新GitHubパック・starterを更新後、移行を案内する。
6. 内容改訂時は「変更した要件」「元の合意との整合」「新旧レシートの差」「未実証」「main不変更」を明記。新チャットで設計を最初から作り直さない。

## K. 作成時点の整合確認
- 最新合格：**154件、CI run 42549866841、JRA追加GET 0件**。
- 最新公式保存済み対象：**2026-11-07京都148頭中96詳細、残52、過去走592**。日時の経過により過去レースの補完は発走前予測に使えない。
- **P1-FB Stage5オフラインサブゲートのみ合格、実HTTP・SP公式リンク全頭・複数ホスト共有予約・収益モデル・仮想運用は未完。**
- これは**実装済み**と**承認済み仕様**を区別するための移行正本であり、自己進化の実装完成・法的な使用許諾・本番競馬予想可能性を保証しない。
