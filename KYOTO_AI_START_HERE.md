# 京都競馬AI｜現在の開発再開入口（実装23・2026-11-19）

**これは新しい研究手順ではない。2026-11-09に実装済みの重複開発防止・再開ゲートへ戻す案内である。**

## 正本の所在と責務

- リポジトリ：`papaneko-ai/kyoto-keiba-ai`
- 本番設定：`main` の11月21・22日PC/SP 8枠（変更には個別の理由・差分検証が必要）
- 既存研究の正本：開発ブランチ `jra-html-diagnostic-20261105` の [KYOTO_AI_START_HERE.md](https://github.com/papaneko-ai/kyoto-keiba-ai/blob/jra-html-diagnostic-20261105/KYOTO_AI_START_HERE.md)
- 既存機能台帳：`docs/diagnostics/kyoto_feature_reuse_inventory_v1.json`（既存の25機能領域）
- 既存変更分類：`docs/diagnostics/kyoto_change_intent_v1.json`（REUSE / REPAIR / INTEGRATE / NEW）
- 既存のコード照合器：`diagnostics/kyoto_development_preflight.py`
- 既存の原本・復旧ゲート：`diagnostics/kyoto_resume_gate.py` と `docs/diagnostics/kyoto_ai_resume_evidence_registry_v1.json`

これらはすべて開発ブランチ上に存在を確認済み。**mainに同名ファイルがないことを、過去成果が消失したという根拠にしてはいけない。**

## ユーザー操作ゼロを原則とする再開手順

1. アシスタントがGitHubからmain・開発ブランチの最新HEAD、PR、既存Actions run/job/log、復旧記録を自分で確認する。GitHubから確認できる情報をユーザーに画面操作させない。
2. 作業要求を既存25領域と合意要件に照合し、`REUSE`／`REPAIR`／`INTEGRATE` の最小変更を優先。既存成果の再試験・再実験を完了条件にしない。
3. 特定の過去証拠の所在・完全性を検証する必要がある場合のみ、元の`kyoto_resume_gate.py`を**元の適切なデータ・アーティファクトとともに**利用。期限切れの旧GitHub Artifactを再取得不能という理由だけで新規データ取得や再研究を指示しない。
4. 失敗が発生したら既存ログから原因と影響範囲を特定し、同じ根本原因を既存コード内で探索して**一度の最小修正**を行う。テストは変更した境界・関連退行だけ。過去の実験そのもののやり直しは不可。
5. 結果には「既済証拠／今回変更したもの／今回だけ検証した差分／実開催未実証」を分離して表示。ステータスバーの定義・分母は変更しない。
6. GitHub・Turso・Secretsへの操作は最小限。診断のために本番共有予約を有効化しない。認証情報のスクリーンショット・チャット貼付を求めない。
7. 11月21・22日の発走前原本・馬連／枠連オッズ取得を最優先。PC/SPハイブリッド、8枠、暗号化、既存Turso保護を維持。

## 2026-11-19時点の未完了境界（歴史的スナップショット）

- 検証済み：隔離TursoでのGitHub Actions／Streamlit共有予約・競合回避、Hrana NULL修正、G06内の重複取得防止・復旧試験。
- 本番main：11月21・22日8枠に実装23取得器がピン留め済み。**共有予約自体は無効**。新規本番Tursoホスト・URL・トークンは未設定（Run `44460603005`の実ログで確認）。
- 既存Turso `kyoto-keiba-ai-test` の `__kyoto_ai_weekend_claims_isolated_lab_v1` は**隔離実験用**。構造・レコードの再調査、既存実験のやり直し、本番予約テーブルへの流用禁止。
- 未完了：本番専用予約領域・権限の決定、取得経路での実接続・予約／競合実証、新開催の発走前実データ取得。
- 本ファイルはHEADの固定宣言ではない。毎回現在のGitHubを確認する。

## 自動化された変更入口

`.github/workflows/kyoto-existing-work-reuse-review.yml` は **main向けPR** に限り、既存`kyoto_development_preflight.py`を開発ブランチの正本で実行し、PRに変更分類・既存証拠・本当に新しい境界の明記を要求する。**再研究ではなく、既存の静的な証拠・関数照合である。** このチェックだけではブランチ保護を設定したことにはならず、実際の本番取得成功も意味しない。

この入口の設置は過去の機構の置換ではない。既存の機構がmainで無視されていた接続不備の修正である。

## 2026-11-19 補訂・確定引継ぎ｜Turso test DBと本番共有予約（実装23）

### A. なぜこの記録が必要か
2026-11-19の実装23では、過去に成功したTurso共有予約実験について、管理画面を開いてテーブル構造・データを再確認する作業が発生した。**過去成功実験を再実施せず、保存済み証拠を引用する**という2026-11-06・09・13の固定指示に反する非効率だった。次チャットは既存の成果を「未発見」「未実装」と扱わない。ユーザーに同じ管理画面操作を頼まない。

### B. 画面で確認済みの実験用Tursoの事実（2026-11-19）
- Turso組織：`papaneko-ai`。管理画面に表示されたDB：`kyoto-keiba-ai-test`、Active、group `default`。画面上では1 DBが一覧に表示されたが、**アカウントの全本番データ保存先を確定したわけではない**。
- 接続先（公開可能な識別用ホスト）：`kyoto-keiba-ai-test-papaneko-ai.aws-ap-northeast-1.turso.io`。これは過去に実験用途として識別したホストであり、本番用に設定しない。
- 既存の実験予約テーブル：`__kyoto_ai_weekend_claims_isolated_lab_v1`。STRUCTURE画面で `claim_key`／`owner`／`generation`／`expires_at`／`state`／`receipt_sha256` の6列を確認。
- DATA画面で既存7レコードが表示され、`LEASED` 6件・`DONE` 1件、完了レコードのハッシュ欄あり。ただし**画面だけで複数ホスト競合制御の完全な独立証明としない**。成功の根拠は既存のActions／Streamlit実験ログで再照合する。
- 本番コードが参照する予定のテーブル名は `__kyoto_ai_weekend_claims_v1`。上記の実験テーブルとは**別名・別用途**。
- 上記は2026-11-19の画面観察と既存の実験実績。新しいDB作成・改名・移行・権限設定・本番稼働の証拠ではない。

### C. 決定済みの方針とその理由
1. **`kyoto-keiba-ai-test` を改名しない。** `test` は実験DBであることを示す妥当な識別子。名称だけ `prod` に変えてもデータ・権限・隔離性は本番仕様にならず、旧実験ログ・URL・接続設定との照合を難しくする。
2. **既存実験DBと `__kyoto_ai_weekend_claims_isolated_lab_v1` は保全。** 改名・削除・上書き・本番への安易な転用をしない。既存成果を再現するだけの実験も行わない。
3. **本番で使う予約領域は実験から分離する。** 本番向け名称候補 `kyoto-keiba-ai-prod` は、あくまで新設の場合の**候補**。現時点で作成済みでも決定済みでもない。
4. **本番専用DBを作るか、既存の適切な本番DBの独立テーブルを使うかは未決定。** 実際の本番保存先、権限、無料枠、変更影響、バックアップを調べて比較し、不要な新設・設定変更をしない。「実験用DBに本番テーブルを作って同じ認証を使う」案を、分離の検証なしに採用しない。
5. **既済実験を再利用して未完了の本番境界のみ解決する。** 検証済みの共有予約コード・競合回避実験・Hrana NULL対策を再利用する。新しい検証が必要なのは選定した本番接続先でのスキーマ・書込権限・取得器との接続・実予約排他など、本番固有で未実証の事項だけ。
6. **ユーザーの手間を原則ゼロにする。** GitHub APIで既存HEAD・Actions run/job/log・Secretsの「名前の存在」等の確認が可能なら、アシスタント側で実施する。機密トークンを貼らせない。ユーザー操作は外部管理画面の本人認証・新たな秘密情報の登録・明示的な本番変更承認など不可避なものに限定し、一度に最小の手順だけ示す。

### D. 直近の証拠と重要な未完了事項
- GitHub実装23の本番観測Workflow：`.github/workflows/kyoto-20261121-22-two-source-production-observer.yml`。2026-11-19時点で11月21・22日の8枠を維持。collector pin `ba6b62bdbb25abf5605ea3b2b2ecb7f288b1d320`。**共有予約の機能は統合済みでも、productionの有効化は未完了**。
- 手動読み取り専用診断 Actions Run [44460603005](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/44460603005)：`READ_ONLY_CONFIGURATION_INCOMPLETE_NO_REMOTE_IO`、`remote_schema_verified=false`、`remote_write_verified=false`、`production_claim_certified=false`。未設定項目名：`KYOTO_SHARED_CLAIM_APPROVED_PRODUCTION_HOST`、`KYOTO_SHARED_CLAIM_TURSO_URL`、`KYOTO_SHARED_CLAIM_TURSO_TOKEN`。このRunは**本番Turso接続成功の証拠ではない**。
- `KYOTO_SHARED_CLAIM_ACTIVATE` と `KYOTO_SHARED_CLAIM_PRODUCTION_APPROVED` は本番への切替条件であり、接続診断を目的に推測・変更しない。Turso Secretsや本番予約テーブル作成は明示的な対象・影響確認を伴う。
- 既存機能の重複防止機構は再構築しない。開発ブランチの `KYOTO_AI_START_HERE.md`、25領域台帳 `docs/diagnostics/kyoto_feature_reuse_inventory_v1.json`、`diagnostics/kyoto_development_preflight.py` を利用。
- 2026-11-19の再開入口修復は [PR #12](https://github.com/papaneko-ai/kyoto-keiba-ai/pull/12) によりmainへ反映済み（`0af82ee6d2bca2ffcdf45d469e3590fc0b022850`）。CIチェックの存在と、すべての実作業で自動的に重複が防がれることは同義ではない。

### E. 次チャットの作業開始点（やり直し禁止）
1. アシスタントがmain・開発ブランチの**現在HEAD**、上記Runと最新の関連Actions／バックアップ、現行の保存先情報を取得し、既存根拠を確定する。古いSHAを最新と決めつけない。
2. 既存の実験DBを触らず、本番共有予約が使うべきDBの既存候補・権限・コスト・必要な名前だけを比較し、**採用先を確定する**。確認結果が不足すれば、その不足を限定して示す。旧実験の構造・7件の確認を繰り返さない。
3. 新たな接続先の設定が必要な場合に限り、ユーザーへ不可避な最小手順を提示。Secretsの値をチャットに表示させない。実データ取得機会と競合する不要な変更を行わない。
4. 既存ロジックを再利用し、**本番固有の未実証部分だけ**を検証。11月21・22日の発走前出馬表・馬連／枠連オッズの原本・SHA256・UTC保存を最優先。PC/SPと補助情報源・8枠を維持する。
5. 新たな調査・試験・資料作成の前に、**「何がすでに証明済みで、今回初めて何を確認するか」**を1行で定義。これが説明できない作業は着手しない。

**2026-11-19時点の状態：名前・分離方針のみ確定。本番DB名／作成／移行／Secrets登録／予約機能有効化／実開催での成功は未完了。過去実験の再実施は不要。**
