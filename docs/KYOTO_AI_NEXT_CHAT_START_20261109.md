# 京都競馬AI開発｜新チャット開始用・完全指示（2026-11-09 最終）

これは既存の**個人趣味プロジェクト** `papaneko-ai/kyoto-keiba-ai` の**継続開発**である。新規設計・既存コード破棄・合意事項の再構成を禁止する。2026年11月9日の前チャット「実装06」から、GitHubの実コードと証拠を引き継ぐ。

## 第一指示：新しい開発を行う前の必須確認
1. GitHub開発ブランチ `jra-html-diagnostic-20261105` の**現在HEAD**と本番 `main` のHEAD、最新の独立バックアップをそれぞれGitHubで確認し、前回からの差を整理する。既知の本番main SHA `471b60e632d878b52b6dcb4aa1a622becba40882` は改変しない。
2. ルート `KYOTO_AI_START_HERE.md`、`docs/KYOTO_AI_20261109_COMPLETE_MIGRATION_PACK_FINAL.md`、`docs/diagnostics/kyoto_ai_resume_evidence_registry_v1.json`、`docs/diagnostics/kyoto_ai_full_resume_ci_reconciliation_20261109.json`、`docs/KYOTO_AI_ALGORITHM_REQUIREMENTS_REGISTER_v1_20261106.md`、`docs/KYOTO_AI_ALGORITHM_AND_EXECUTION_ROADMAP_20261106.md` を実際に読む。ファイルが見当たらなければGitHub上で検索し、内容を想像で補わない。
3. `diagnostics/kyoto_resume_gate.py` を、保存済みGitHub Artifact `13482994623` の最新APIメタデータ、またはSHA検証済み携帯復旧ZIPとともに検証。ゲートがブロックした場合は**原本・資料の同定を先に修復**し、すでに取得したHTMLを再GETしない。
4. GitHub Actionsの実施状況は `/repos/papaneko-ai/kyoto-keiba-ai/actions/runs?branch=jra-html-diagnostic-20261105&per_page=100` で一覧確認し、run/job/logを追う。PR専用APIやcombined status空だけで「CI未実施」と誤解しない。成功を主張する場合は実run ID・結論を明示する。

## 既達成果：再設計・無駄な重複調査禁止
- 京都2026-11-07出馬表12R・148頭、過去走日付396件。
- 詳細プロフィール96頭：過去走あり77頭／履歴なしを証拠付き確認済み19頭。未取得52頭。合計592過去走。
- 実PC HTML原本84頭をバックアップから再解析成功：過去走485件・特徴量335項目一致。PC版原本未復元12頭（各Rの馬番1）、記録上107過去走は原本再証明不可。
- 復旧Artifact ID `13482994623`、run `42176719321`、有効期限2027-02-04、外側SHA256 `49d61bff4eca82405d9d63e4244092e0fd2650bec5f899eba4f5ed2679c68863`。携帯ZIP `KYOTO_AI_P1_REAL_ORIGINAL_84_REPLAY_VERIFIED_20261109.zip`（SHA256 `7e16c23a595e13574554a7970cfc8ec3c4de652337f0bcbd7934ce1af4c83bd9`）。
- 公式オッズPC/SP画面は11/06の一時点で未発表。11/07一日を通じて未発表だった意味ではない。10/31過去**最終**オッズ馬連120組／枠連36組は11/07の発走前価格として使用禁止。
- P2履歴148行19列のCSVは存在。P3馬連/枠連理論計算・P4期待値・P5予算・P6 LAB限定仮想台帳と再起動・訂正の研究実装あり。較正済みモデル、ライブ予想、実仮想購入は未完成。
- P6複数点の合計額上書きによる損益バグは修正済み。Python3.11の診断アプリ構文エラーとAppTest存在しない属性も修正済み。実行履歴台帳に原因・修正・成功runを保存済み。
- 11/09今回 `diagnostics/p1_prerace_market_coverage.py` と `jra_p1_intake_bridge.py` へ馬連全組合せの検査を追加。18頭153組、欠落を拒否。GitHub Actions run `42569049451` success（8+16=24テスト）。これは合成値の**構造検査**であってJRA実発走前オッズの取得ではない。

## 必須維持仕様
- P1～P8を順序維持。ALG-01～13、EVO-01～08（EVO-07独立評価とEVO-08意外性発見を含む）を省略しない。
- 通常スマホで操作、無料・軽量・高速。推奨2～3R（最大4）、原則1R2点（最大3）、馬連/枠連選択、予算は上限で使い切り不要、上位集中と手動調整。
- 事前時点に存在した情報だけを凍結保存し、仮想投資と実馬券を厳格に分離。確定結果・払戻・返還・訂正に対して重複計上せず採点。時系列で新旧を独立比較し改善確認後のみ進化採用、悪化時ロールバック。推測による買い目・勝率・回収率表示は禁止。
- 旧公開`app.py`は設計参考にしない。`main`、Turso、Secrets、実購入記録はユーザー承認なしに変更しない。趣味用の開発を仕事のWork/Codexへ混ぜない。

## 次に実行する大きな節目
**新開催日の公式出馬表・馬連/枠連発走前全オッズの、適法・安定・無料の取得と原本時点固定**を最優先。取得権限が未確定なら無許可の自動HTTPを行わず、手元で正当に保存された原本を入力するオフライン経路で実証する。全組合せ・取消・発売状態・公式出典・発走前UTC・モデル較正が揃わないなら`prediction_ready=false`とし、見送る。P1受入を通過後にP2～P6の実レース縦断検証へ進む。

**実行方針**：不要な確認を挟まず、区切りの大きな単位で実装→現行ファイルとのGit blob照合→GitHub Actions実ログで検証→根本原因修正→受入証拠・バックアップを作成。問題が起きたら既済の成功・失敗を最初に照合する。移行直後の再設計と既済工程のリプレイを禁止。
