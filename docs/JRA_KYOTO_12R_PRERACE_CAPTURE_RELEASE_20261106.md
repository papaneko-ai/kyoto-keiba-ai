# 京都競馬AI｜全12レース発走前データ取得・独立検証：大工程完了（2026-11-06）

## 1. 検証済みの到達点
**2026年11月7日開催・京都1R～12R、148頭、過去走日付396件**について、2026年11月6日の時点でJRA公式の出馬表を取得し、馬番・枠番・馬名・競走馬プロフィールへの遷移情報・過去走日付を構造化して、診断用ブランチに固定した。

レースごとの出走馬数：1R=9、2R=15、3R=13、4R=15、5R=8、6R=11、7R=11、8R=9、9R=10、10R=14、11R=16、12R=17（計148）。
過去走日付：1R=14、2R=30、3R=22、4R=22、5R=0、6R=0、7R=44、8R=36、9R=40、10R=56、11R=64、12R=68（計396）。新馬戦の過去走0件は正常で、架空データは生成しない。

取得にはJRA公式の個別出馬表URLを使用。最初の1・6・7・12Rは個別URL、残る8レースは保存済みの京都7R公式HTMLに実際に含まれた12レース分の `/JRADB/accessD.html?CNAME=...` から抽出。**CNAMEの末尾を推測して組み立てていない。**

各原本に取得時刻・サイズ・SHA-256を付与。原本HTMLはGitHub Actionsの短期Artifact（保存3日）に保持し、一般公開リポジトリには原本を掲載しない。構造化JSONとレシートのみを保存。

## 2. 独立検証
GitHub Actions Run ID **42157811739**：残る8レースの収集・解析・保存 **success**。
GitHub Actions Run ID **42157892914**：保存済み12レースの独立オフライン検証 **success**。
判定証拠：`docs/diagnostics/JRA_KYOTO_FULL_DAY_ACCEPTANCE_20261106.json`（race_count=12, runner_count=148, prior_date_count=396, test_outcome=success）。検証対象は構造化JSONであり、**CIが原本HTMLバイトを独立ダウンロードして突合したことまでは証明していない**。

保存先：
- 1/6/12R：`docs/diagnostics/multirace_20261106/kyoto_{01,06,12}_snapshot.json`
- 7R：`docs/diagnostics/JRA_KYOTO_R7_PRERACE_FROZEN_20261106.json`
- 2/3/4/5/8/9/10/11R：`docs/diagnostics/remaining8_20261106/kyoto_{NN}_snapshot.json`
- 日次合格記録：`docs/diagnostics/JRA_KYOTO_FULL_DAY_ACCEPTANCE_20261106.json`
- 公式リンクの抽出原本から得た一覧：`docs/diagnostics/JRA_LIVE_NAV_DISCOVERY_20261106.json`
- 対応コード：`diagnostics/jra_multi_capture_20261106.py`, `diagnostics/jra_remaining_8_20261106.py`
- 日次再検査：`tests/test_jra_full_day_20261107.py`

## 3. インシデントと根本原因への対処
最初の8レース一括実行 Run ID **42157423013** は `ModuleNotFoundError: No module named 'diagnostics'` で、**JRAアクセス開始前に失敗**。GitHub ActionsのPython実行時に、プロジェクトルートのimportパスが渡されていなかった。ワークフローの実行を `PYTHONPATH=. python ...` に修正し、再実行で全8レース成功。ユーザーに不要な再取得を繰り返させないため、以後の実行環境・importパスをCIに明記する。

## 4. 過去レースの「隠しページ」に関する確認
2026-11-05のJRA公式保存原本 `entries.html` には、出馬表開催選択向け `doAction('/JRADB/accessD.html','pw01dli00/F3')` は存在するが、当時のレース別発走前出馬表の原本ではない。一方、`kyoto_all_results_20261031.html` には、実際に使われた過去の確定結果・最終オッズへ進む `doAction` とCNAMEが存在する。**過去の出走表が現在も必ず取得できる「隠しURL」が存在する、とまでは未実証**。2026-10-31の最終オッズを当時の発走前オッズとして利用しない。

## 5. 運用上の未完了
- 取得を特定日だけでなく各開催日・各場に展開するイベント主導のスケジューラは未実装。
- 出走取消・出走除外、レース当日の馬場情報、発走前馬連・枠連オッズのタイムスタンプ付き保存は未実装。
- `CNAME` は画面遷移トークンであり、競走馬の恒久IDとしては未承認。
- 原本HTML短期保存の長期保全方法（権利・利用条件を含む）の整備は未完了。
- 本番アプリの予測、勝利条件発見、仮想投資、自動採点、モデル進化・比較・復帰は未着手・未検証の部分が残る。**学習・予測への自動投入はしない。**

## 6. 変更保護
公開`main/app.py`、Turso本番、既存モデルは未変更。GitHubの診断用ブランチだけで実験した。追加のAPI課金なし。JRA公式を主軸に補助情報源を使う方針と、原本の時点証明・データリーク防止を維持する。

**正式な今回の区切り：2026-11-07京都全12レース148頭の発走前実データを初めて取得・固定し、独立CI successを確認した。**
