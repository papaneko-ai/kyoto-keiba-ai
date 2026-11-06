# 京都競馬AI｜P1公式データ実験：京都1R～3Rの全頭詳細プロフィール取得完了（2026-11-06）

## 本書の役割
この文書は**2026-11-06の最新進捗の正本**。過去のログを上書きせず新しい節目のレシートとして保存する。
アルゴリズム：`docs/KYOTO_AI_ALGORITHM_REQUIREMENTS_REGISTER_v1_20261106.md`。
工程順：`docs/KYOTO_AI_ALGORITHM_AND_EXECUTION_ROADMAP_20261106.md`。
セクション移行規則：`docs/KYOTO_AI_CONTINUITY_AND_STAGE_GATE_RULES_20261106.md`。

## 実データによる検証値
- 対象：2026-11-07京都公式出馬表12レース148頭
- 公式の詳細プロフィールHTMLを取得し、原本SHA・馬名・馬番・UTCを照合して構造化：**48頭**
- 完全に詳細取得したレース：京都1R **9/9頭**、2R **15/15頭**、3R **13/13頭**
- 詳細プロフィールを未取得：**100頭**
- 有効な着順がある過去走：**172件**（前回153件＋19件）
- 事前に別扱いした除外1件、新馬の過去走0件2頭、障害競走の芝ダコース分類は維持
- 完了バッチ：**batch_01～batch_06**、各6頭、例外処理も別記録。今回追加したbatch05/06は12頭中成功12頭・失敗0件
- 次の正確な再開地点：**batch_07**（最新の148頭台帳には未取得100頭を区別して保存）

## 検証根拠
- 最新の機械判定：`docs/diagnostics/jra_p1_three_complete_races_20261106/status.json`
- 最新全148頭特徴量台帳：`docs/diagnostics/jra_p1_three_complete_races_20261106/feature_rows_148.json`
- 第5バッチの個別取得・原本レシート：`docs/diagnostics/jra_p1_profile_batches_20261106/batch_05_receipt.json`
- 第6バッチの個別取得・原本レシート：`docs/diagnostics/jra_p1_profile_batches_20261106/batch_06_receipt.json`
- 第5・第6バッチの原本SHA照合・過去走再解析：`docs/diagnostics/jra_p1_profile_batches_20261106/replayed_batch_05/`、`replayed_batch_06/`
- GitHub Actions `42167231089` 第5バッチ実取得：SUCCESS
- GitHub Actions `42167318860` 第5バッチ独立原本再解析：SUCCESS
- GitHub Actions `42167373275` 第6バッチ実取得：SUCCESS
- GitHub Actions `42167483288` 第6バッチ独立原本再解析：SUCCESS
- GitHub Actions `42167538569` 3レース完全取得の統合受入試験：SUCCESS

## 次の確定作業
引き続き **P1 予測に必要な実データ取得と欠落管理**を進める。新しいセクションではまず最新 status の `next_batch=batch_07`、`profile_details_source_verified=48`、`detailed_profiles_unqueried=100` を確認する。実取得済みの1～6バッチは再取得しない。次の対象は固定計画 `docs/diagnostics/JRA_PENDING_136_PROFILES_PLAN_20261106.json` の batch_07。

重要：3レースのプロフィールがそろったことは予測用の全条件がそろったことを意味しない。騎手・調教・当日馬場・取消・発走前オッズ、公式原本HTMLの恒久保管、利用条件の確認などは未完了。**予測・学習可能と認証しない**。

## 正本保護
- 統計的勝ち馬特徴自動発見、複数モデル比較（ベンター型・Harville・Plackett–Luce・Bolton–Chapman型など）、Brier・対数損失・較正、馬連枠連の期待値、予算最適化、発走前凍結仮想投資、自動採点、改善採用ゲートを省略しない。
- 本番 `main/app.py`、Turso、本番モデル、実購入台帳は変更しない。趣味開発を業務用Work/Codexと分離。原則追加費用0円。
- 途中の失敗はログに残し、成功した独立再検証を完了の根拠とする。
