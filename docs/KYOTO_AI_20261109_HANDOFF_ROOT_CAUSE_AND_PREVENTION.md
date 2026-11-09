# 京都競馬AI｜引継ぎ漏れによる重複調査の根本原因と再発防止実装（2026-11-09）

## 1. 事実経過と再発要因
- 2026-11-06：`docs/KYOTO_AI_20261106_FINAL_BACKUP_VERIFIED_RECEIPT.md` は、18組の原本取得Artifactを束ねた復旧ZIPを明記。GitHub Actions run `42176719321`、artifact `13482994623`、HTMLを含む原本tar SHA-256、保存期限まで記載していた。
- 11月9日の継続開発：この正本を確認せず、「実HTML原本の所在が未確認」と扱い、周辺の所在検索・チェックコードを新設。**既に存在していた取得成果の探索を繰り返した**。
- 11月9日の追跡調査：既存Artifactを実際にダウンロード。実HTML86件（馬プロフィールPC84件、SP診断2件）、プロフィール原本84頭・過去走485件・335特徴量を再解析し、旧レジストリと完全一致。原本12頭はこのZIPにはない。
- 原因は「当時の資料不足」ではない。**最新成果物・証拠・元の取得場所を単一レジストリで検索できず、開発開始時に必須証拠の読取と現存検証を要求する実行ゲートがなかった**こと。静的な移行パックは古い60頭時点などを含み、文書を見つけた順番で新旧が逆転し得た。

## 2. 今回実装した恒久対策
### A. 一つの再開入口
`KYOTO_AI_START_HERE.md` を開発ブランチのルートに新設。新しいチャット、端末、担当者は先にここから再開。最初に読む資料、Artifact ID、再開コマンド、未完課題を記載した。
従前の `docs/KYOTO_AI_CONTINUITY_AND_STAGE_GATE_RULES_20261106.md` にも、この入口と再開検査を必須と追記。古い移行パックは削除せず履歴として保存。

### B. 統一されたエビデンス台帳
`docs/diagnostics/kyoto_ai_resume_evidence_registry_v1.json`：
- 既存正本6ファイルの**現在のGit blob SHA**を固定（文書・status・148馬レジストリ・84頭原本再解析証拠）。
- 2026-11-06復旧ArtifactのID `13482994623`、run `42176719321`、SHA-256 `49d61bff4eca82405d9d63e4244092e0fd2650bec5f899eba4f5ed2679c68863`、期限 `2027-02-04T06:47:55Z`。
- 別途保管済みの再現用ZIP `KYOTO_AI_P1_REAL_ORIGINAL_84_REPLAY_VERIFIED_20261109.zip` の既知SHA-256 `7e16c23a595e13574554a7970cfc8ec3c4de652337f0bcbd7934ce1af4c83bd9`。
- **取得確定**：京都11/07の148頭、詳細96頭（過去走あり77、履歴なし確認19）、未取得52、過去走592件。
- **原本から実再検証**：84頭／485件／335特徴量、復旧ZIPにない12頭の107件は証拠なし、と区別。推奨予測・学習は不可。

### C. 再開前の「失敗時停止」プログラム
`diagnostics/kyoto_resume_gate.py`：
- 必要資料の消失、内容差分・Git blob SHA不一致、古い人数への逆行、原本再解析実績をゼロと誤認する記録、Artifact ID/SHAの変更を拒否。
- GitHub APIから**その時点で**取得したmetadata（id/expired/digest/expires_at）か、SHAが一致する携帯用ZIPを求める。
- どちらもない場合は `BLOCK_NEW_IMPLEMENTATION` を出し、CLI終了コード2。復旧Artifactが期限切れの場合も、確認済みローカルZIPのSHAがなければ先に進めない。
- 成功しても `RESUME_EVIDENCE_ACCEPTED_NOT_LIVE_AUTHORIZATION`：P1実通信・実予測の許可ではない。歴史的原本の再取得・公式URLの重複GETは不可。
- 読取専用、stdlibのみ、GitHubやJRAに自動通信しない。ユーザーの本番環境を書き換えない。

### D. 回帰検査とCI
- `tests/test_kyoto_resume_gate.py`：本物の148馬レジストリを用いた**13件のテストをローカル実行し13/13 PASS**。
- `diagnostics/kyoto_resume_gate.py` とテストのGit blob SHAが、手元で実行したソースと**2/2一致**。
- `.github/workflows/kyoto-ai-resume-evidence-gate.yml`：GitHub上でテストを再実行した後、`gh api` で原本Artifactの最新metadataを取得し、正本の6ファイルのSHA/計数をゲート検査。最後にJSONレシートを保存。
- 今回GitHub connectorで現在の正本6ファイルのGit SHA一致 **6/6**、実Artifactの`expired=false`とSHA一致を確認。
- **GitHub Actionsの新workflow自体の実行成功は、run ID/job/logが独立確認されるまで未確認**。不要なメールの原因になる全pushの監視ワークフローにはせず、関連するファイルが変わった時のみのpushと手動`workflow_dispatch`に限定。

## 3. 継続開発時の受入順
1. 新チャット初手で `KYOTO_AI_START_HERE.md` を開く。開発ブランチと現在HEADをGitHub APIで取得し、`main`が保護されたままか確認。
2. 証拠台帳v1、旧要件13項目/工程P1～P8/進化EVO-01～08、**96頭確認済み／84頭原本再解析済み／12頭のPC原本欠落**を読む。
3. Artifact `13482994623` の現状をGitHub APIで確認する。存在不能時はSHA照合済み携帯用ZIPから復旧。**取得に成功した古いURLの再GETはしない**。
4. `python -m diagnostics.kyoto_resume_gate ...` を実行。結果をレシートに残し、拒否なら**新規実装ではなく根拠の修復**に戻る。
5. ここまで通過したら次工程は未解決のP1（許容された新開催日の出馬表・発走前馬連/枠連オッズ）。P3～P6研究用コードを「実用化済み」と扱わない。
6. 新たな実証やArtifactの保全状態が変わったら、古い台帳を黙って上書きせず、正本v2を作成し入口を更新。旧レシートは削除しない。

## 4. 再発防止の範囲と残る限界
- **防げること**：原本Artifact IDの見落とし、消失した正本での作業、証拠の矛盾した集計、確認なしの「原本ゼロ」判定、同じ証拠収集の反復判断。
- **防げないこと**：GitHubに接続できない状態の遠隔実行、まだ取得されていない新開催日のデータ、JRA利用条件、外部時刻の真実性、将来の新Artifactの自動発見、ユーザーのGitHub branch protectionの強制。ChatGPTは新チャットでこの入口を実際に読む必要がある。Actionsは関連ファイル変更時・手動起動のみで、ブランチ全pushを必ず技術的に遮断する設定ではない。
- 必要以上のCI実行・通知メールを避ける。原本HTMLはGitHub APIの保存期限後も自動では残らない。携帯用ZIPのユーザー自身の保全が重要。
- **この修正を「全チャットの引継ぎを自動保証」とは呼ばない**。現在の既知事故について検査・停止・再開位置を強化し、次回の実開発で確実にこのゲートを通す。

## 5. 今回の判定
**原因特定：済／同根問題（古い静的記録・バックアップ見落とし・再開前証拠不足）対策：正本台帳＋入口＋検査プログラム＋13件回帰＋CI定義として実装／ローカル検証：13/13 PASS／現行正本6件＋Artifact metadata照合：PASS／新CI実行確認：未達。**
