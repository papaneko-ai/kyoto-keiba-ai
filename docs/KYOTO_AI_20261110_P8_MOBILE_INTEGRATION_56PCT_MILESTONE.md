# 京都競馬AI：スマホ統合画面 P8-02 節目（2026-11-10）

## 実装と既存実データ
`diagnostics/p8_mobile_readonly_planner_app.py` を追加。保存済み2026-11-07京都12R/148頭の実履歴確認数（96頭）と未取得数（52頭）を既存の `diagnostics.p1_monitor_viewmodel.summarize` から読み取り、馬連/枠連・予算・候補数・買い目数・候補別比率を一画面で操作できる。予算計算は前節目で実装済みの `diagnostics.p5_manual_allocation.allocate` を再利用。ネットワーク・DB・購入・仮想投資・実予想は未接続。過去開催と現在を厳格に区別。

## 自動検証
`tests/test_p8_mobile_readonly_planner.py` はStreamlit AppTestで実履歴148/96の表示、馬連→枠連切替、予算15,000円への変更、候補数3→4の動的UI更新、購入ボタン不在を確認。初回CI run 42755973728 はテストのStreamlit表示要素型の想定違いで失敗。修正後run **42756040357** / job **129630546706** / SHA **17d835cebbd4fa7a2150f6de10838e35b557c499** success。

## 定量採点（固定ルーブリックを変更せず）
P8-02「新スマホ実用画面と予算・買い目操作」研究・診断範囲の3点を認定。採点run **42756125698** / job **129630826914** / SHA **b6f7ba1ee160897764f75a1d2dfe0cb0d99f989b** success、`KYOTO_PROGRESS_VERIFIED=56%`、`KYOTO_PROGRESS_DELTA=3`、残り14条件。**独立検証済み実用能力は0/100**。この3点はライブ予測・実用化・実開催日の取得証明ではない。P8-03（実開催データ・予測・仮想精算連携）とP8-04（公開環境動作）は未認定。

## 継続の優先事項
合法的な新開催日発走前JRA出馬表・馬連枠連オッズの取得・独立時刻証拠、P3実モデル、P6仮想投資の連結。実原本がない限り実用ゲートは加点しない。公開main/Turso/Secrets/実購入は変更しない。
