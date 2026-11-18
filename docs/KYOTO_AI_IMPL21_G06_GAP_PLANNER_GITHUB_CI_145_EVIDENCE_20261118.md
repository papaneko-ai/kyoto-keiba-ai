# 実装21 G06欠測回復計画器・GitHub独立試験証拠（2026-11-18）

## 変更（実験ブランチのみ）
- 新規：`diagnostics/kyoto_g06_gap_recovery_plan.py`、`tests/test_kyoto_g06_gap_recovery_plan.py`。
- 変更：`diagnostics/kyoto_g06_all12_capture.py`。取得済み馬連・枠連SHAを保持して欠測項目の回復候補を提示。未観測SPリンクの推測は禁止。アクセス拒否403/429時の他ホスト回避は禁止。現在の回復計画は**ネットワークを一切実行せず**、現場の許諾済み補助情報源/発走前時点に従い次操作を記録するだけ。
- G06-HYB-01/02/04/05の前段制御が進んだが、実取得器による項目別の自動再試行・リンク探索・補助ソース取得が完成したことは意味しない。

## 独立試験と復旧
- `Kyoto G06 paired-market all-12R capture preflight` Run **44239999272** / Job **134585266550**、HEAD `8c6b7de8fc6ca07226dadf5f6f4aa86bb8c9cee2`、**145 tests OK**、外部HTTP取得の成功証拠ではない。
- CI Artifact **14398833788**、digest `sha256:86b023175cb98f331538d9252e05850a9c4c605bbfe8ad2f30c8a415df492e8c`。
- full-source checkpoint Run **44239999255** SUCCESS、Artifact **14399177153**、digest `sha256:6e7239ee6e1102967280736263e1bbdc51874032b4bc5c85e26e609bab6cd9b2`。
- 本証拠文書追加後のHEADは上記証拠時点から進むが、本書追加はテスト・実行コードへの変更を伴わない。

## 本番への非反映
GitHub `main` のNov21・22 schedule workflowと実験ブランチ同名workflowは別内容。main本番取得器固定SHA `c96df31542cb94435ca36cb4a1b8bd6de938233f` は、独立実験G06の最新HEADを使わない。無承認で本番・Turso・Secrets・予約時刻を変更しない。

## 固定管理指標
既存12工程 **6/12**、予備9工程 **6/9**、新ハイブリッド6工程 **4/6**、実開催独立検証 **0/6**、実用能力独立検証下限 **0/100**。今回の145件PASSだけでG06/H03/H05を合格認定しない。
次の固定指標上昇には、保存済み実原本の全12R照合、独立SP原本、実際の項目別フォールバックと再試行まで検証する必要がある。週末の取得が必要なゲートは事前に自己認定不可。
