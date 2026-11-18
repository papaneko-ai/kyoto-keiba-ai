# 実装21 G06：公式市場リンク原本照合・独立CI証拠（2026-11-18）

## 新たに解消した誤判定
前段の`run_twelve`は`bool(spec.pc_racecard_url)`等（出馬表URLの存在）を「市場オッズリンクを公式に観測した」として回復計画器へ渡していた。これでは市場リンクを未観測でも`FETCH_OBSERVED_MARKET_ONLY`と案内し得る。

実験ブランチで新規`diagnostics/kyoto_g06_market_link_evidence.py`を追加し、保存済み`receipt.json`と`official_odds_menu.html`または公式ナビ原本について原本バイト数・SHA256・発走前UTC・競馬場/開催日/レース同一性・公式CNAME形式・最終オッズ否定を独立に検査。失敗時は公式リンク観測の根拠なしとして`OBSERVE_INDEPENDENT_OFFICIAL_NAVIGATION`を選択。推測URLの取得はしない。

`diagnostics/kyoto_g06_all12_capture.py`に結果を接続し`official_market_link_proof`を保存。ハッシュ改ざん、最終オッズ、発走後、レース不一致、受領証不在、肯定経路のテスト追加。全工程ネットワークアクセスを増やさず、本番変更なし。

## GitHub上の独立実証
- Branch: `experiment/multisource-hybrid-20261117`
- 機能試験に用いたHEAD: `0c88a756a5ec8124f123b4aa71f1ea50ab4ee03f`
- CI `Kyoto G06 paired-market all-12R capture preflight`: Run `44240759689`, Job `134587800507`, **151 tests OK / success**.
- CI証拠 Artifact `14398559187`, digest `sha256:352b59dd9e377fe9f7b8007f2b4f049cd77c1f7fef989bc0832e2da55f8b9b97`.
- 同HEAD全ソース復旧: Run `44240759652`, success, Artifact `14400045080`, digest `sha256:98de70b9f19b5324d10ceaafc32eec719c7ab1297f661c7e0a6317b79f3e5e2b`.
- main/既存開発ブランチは無変更。本番取得器固定SHAは`c96df31542cb94435ca36cb4a1b8bd6de938233f`。

## 固定進捗の厳格評価
既存12工程 6/12、予備9工程 6/9、ハイブリッド6工程 4/6、実開催独立 0/6、実用能力独立下限 0/100を維持。
追加試験成功や資料作成だけで認定条件を緩めない。ユーザー指定の「現状の固定数値を大幅に超える節目」は今回**未達**。
G06の発走前全12R実原本、H03全12R SP原本、H05同一実原本比較、G08外部スケジューラ実発火など独立証拠が必要。

## 次の優先作業
1. 実験用取得器で公式ナビの独立探索→欠測市場**のみ**再取得する実処理を整備（プランナーだけでは未完成）。
2. 部分原本を保持し、失敗種別・購入前時刻・発走時刻・出典で回復を制御する。403/429を別ホストによる拒否回避に使わない。
3. 週末11月21・22日のmain固定取得器と実験G06の差分を無断切替せず、既存予約とデータ取得を最優先。開催前に動かせない実原本・タイマー実証を済と扱わない。
4. 直近復旧点はRun 44240759652。GitHub HEADが先に進む場合は、その差分を確認して再開。
