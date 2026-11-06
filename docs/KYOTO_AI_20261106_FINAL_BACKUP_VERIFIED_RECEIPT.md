# 京都競馬AI｜2026-11-06終業前バックアップ実在検証

## GitHubによる実際の確認済み項目
- 依頼：日本時間2026-11-06 16:00終業前に、P1-FB第4段階の成功地点を固定し、全コード・進捗・保存済みHTMLの復旧バックアップを作る。
- **最終CI**：`42176287433` はすべてsuccess。17+16+11+15=59件の模擬HTTP/通信予算/特殊行/双方向判断テストが成功。実JRAへのGETは0。開発環境だけ。
- **最初の固定バックアップ**：`backup/p1-fb-stage4-20261106-close`、コミットSHA `855aa94dd1a562f7d258f09b4bf619e561ff4aea`。終業引継ぎ書 `docs/KYOTO_AI_20261106_END_OF_DAY_BACKUP_AND_RESUME.md` を含む。
- **原本18組収録済み固定バックアップ**：`backup/p1-fb-20261106-final`、コミットSHA `22bb8d933649bc82734c58ff246c19c4da0032d5`。上記引継ぎ書のほか `diagnostics/eod_20261106_original_artifacts_manifest.json` と `diagnostics/build_eod_20261106_bundle.py` を含む。
- **復旧ZIP生成ジョブ**：GitHub Actions `42176719321`、`backup`ジョブ **success**。固定ブランチ`backup/p1-fb-20261106-final`からHEADを取得し、GitHubに既存保存されていた公式原本Artifact **18グループを再利用（JRAアクセス0）**。少なくともHTML90個存在することをジョブ中に検査。ソース一式のZIP・原本TAR.GZ・SHA検証マニフェストを単一ZIPに内包して、GitHub Actions Artifactにアップロード。
- **ダウンロード可能なZIP**（GitHubログイン要）：
  https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42176719321/artifacts/13482994623
- Artifact ID：`13482994623`、名称：`kyoto-ai-nov6-2026-final-recovery-code-and-source-originals`、保存成功サイズ **1,874,655バイト**。GitHub上の`expired=false`を確認。
- **保存期限**：GitHub API確認時`2027-02-04T06:47:55Z`（日本時間**2027-02-04 15:47:55**）。期限付きであり**恒久保管ではない**。独立Gitバックアップブランチは別途存続。
- ジョブログ確認済み原本TAR.GZのSHA256：`42f64264c0a8a86bf6ff0d41d1d71a1ff36cc07e00b534f813d21ac1f701c634`。
- Artifactアップロード時GitHub表示SHA256：`49d61bff4eca82405d9d63e4244092e0fd2650bec5f899eba4f5ed2679c68863`（これはGitHubがZIP Artifactとして表示する圧縮パッケージのハッシュであり、内包ソースTARのSHAとは別）。
- 厳密な原本全件完全性について：**すでに消失済み、あるいは当初保存されなかった失敗GETのHTMLまで復旧したとは主張しない**。保存が存在し、取得に成功した18組だけを収録。解析済み証拠と同一取得時点のSHAはGitHubレシートを照合する。
- **本番`main`はSHA `471b60e632d878b52b6dcb4aa1a622becba40882`で変更なし**。Turso・公開モデル・実馬券記録も変更なし。
- P1確定データは96/148頭、未取得52頭、正しく解析した有効過去走592件、京都1R〜8R全馬。次は`batch_15`だが自動取得は未承認。P1-FB第4段階モック合格で、実運用自動フォールバックは未完成・無効。
- 次回は`docs/KYOTO_AI_20261106_END_OF_DAY_BACKUP_AND_RESUME.md`を先に読み、P1-FB第5段階の統合と証拠/利用条件ゲートから再開。新しいチャットへの移行も可能。16:00以降の予約された作業や自動取得は存在しない。

## バックアップ取得方法
GitHubにログイン後、上記Artifactリンクを開きZIPを保存。期限に依存しないコードと検証レシートの復元はバックアップブランチ `backup/p1-fb-20261106-final` の[Code → Download ZIP]から取得できるが、**CodeのZIPはActions Artifact保存の生HTMLを含まない**。
