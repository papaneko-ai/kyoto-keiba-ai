# 京都競馬AI｜2026-11-11 P3-02全市場研究比較98％認定・完全復旧パック

## 0. 事実の結論・大きな節目達成
- リポジトリ：`papaneko-ai/kyoto-keiba-ai`、開発ブランチ：`jra-html-diagnostic-20261105`。本番`main/app.py`、Turso、Secrets、実購入機能を保護。
- **研究・開発工程認定率 94％ → 98％（+4ポイント）**。固定32条件で30/32 → **31/32**。研究段階卒業 **100％（12/12）**。別指標の実開催接続 **0/6**、独立検証済み実用能力下限 **0/100** は変わらない。固定ルーブリック `docs/diagnostics/kyoto_progress_rubric_v1.json` の内容・配点・分母は一切変更していない。
- ユーザー指定：**「次の大きな節目」とは直前にCI・復旧が確定した研究・開発工程認定率より増加すること。次回からは今回98％超が次の節目条件。**
- 最新の残り固定条件：P8-04「公開環境の動作・復元・費用検証」 **1項目・2ポイント**。本書でP8-04を認定しない。

## 1. P3-02が4点認定された具体的根拠と研究スコープ
- 固定ルーブリックのP3-02は「実データで市場とモデルの同条件比較」（配点4）で、acceptance条文は**「指定範囲の実データまたは研究用テストで実証しGitHub Actionsのrun/job/SHAで再現可能にする。研究用は実用済みと混同しない」**。P3-02はこの明文が認める**研究用テストでの機能認定**として記録した。実開催の現場採用・モデル精度・回収率の認定ではない。
- 以前の `diagnostics/p3_same_cutoff_market_model_bridge.py` と `tests/test_p3_same_cutoff_market_model_bridge.py` は研究モデル2頭・馬連1組の接続を確認済み。ただし全市場での同一性とモデル交換を検証していなかったため当時のP3-02採点は未達で保持した。
- 新規 `tests/test_p3_full_16_runner_same_cutoff_research.py` を実装。**架空の16頭と3つの独立した研究用HTML bytes**を生成。研究用馬連15段の全120組、枠連8段の全36組（同枠を含む）、全レース原本ハッシュ/取得時刻/モデル特徴量SHAを既存パーサ `diagnostics/jra_odds_matrix_parser.py` と P1三原本監査経由で比較する。
- 新旧2モデルの凍結時刻・共通cutoff・特徴量SHA・出走馬集合を一致させ、**全156ペアの期待値と下振れ期待値差分**を検証。モデル交換で符号が反転、原本は同じ、価格改変/同枠改変、16頭中1頭のモデル欠落、偽事前モデル/未来凍結、特徴量相違、発売停止、歴史的最終オッズ混入をfail-closedで拒否。
- 新規13件の研究用破壊・回帰テスト。**全体CI success** run **42938728752** / job **130255118264** / SHA `16fa5ff7e688a4d12565a9dd252e58a1d9e862c4`。runログに`test_16_horses_full120_and36_market_comparison ... ok`。
- P3-02の証拠を `docs/diagnostics/kyoto_progress_evidence_v1.json` に`kind=HISTORICAL_OR_RESEARCH_SCOPE_ONLY`で追加、**固定採点CI success** run **42938981440** / job **130255950762** / SHA `5d1f457ffc700806a1148b26c86c3b630446ffeb`、ログ `KYOTO_PROGRESS_VERIFIED=98%`、`KYOTO_PROGRESS_DELTA=4`、`KYOTO_PROGRESS_REMAINING=1`、`KYOTO_RESEARCH_GRADUATION=100.0%`、`KYOTO_RESEARCH_TO_LIVE_VERIFIED=0/6`、`KYOTO_OPERATIONAL_VERIFIED=0/100` を実測。

## 2. 実際の新開催日の予測とは明確に分離
- 今回の16頭市場・3原本は**合成した研究用データ**。実際のJRA公式現行出馬表／発走前市場／公式発売・取消情報に由来すると主張しない。
- 新旧モデルの比較コードの確率は未較正研究用。**データを独立認証した本物の採用モデルによる未使用開催日の勝率・回収率の測定には使っていない。**
- 実開催データの使用と真の運用実証は別の6領域・100点の独立実用検証で管理し、現時点ではそれぞれ0/6・0/100。過去JRA最終オッズを未来の発走前オッズに代用禁止。
- 既存JRA原本保全Artifact `13482994623`、84頭原本・485過去走・335特徴量、11月7日全12R148頭の出馬表、PC/SPの公式未公開・未取得状態を再取得せず保持。

## 3. 残り2点と具体的な次アクション
- **P8-04だけ残る（2点）**。「公開環境の動作・復元・費用検証」。ローカルChromiumとCloud URLの存在だけでは独立したCloud管理画面での公開成功・再起動成功・費用確認に不足するため未認定。
- 既存旧Cloud診断URL `https://kyoto-ai-cloud-probe.streamlit.app` への外部読み取り検査は2エンドポイントともHTTPError。新P8シャドーを旧Cloudアプリと混同せず `diagnostics/p8_uploaded_archive_shadow_app.py` の新規別アプリをユーザーのCommunity Cloud管理下に配置する必要がある。
- 新アプリの設定：repository `papaneko-ai/kyoto-keiba-ai`、branch `jra-html-diagnostic-20261105`、main file `diagnostics/p8_uploaded_archive_shadow_app.py`、Python 3.11、Secrets不要。新アプリURLで `.github/workflows/kyoto-ai-p8-remote-release-verification.yml` の手動検証を行いSHA一致/スマホ幅/無購入を証拠化。管理画面での**実際のReboot前後**と無料プラン・課金実績の証跡を別途確認し、P8-04の固定ルーブリックで独立判定する。
- Cloudへこちらから接続済みの管理権限はない。公開成功を推測したり、勝手に`main`、Secrets、Turso、旧公開アプリ、実購入環境を変更しない。

## 4. GitHub版の再開・復旧
- 現行入口 `KYOTO_AI_START_HERE.md` と固定rubric/evidenceを必読。最新HEAD・全体CI・復旧Artifact・branchの同じSHAの一致を確認。
- この文書をGitHubにpushすると、`.github/workflows/kyoto-ai-milestone-recovery-archive.yml` が**ソースZIP・SHA256SUMS・RECOVERY_MANIFEST**を同一SHAでArtifact化する。ジョブsuccessと同じSHAの継続CI successを検証後に節目の復旧完了とする。
- 今回のバックアップ専用branch名は `backup/kyoto-ai-development-98pct-20261111`（同一SHA固定）。元の94％ブランチと復旧Artifactも削除しない。
- **指示された進捗報告形式**は必ず「研究・開発工程認定率98％・横長の緑バー・前回94％/＋4ポイント」の直後に**管理指標／前回／今回／増減の4列5行**（研究開発率、32項目合格数、研究卒業率、実開催接続、実用能力下限）を表示。別フォーマットに替えない。
