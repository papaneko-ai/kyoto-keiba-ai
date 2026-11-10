# 京都競馬AI｜P1-03 PC/SP統合・研究開発73％節目／完全継続復旧記録（2026-11-10）

## 正本・実行対象
- GitHub: `papaneko-ai/kyoto-keiba-ai`、開発ブランチ `jra-html-diagnostic-20261105`。新規設計・ゼロからのやり直し禁止。
- 再開時は `KYOTO_AI_START_HERE.md`、本記録、`docs/KYOTO_AI_20261110_P4_TEMPORAL_66PCT_MILESTONE.md`、`docs/KYOTO_AI_20261110_RG06_RESEARCH_GRADUATION_100PCT_MILESTONE.md`、固定採点ルーブリック2種類、証拠台帳、GitHub最新HEAD/Actionsと保存済みP1原本のArtifact `13482994623` を確認する。

## 固定基準による進捗
- **研究・開発工程認定73/100**、固定32条件中23合格。前回66/100・22/32から**+7ポイント、+1条件**。追加はルーブリック既存P1-03（固定7点）。採点基準・配点を変更していない。
- **研究段階卒業100％**、12/12、研究統合6/6。前回から変化なし。
- **実競馬接続の独立検証0/6、独立検証済み実用能力の下限0/100**。研究用検証を実開催の実績に転用しない。
- P1-03の合格は**注入された模擬通信を使ったPC/SP切替機構**の研究開発認定。実開催の公式JRA発走前原本自動取得の成功、許諾、公式原本の真正性、公式発売・取消、事前予測・仮想投資実績を認定したものではない。これらは未証明のまま。

## 今回の実装
- `diagnostics/p1_authorized_pc_sp_fallback.py` を追加。既存の `diagnostics/jra_pc_sp_benchmark.py` の `reconcile_saved_racecards`（PC/SP parser、馬番・枠番・馬名の照合）を再利用。
- 明示した取得先URLの厳格検査、発走前UTC、独立凍結名簿、PC版最優先・成功時SPは呼ばない・失敗時のみSPという上限2リクエスト構造。
- 取得元・リダイレクト・未来の取得時刻・不正バイト・名簿差異・両経路の失敗を拒否。成功時は原本バイトとSHA256、試行履歴・選択経路を戻すが、公式由来を独立認証したとは主張しない。
- `tests/test_p1_authorized_pc_sp_fallback.py` に15件の正常・異常・再現性テスト。**実ネットワーク要求はない**。実用認定と混同しない。

## GitHub Actions実測証拠
- 研究統合15件・全CI成功: run `42764699297`, job `129658319930`, SHA `363cf093d15ad2996d09297c5f500a9d8f8d722f`。15 tests success、固定進捗はこの時点で66％。
- 固定進捗証拠台帳 `docs/diagnostics/kyoto_progress_evidence_v1.json` に既存のP1-03を追加。成功run/job/SHAと実装・テストのパスを固定。
- 再採点成功: run `42764842513`, job `129658786151`, SHA `d7314748f903979be8a43db97f9c2a48e302aa88`、ログ `KYOTO_PROGRESS_VERIFIED=73%`、`KYOTO_RESEARCH_GRADUATION=100.0%`、`KYOTO_OPERATIONAL_VERIFIED=0/100`、`KYOTO_RESEARCH_TO_LIVE_VERIFIED=0/6`。
- 本書追加時に復旧ワークフロー `.github/workflows/kyoto-ai-milestone-recovery-archive.yml` が発火する。同一SHAで継続CI success、source ZIP/SHA256SUMS/manifestのArtifact保存を**必ず確認後**に報告する。これらが未確認なら完成とは呼ばない。
- 既存66％バックアップ: run `42764492023`、Artifact `13739705143`、保存SHA `13b9e8a6e2018f76d4ddf6b022cb433b80254b3b`。旧バックアップを変更しない。

## 次の優先開発
- 新開催日の許諾を確認できる真正な発走前PC/SP原本（出馬表・馬連・枠連オッズ）と、発売状態・取消・UTCタイムスタンプを独立証明する。取得成功を架空のmockや過去レースで代替しない。
- P1-04、P4-02、P3-02、P5-02/03、P6-02/03、P8-02/03/04等の未達条件を、既存のP1解析・PC/SP切替・P3研究モデル・P4価格鮮度検査・P5配分・P6仮想台帳・P7独立進化に接続。受け渡し不整合があれば停止。
- ALG-01～13、EVO-01～08、工程P1～P8、馬連枠連、上限予算・見送り、2～3R/2点の原則、未使用時系列、モデル悪化時復帰、スマホ軽量化・追加費用原則0円を維持。
- main、Turso、Secrets、旧公開アプリ、実購入機能・公開モデルは無断変更しない。

## 新しいチャットでの継続指示
「既存 `papaneko-ai/kyoto-keiba-ai` の開発ブランチ `jra-html-diagnostic-20261105` を継続し、本73％節目パックと`KYOTO_AI_START_HERE.md`、固定ルーブリック・証拠・原本/バックアップ・最新GitHub HEADを照合。研究開発73％(23/32)、研究卒業100％(12/12)、実開催接続0/6、独立実用能力下限0/100を混同しない。既存のP1-03 PC/SP切替を使い、真正・許諾された実開催発走前データと市場の統合を優先。成功CIと同一SHAの復旧ZIPを保存し、得点差分理由を報告する。main/Turso/Secrets/旧アプリ/実購入の無断変更禁止。」
