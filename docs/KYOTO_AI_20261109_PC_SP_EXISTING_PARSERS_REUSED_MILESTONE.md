# 京都競馬AI｜PC/SP既存解析器再利用・次開催日対応・オフライン補完の実装記録（2026-11-09）

## この節目の位置付け
既存の実データ取得機能を再設計せず、実装済みPC/SP解析器を利用する。2026年11月7日京都の実出馬表・既存5レース両経路検証を新規解析器の開発として繰り返さない。

## 調査で確認した既存の本物の実績
- `diagnostics/jra_pc_sp_benchmark.py` は従来からPC側 `diagnostics.jra_multi_capture_20261106.parse` とSP側 `sp_rows` を使っていた。
- `docs/diagnostics/pc_sp_benchmark_20261106/benchmark_report.json` に京都2026-11-07の1R、5R、6R、11R、12Rの両チャンネルのパース／レースカード一致記録がある。従来の `tests/test_jra_benchmark_acceptance.py` は8件成功（本節目のCIでも再検証）。
- `docs/diagnostics/JRA_SP_RUNNER_PARITY_20261106.json` は初期の0頭失敗記録であり、`JRA_SP_RUNNER_PARITY_FIXED_20261106.json` と `JRA_SP_RUNNER_PARITY_FIXED_RECEIPT_20261106.json` に11Rの16頭一致という修正済み証拠が残る。初期失敗を現況と取り違えない。
- 上記は過去の開催時点の証拠。発走前馬連・枠連オッズの継続取得の成功を意味しない。

## 既存モジュールの修正・接続
1. `diagnostics.jra_multi_capture_20261106.parse` は従来の2026-11-07をデフォルトに保ちつつ、`meeting_date` を指定できるようにした。過去走日付の境界と当日見出しを与えた開催日で照合する。従来の11月7日の履歴・呼出互換を維持。
2. `diagnostics.jra_pc_sp_benchmark.pc_rows` から新しい開催日引数を既存PC解析器に渡す。
3. `diagnostics.jra_pc_sp_benchmark.reconcile_saved_racecards` でPC/SP保存済みHTMLを既存両解析器へ入力する。独立に検証済みの凍結済み名簿を基準に、番号・枠番・馬名を完全一致比較。PCに問題がある場合、SPが完全一致するならオフラインでSPへフォールバック。逆方向はPC採用。SHA不一致・時刻矛盾・原本欠落・両経路不一致は遮断。
4. 新たなネットワーク収集器は追加していない。過去の公式原本GETを再実行していない。本番main・Turso・Secrets・実馬券履歴は不変更。

## GitHub Actions実ログに基づく受入
- Workflow: `Kyoto P1 reuse actual PC and SP roster parsers`
- run `42575107672`、job `129020946710`、success
- `tests/test_jra_pc_sp_saved_reconciliation.py`: 13件PASS（既存解析器を使う動的開催日・PC故障時SP補完・不整合拒否・時刻拒否・反復同一性）
- `tests/test_jra_benchmark_acceptance.py`: 既存8件PASS（実PC/SPベンチマークの保存済み記録を再評価）
- Workflowと実際のGitHubコミットの参照はCI run/jobと合わせて固定する。テストは新規開催日について合成HTML、ベンチマークは保存済み過去の実測記録に基づく。

## 完了/未完了の明確な区別
- 完了：既存PC/SP出馬表解析器の再利用、開催日可変化、保存済み原本ベースの比較・補完、合計21件の対象CI検証。
- 未完：PC/SPの実開催日ライブ取得の統合、取得権限に適合する運用経路、公式発走前馬連・枠連両市場、取消速報との統合、実予測解禁。
- 次の大きな実用節目は、新しい開催日について既存URL発見・取得コードを結び、正当に取得した実原本のPC/SP解析と市場の同期まで確認すること。単独の研究用検証追加を節目としない。
