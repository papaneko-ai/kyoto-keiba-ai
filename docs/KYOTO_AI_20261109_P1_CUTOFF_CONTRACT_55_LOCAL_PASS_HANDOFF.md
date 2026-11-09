# 京都競馬AI｜P1-FB第5段階・原本と構造化データの同一締切保証｜2026-11-09

## 出発点と原因
- 直前開発HEAD: `99c4f326e02ed4b4747a74b588fee097827dfa18`。作業前にGitHub compareでHEAD一致を確認。
- 前節目の `diagnostics/jra_p1_intake_bridge.py` は原本ZIPと構造化出馬表・オッズJSONについて同一開催日・レース番号・SHA・取得時刻を照合するが、manifestの `cutoff_utc` と構造化JSONの `prediction_cutoff_utc` を**突合していなかった**。
- また検査の実行時刻が予測締切を過ぎた場合に、`STRUCTURAL_CHECK_ONLY` として返せる危険があった。どちらもP1の事前/事後混入を誘発する同根の欠落であり、既存部品を最小改修した。

## 修正
- `diagnostics/jra_p1_intake_bridge.py`：原本の固定締切とJSONの予測締切を同一UTC時点として比較。不一致なら `cutoff_time_mismatch` で拒否。検査時刻が締切以上なら `cutoff_already_elapsed` で拒否。UTCの `Z` と `+00:00` は正規化して照合。新しいネットワーク、DB、認証機能なし。
- `tests/test_jra_p1_intake_bridge.py`：締切不一致、締切経過、UTC同義表記の3件を追加。前回52件＋今回3件＝55件。
- 既存の `.github/workflows/jra-p1-future-evidence-offline.yml` は該当テストファイルをすでに自動実行対象に含むため、同じテストを重複定義する変更は行わず、診断ブランチへのpushでの検証を意図した。

## 独立したローカル受入証拠
- 実行: `cd /mnt/data/kyoto_p1_bridge && PYTHONPATH=. python -m unittest discover -s tests -q`
- 実測: `Ran 55 tests in 0.062s / OK`。従前52件のケース（13原本時点・12 ZIP・17出馬表/オッズ・10接続）と新3件を通しで検査。
- GitHub上ソースblobと実行ソースGit blob SHA一致：`080cb07cecdbec11f4bb4474aac3aa48451f29ad`。
- GitHub上テストblobと実行テストGit blob SHA一致：`9b93b1f8d535e4af799258f8ae48c7c39ffab3fb`。
- 他の従前モジュールは前回ローカルコピーに由来し、今回改めて全ファイルのGit blob同一性を証明したわけではない。この55件は**ローカルオフラインテスト**であり、GitHub Actionsでの55件CI successとは主張しない。
- 154件の旧GitHub Actions success（run `42549866841`）は別の検査の履歴。55件との合算CI成功件数は宣言しない。

## 未解決と停止条件
- JRA公式自動収集の利用条件、現行公式PC/SPリンク、実HTTP安全アダプター、異ホストの取得予約共有、未発走開催の真正な原本・馬ID・当日馬連/枠連オッズの取得は未達。
- 今回は実際の開催時刻や取得時刻をJRAから独立照合していない。ZIP/JSONは外部申告値であり、原本HTMLを解析して馬番・オッズが正しいと証明したものではない。したがって検査成功でも `prediction_ready=false`、投資推奨なし。
- Streamlit実起動や画面の実操作、GitHub Actions新規run ID/job/logの確認も未達。GitHub checksが空でもCI成功とはみなさない。
- 古い11/07の終了済み京都の148頭中96詳細・592有効過去走を将来の発走前予測に流入させない。歴史的statusファイルは変更しない。

## 次工程（実務優先）
1. すでに定義済みのGitHub Actionsで55件を実行したrun ID/job/logとStreamlit AppTest/healthを確認。公開・権限変更・本番設定の無断変更はしない。
2. 無料・許容される公式原本の取得方法を確定する。原本から構造化出馬表・馬ID・正式発走時刻・発走前馬連/枠連オッズを抽出・照合し、手入力JSON恒久依存を排除する。利用条件が未確認なら自動GET禁止。
3. P1が実データで合格した後に、P2～P8、ALG-01～13、EVO-01～08を維持したまま、最小予想→P6事前登録仮想投資・結果照合へ進む。CIの件数だけで実用完成とは認めない。

## 保護判定
本番main/app.py、Turso、Secrets、実馬券台帳は変更しない。**小節目：原本/JSONの締切整合性不具合修正とローカル55件PASS。P1-FB第5段階全体：未完了。**
