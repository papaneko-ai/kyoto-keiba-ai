# 京都競馬AI｜2026-11-09 P1-FB第5段階 共通予約台帳・オフライン統合節目

**確定判定：P1-FB Stage5の「単一永続SQLiteを共有する複数処理間の重複遮断と模擬PC/SP切替」サブゲートPASS。JRA実通信・正式PC/SP切替・本番採用は未PASS。**

## 1. 成果の証拠
- GitHub Actions **run 42546465445 / job 128932427036**：成功。19+10+14+8+17+16+11+15=**110テスト**全部成功。Pythonコンパイル、`OFFLINE_ONLY_GATE_PASSED`。公式JRA追加GETは**0件**。
- 直前の同構造統合テスト：CI 42546399466、109テストsuccess。最後の1件は**独立4プロセスによる同一URLの競合テスト**で、同じSQLiteに接続した処理のうち1件だけ予約成功することを検証。
- 受入記録：`docs/diagnostics/jra_p1_fb_stage5_shared_ledger_gate_20261109.json`。第5段階の前回88件のゲートは`docs/diagnostics/jra_p1_fb_stage5_20261109_acceptance.json`。成功済み成果を再取得していない。

## 2. 実装した機能
- `diagnostics/jra_p1_fb_stage5_global_attempt_registry.py`：
  - SQLiteの`BEGIN IMMEDIATE`トランザクション、一意URL制約、同一馬/同一PC・SPチャネルの重複防止、全通信予算上限、UTC逆行と2秒未満の予約遮断、カットオフ超過拒否を実装。
  - URL予約は取り消さず、クラッシュ・HTTP障害で未完の`RESERVED`が残っても**再取得禁止**。`RECEIPT_RECORDED`への更新と全記録の照合が可能。
  - 永続性に`PRAGMA synchronous=FULL`とWALを利用。故障時はfail-closed。利用側の永続ストレージの構成・バックアップが別途必要。
- `diagnostics/jra_p1_fb_stage5_ledger_replay.py`：
  - `run_guarded_replay`と共通予約台帳を接続し、**模擬通信の前に必ずURLを予約**。PCが失敗してSPへ切替える模擬経路でも、両URLを別個に予約し原本・障害receiptを保存。
  - グローバル予約が拒否された場合は、元の障害receiptを書いた後に直ちに例外を伝搬。これを一般的HTTP障害と誤認して**代替URLへ進むことは禁止**。
  - 終了後に予約IDへ採点済みの状態を付記。記録更新不能時は未完`RESERVED`として残り再取得しない。
- 第4段階`diagnostics/jra_p1_fb_stage4_mock_adapter.py`と第5段階`diagnostics/jra_p1_fb_stage5_guarded_replay.py`に後方互換の`fatal_transport_exceptions`を追加。
- `tests/test_jra_p1_fb_stage5_global_attempt_registry.py`（14件）と`tests/test_jra_p1_fb_stage5_ledger_replay.py`（8件）を新設。既存のstage4/stage5/SP/双方向判定の全回帰も成功。
- 既存の**公式出馬表由来PCリンクの同定のみ**証明済み。SPリンクをPCのCNAME等から合成しない。

## 3. 厳守すべき適用範囲
- **この台帳は同一の永続SQLiteパスに接続する処理間だけで共有できる。** 別のGitHub Actions runner、Streamlitインスタンス、独立端末間のURL二重予約を、単一ローカルSQLiteでは防げない。別ホストへの展開時は原子的に共有できる永続台帳の検証が必須。
- **テストにおける2秒の間隔は論理時刻を使った模擬検証であり、実際のネットワーク通信間隔を検証したわけではない。** 実際のHTTPアダプターは別に設計して、時刻・上限・利用条件・発走前期限を実証する必要がある。
- `offline_replay_only`は本番のセキュリティ機構ではない。模擬通信以外で利用を許可しない。本番`main/app.py`／Turso／公開アプリに未導入、公式自動切替は未認可。
- 過去の2026-11-07京都12R148頭・プロフィール96頭・過去走592件は保存済み。残52頭を11/09に取得して発走前原本と偽らない。将来の新開催に独立した公式時点と原本が必要。

## 4. 次の大きな目標と作業順
1. P1-FB第5段階の**実通信安全ゲート**：ネットワーク通信の許可条件を明確化し、公式PC/SPの実在の対応リンクをそれぞれ根拠原本で検証。
2. 同時に、Streamlit / GitHub Actionsなど異なる実行環境間で**予約台帳を単一の共有永続ストアに配置できるか**、追加費用0・Turso本番保護を前提に実証。未証明なら同時アクセスは無効。
3. 過去の保存済み公式原本でPC/SPの異常履歴・転入転出・枠馬IDの正規化を再検査。新しい未発走開催の情報入手が可能になった場合だけ発走前証拠を新規取得。法的/利用条件の確認が未了の場合は自動GETを開始しない。
4. 上記安全ゲートを通過したときだけ段階的なP1データ取得へ移り、その後P2～P8の工程順を維持。P6仮想投資と公式払戻、P7のEVO-07独立進化監査、EVO-08閃きを含むALG-01～13/EVO-01～08を削除しない。
5. 実践投入優先。仕組みの複雑化が遅延要因になる場合、PC安全単一路線による限定実証を検討しつつ、PC/SP双方向要件は将来完了まで台帳に残す。工程自体を無断変更しない。

## 5. チャット移行・保護条件
- **本書＋CI 42546465445＋`docs/diagnostics/jra_p1_fb_stage5_shared_ledger_gate_20261109.json`が新しい正本。** 過去の88件レシートは破棄せず履歴として保存。
- 次回開始位置：**P1-FB Stage5の未通過実通信／異ホスト共有台帳／公式SPリンクのゲート**。Stage5本番完成・予測ready・学習readyを誤って宣言しない。
- GitHub開発ブランチ`jra-html-diagnostic-20261105`。旧公開アプリは参考にしない。本番`main/app.py`と本番Tursoを変更しない。仕事用Work/Codexと趣味を分離、追加課金の事前承認が必要。
