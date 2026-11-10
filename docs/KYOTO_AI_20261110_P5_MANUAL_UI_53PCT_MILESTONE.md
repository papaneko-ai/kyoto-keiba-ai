# 京都競馬AI・P5-04実装節目：固定工程52→53点（2026-11-10）

## 実装
- `diagnostics/p5_manual_allocation_app.py`：新しい独立したStreamlit画面。馬連/枠連の切替、予算上限、候補レース数1〜4、1レース買い目数1〜3、候補別比率を手動調整。スマホ向け中央配置。
- `diagnostics/p5_manual_allocation.py`：100円単位・予算を超えない決定論的な最大剰余法。ゼロ比率は配分ゼロ、金額・比率・候補数の不正入力は拒否。
- `tests/test_p5_manual_allocation.py`：計算の端数・上限・不正値に加え、実Streamlit AppTestで馬連→枠連切替、予算変更、候補数変更、購入ボタンなしを検証。
- 常時CIへAppTestを追加。最初のCI run 42755342340 はAppTestの相対パス誤りで失敗し、絶対パス解決へ修正。修正後run 42755410973/job 129628530896/SHA 5cd8d0298c6ad1bcb57410d684f1e7242bb26f9c success。

## 受入の定量証拠
- 固定32項目100点の**P5-04（馬連枠連選択・手動比率調整UI）1点**だけを新規合格。採点の配点・合格条件は変更していない。
- 採点CI run **42755514707** / job **129628863154** / SHA **db20b0456d86c4ad2ce41e41afa53f8a97206948** success。ログ `KYOTO_PROGRESS_VERIFIED=53%`, `KYOTO_PROGRESS_DELTA=1`, `KYOTO_PROGRESS_REMAINING=15`。
- 独立検証済み実用能力の下限 `KYOTO_OPERATIONAL_VERIFIED=0/100`、未検証100/100。**53%は研究・開発工程の認定得点であり、実運用完成率ではない。**

## 実装境界と次の工程
この画面は候補レースの順位、実際の馬番、発走前オッズ、期待値、予測確率を生成しない。実際の購入・仮想投資記録・Turso書込み・HTTP取得は行わない。本番main・公開アプリ・Secretsには触れない。次は実開催日の合法的な出馬表と発走前市場の独立認証、モデル統合に進む。研究用の加点だけで実用化を主張しない。
