# 京都競馬AI｜P1-FB 第一実装節目（2026-11-06）

## 作業位置
- 対象レース：2026-11-07京都1R〜12R 148頭。
- 第14バッチ完了・最新正本：`docs/diagnostics/jra_p1_batch14_96_profiles_20261106/status.json`。96頭詳細確認、未確認52頭、有効過去走592件、京都1R〜8R全頭確認済み。
- P1-DUAL-01〜08 の追加設計要件：`docs/KYOTO_AI_P1_PC_SP_BIDIRECTIONAL_FAILOVER_REQUIREMENTS_20261106.md`。
- 第14バッチ成功後のP1-FB実装を開始。既存ALG01〜13、P1→P8順序変更なし。

## ゲートFB-1：ネットワークなしの双方向切替判断（PASS）
- 実装：`diagnostics/jra_p1_failover_offline.py`。
- 単体テスト：`tests/test_jra_p1_failover_offline.py`、**15ケース成功**。
- CI [42173245186](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42173245186) 全ジョブsuccess。
- PC→SP、SP→PC、双方失敗、片側正常、全項目一致・競合、別馬混入、同一チャネル二重使用、取得期限超過、SHA/原本保存不備、失敗元の独立障害維持、上書き拒否を検証。
- 証拠：`docs/diagnostics/jra_p1_fb_offline_20261106/status.json`。HTTPなし、予測採用なし。
- 注意：この部分は**既に入手した結果を評価するオフライン切替判断器**であり、PC版/SP版の自動HTTP取得や本番フォールバックを実装したことにはならない。

## ゲートFB-2：公式SP版の馬プロフィール原本を使用した独立解析（限定的PASS）
1. 既存SP版京都11R出馬表原本（ベンチマークrun 42159644686）をSHA照合し、**同じ京都11Rの出走馬16頭**の公式SPプロフィールリンクを実際のHTMLから抽出。原本表中の全プロフィールリンク24件には馬以外のリンクもあるため、同定済み出走馬16頭との一致を別途確認済み。証拠：`docs/diagnostics/jra_p1_fb_offline_20261106/sp_11r_profile_links.json`。CI [42173364101](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42173364101) success。
2. そのうちPC版で過去走30件検証済みの**京都11R馬番1・モンドプリューム**の公式SPプロフィールに対し、取得日時2026-11-06T06:17:18.681693+00:00を記録した限定診断GETを1回のみ実施。
3. SP原本を解析**前**に保存。SP HTML SHA-256：`b26d60b459e8d5936df50f78bcdfa482fd291c3b630f55fbb3ac5041f86dac22`。元の生HTMLはGitHub Actions 3日間保存のArtifact。リンク：`docs/diagnostics/jra_p1_fb_offline_20261106/sp_profile_receipt.json`。
4. 独立SP解析器：`diagnostics/jra_p1_sp_profile_offline.py`。PC版14列とは異なるSP版2列を対象に、公式原本SHAを固定して**31履歴行→通常過去走30件＋出走除外1件、invalid 0**を確認。
5. 既にPC版で確認済みの同一馬の過去走30件と**件数一致**。比較証拠：`docs/diagnostics/jra_p1_fb_offline_20261106/sp_profile_real_parity.json`。
6. オフライン検証CI [42173793835](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42173793835) success、追加のJRA通信0。

## 未完了・次のゲート（厳守）
- **PC/SP同一馬の行単位の実データ完全一致（開催日、距離、芝/ダート、着順、除外/中止など）**はまだ証明していない。件数一致だけを完全一致と呼ばない。
- SP版解析器の別形式・転出転入・障害・新馬・不整合行に対する独立テストと複数馬の実原本検証は未完了。
- PC・SPの個別アダプターへ組み込むネットワーク管理（既知の公式リンクだけ／通信上限／2秒間隔／再取得禁止／時点カットオフ）、未解決障害ID管理、ソース矛盾の発見・隔離、相互フォールバックの実負荷・精度比較を実装・検証する。
- `live_automatic_switch_authorized=false`、`prediction_ready=false`、`training_ready=false`。SP版取得成功を本番自動切替成功と誤認しない。
- 原本保存はActions Artifact 3日間が中心で、恒久原本保存・利用条件の検討は未完了。
- **再開位置：P1-FB第2段階：PC/SPの同一馬履歴の行単位照合・両専用アダプター回帰テスト**。それを通過してから取得経路自動切替へ段階実装し、P1の残52頭へ戻る。事前に取得成功済みの96頭のPC版URLへ再アクセスしない。
- `main/app.py`、Turso、公開モデル、実馬券台帳は変更しない。追加費用なし、業務用Work/Codexと分離。

## 履歴上の補足
- SP実証で使った11Rモンドプリュームは既にPCで検証済みの1頭。**新しい96頭の人数には加算しない**。比較用の2つ目の情報源として扱う。
- 第14バッチは取得/再解析が成功したが旧再解析レシートの件数定数が2のままだったため、原本の再アクセスなしに独立オフライン再解析・受入修復を実施。確定CI [42172828429](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42172828429) success。

## 第2節目（2026-11-06追記）
- **新しい進捗正本**：`docs/KYOTO_AI_P1_FB_STAGE2_REAL_ROW_PARITY_HANDOFF_20261106.md`。この第1節目記録の行数一致だけで完了と扱わない。
- 京都11RモンドプリュームのPC/SP公式原本で通常過去走30行の主要7項目＝210セル一致、競走除外1件一致。オフラインの双方向切替判断は追加9件を含む24件の回帰テストを通過。実運用の自動HTTP切替は未実装・未承認。
- 検証CI：`42174355278`（31イベント行比較）と`42174577868`（実原本の共通正規化＋対称切替ゲート）が成功。次の実装節目はP1-FB第3段階。
