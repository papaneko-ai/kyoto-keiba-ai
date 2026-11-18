# 実装21 G06-HYB-04 回復計画器・候補保存（2026-11-18）

## 成果と証拠
- G06-HYB-04の部分市場原本保持・不足項目別次候補判定・回復予定のローカル候補を作成。
- `diagnostics/kyoto_g06_gap_recovery_plan.py`、`diagnostics/kyoto_g06_all12_capture.py`、テスト2本の4ファイル変更を候補ZIPに固定。
- 141テスト成功（オフライン、Python unittest）。GitHub Actionsでの**新規候補の独立試験は未実施**。
- 配布パック `KYOTO_AI_IMPL21_G06_GAP_RECOVERY_CANDIDATE_20261118.zip` SHA256 `5c3d8b9a3069e765b4f01773927741d86484a5d55a07720212b86b66bbef350a`（現在のチャット添付として保存）。
- 欠測は原則PENDING_RECOVERY、既存馬連取得は保存。SP公式URLの推測は禁止。403/429などによるアクセス拒否があれば別公式ホストへの回避もしない。補助情報源は許諾と観測URLが確認された候補だけ利用を検討。
- 本番main/Turso/Secrets/固定SHA/11月21・22日予約は変更していない。

## 要注意：本番差分
`main` の `.github/workflows/kyoto-20261121-22-two-source-production-observer.yml` のblob SHAは `3882275d40aa900fb1cccaf353f07a5906992324`。実験ブランチの同名workflowはblob SHA `f0330aaf8ea136fd8ee891c7e5c4ed05e879c391` と異なる。
mainは各日09:15、10:15 JST等の取得枠がある。11/21固定collector SHA `c96df31542cb94435ca36cb4a1b8bd6de938233f`、既存事前CI成功 Run `44030290660`。実験ブランチの固定SHA `e2a48f8b58ae13c210eead22533ee107004a45cd` とは別。
**実験ブランチG06変更は今週末の本番ジョブに自動反映されない。** 無承認の本番切替禁止。

## 固定指標
既存 6/12、予備実験 6/9、ハイブリッド 4/6、実開催 0/6、実用独立下限 0/100。**本候補による合格増加はない。**

## 次の再開点
パックの中身をローカルで照合し、既存実験ブランチコードとの最小差分マージ→CI追加→独立GitHub Actions/Artifact検証→必要なら本番差分審査（本番はユーザーの別途承認）を実施する。既存の135件成功Run `44239049687` と復旧Run `44239155819` を無意味に再実行しない。
