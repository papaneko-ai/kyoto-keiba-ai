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
