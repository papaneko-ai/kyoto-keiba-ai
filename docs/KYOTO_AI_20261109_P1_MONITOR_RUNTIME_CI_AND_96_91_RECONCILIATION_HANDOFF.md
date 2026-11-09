# 京都競馬AI｜P1診断画面の実行検証ゲートと履歴数値整合性修正（2026-11-09）

## 実装開始状態
- 直前開発HEAD: `353fffe9eee7427109c425f74cfc0b58692d14c0`。比較でHEAD一致、想定外差分なし。
- 保存済み事実: 2026-11-07京都12R・148頭・プロフィール96頭・残52頭・有効過去走592件。公式取得証拠の再GETは実行しない。旧154件CIは別のオフライン受入履歴。
- 本番main HEAD: `471b60e632d878b52b6dcb4aa1a622becba40882`（作業前照合）。Turso/Secrets/実購入台帳にはアクセスしない。

## 発見した問題と根本的な対処
旧診断画面は `status.json` に記録されたプロフィール96頭を表示するが、全馬完了とされる1～8Rの内訳 `9+15+13+15+8+11+11+9=91` 頭との関係を説明しなかった。この差5頭の所属レースは現状の完了レース集計だけからは認定できない。

- `diagnostics/p1_monitor_viewmodel.py`：画面に先立ち、実status.jsonの版、148=96+52、日時、P1未完成フラグ、未実証グループ、1～8Rの人数などを検証。差5頭を `verified_not_allocated_to_completed_races` として表示する。誤ったレースへ自動割当せず、誤解を避ける。
- `diagnostics/p1_readonly_monitor_app.py`：既存の履歴画面を上記viewmodelに接続。無効なstatusは画面停止し、未割当5頭を注記。発走前の予測可能と示さない。
- `tests/test_p1_monitor_viewmodel.py`：GitHubに保存された**実際のstatus.json**に対して合計11件の正常・負例テストを定義。96/91/5を確認し、旧12頭値や危険な予測可能フラグへの回帰を拒否。
- `.github/workflows/jra-p1-readonly-monitor-acceptance.yml`：Python構文、11件の検査、Streamlit AppTestでのUI実行、127.0.0.1:8501のHTTPヘルス確認、モニターに実JRA収集処理がないことを確認する独立CIを追加。実通信のJRA GETは実行しない。

## 確認したこと・未確認のこと
- GitHub connectorで上記ファイルの保存と直前HEADを確認した。
- この実行環境では `git ls-remote` に失敗（github.comのDNS解決不可）、`import streamlit` も失敗（インストールなし）。従って**Streamlit実起動成功、画面目視、11件のクラウドテスト合格を宣言できない**。
- 現在のGitHub connectorのcommit checksは空、commit workflow runs取得も空。これは成功の証拠でも失敗の証拠でもない。CI run ID、job ID、ログが取れるまで未確認。
- UIは旧開催の可視化に限る。馬番/出走馬ID・発走前市場オッズ・現開催の原本取得を実証したものではない。
- JRA一般HTMLの自動取得・保存利用条件、分散ホストでの重複回避は未完、実HTTPは無効。

## 次に進む条件
1. GitHub Actions上で上記新ワークフローのrun/job/logを取得し、11件テスト・AppTest・HTTP healthの成否を確認。失敗なら同じ根本原因を検索し修正。
2. 診断アプリを本番から独立して公開するときはユーザー承認のうえでStreamlit設定を行う。main/app.pyは変更しない。
3. JRA利用条件と事前取得の許容範囲を確認し、次回未発走の公式出馬表・馬ID・馬場・発走時刻・馬連/枠連オッズをUTC/SHAとともに保存して予測の入力にする。現歴史データは逆流禁止。
4. 実践投入への縦断ルート（P1→最小P3/P4/P5→P6の凍結・公式採点）を優先し、EVO/ALGの削除・工程改変を行わない。

## 受入判定
**実在する公式取得状況の説明不備を修正し、実画面起動を検証するCIを追加した実装節目は完了。CI実行・本番クラウド起動・実レース予測は未検証。P1-FB第5段階は未完了。** P1～P8、ALG-01～13、EVO-01～08、P6仮想、EVO-07独立監査、EVO-08発見を維持。
