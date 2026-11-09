# 京都競馬AI｜実装06・P1保存原本の所在／SHA監査ゲート｜2026-11-09

## 継続開始地点
- 開発ブランチ `jra-html-diagnostic-20261105`、直前節目HEAD `abea51e43c3fd1627922d7c5af7d8cbbab67ab91`。
- 2026-11-07京都148頭の保存済み個別特徴量レジストリは、過去走あり77、履歴なしの本人確認済み19、未取得52、合計592有効過去走。これらの再集計は前節目の履歴的事実として保全する。
- 今回目標は、`feature_rows_148.json`の各馬 `profile_source_sha256` に対応する**本物の保存済みHTMLバイトを実際に発見できるか**を測定すること。解析済みJSONをHTML原本そのものと取り違えない。

## 確認済みの障害
- 保存済みの `status.json` に `permanent_html_archive_completed:false`。ユーザーの完全移行パックにも長期原本保存が未完了と明記。
- 旧154件PASSのGitHub Actions run `42549866841` / job `128942805561` は再確認でき、job `conclusion:success`。ただし同runのアーティファクト一覧は**0件**。旧154件はオフライン模擬通信スイートの証拠であり、96頭の実HTML原本が取得できる証拠ではない。
- レジストリのSHA値は原本バイトの代用ではない。実HTML原本96件を再取得せずに再解析完了とすることを禁止。

## 今回実装した再検証用経路
- `diagnostics/jra_p1_historical_raw_inventory.py`（新規）：公式通信を呼ばず、渡した既存ディレクトリ内の `.html/.htm` ファイルを走査。保存済み148頭レジストリ中96頭の `profile_source_sha256` に一致する原本をSHA-256で照合する。馬の同定重複、既存未取得52頭の不正なソース表示、SHA破損、シンボリックリンク、巨大ファイル、過大候補数を拒否。不足している馬を機械可読JSONに列挙する。保管元HTMLの内容や取得日を推測・生成しない。
- `tests/test_jra_p1_historical_raw_inventory.py`（新規）：実レジストリを読み込む空ディレクトリ、テスト用の一致HTML、改ざんHTML、148行欠落、破損SHA、リンク、未取得馬番の重複を確認する**7テストを定義**。
- `.github/workflows/jra-p1-readonly-monitor-acceptance.yml`に新7テストと、checkout済み`docs/diagnostics`からHTMLを実走査するステップを追加。出力は`/tmp/p1_historical_original_availability.json`に保存し、GitHub Actions artifactとして保持7日。GitHubへ長期保管したりJRA原本を再GETしたりしない。
- ワークフロー実行コマンド:
```sh
python diagnostics/jra_p1_historical_raw_inventory.py \
  docs/diagnostics/jra_p1_batch14_96_profiles_20261106/feature_rows_148.json \
  docs/diagnostics \
  --output /tmp/p1_historical_original_availability.json
```

## 実測値と受入境界
- 旧GitHub Actions `42549866841` : completed/success、アーティファクト0件、今回直接再確認。
- 前回の個別レジストリ監査: 148頭、実プロフィール確認済み96頭、未取得52頭、過去走592件。今回、この数を水増ししていない。
- **今回追加した7テストとActionsのHTML走査は未実行・未合格**。GitHub Actions run IDや `matched_profile_count` はまだ確認できない。原本HTMLの再解析・真正性確認・公式取得時刻の証明もしていない。
- 今回のSHA監査は保存ファイルの有無だけを証明する。たとえ96件一致しても、解析コードでの再解析と結果比較なしに`prediction_ready=true`としない。
- GitHub Actionsの保持期限付きartifactはHTML原本の永久保存ではない。原本の長期保全場所と権利・容量・秘密情報取扱いは別途決定が必要。
- `main/app.py`、本番Turso、Streamlit Secrets、購入実績、PC/SP取得権限、実JRA HTTPは一切変更・実行しない。

## 次の未完ゲート
1. CIで実HTML探索を走らせ、artifactのrun/job/logとJSON内`matched_profile_count`を確認して不足原本を特定。
2. 既に合法的に保存された原本が存在する場合に限り、原本SHA照合後に既存のプロフィールHTML解析器を再実行して592件・馬IDと突合。存在しない原本を再取得した「事前証拠」と扱わない。
3. 新開催日の取得条件／実通信安全境界と公式出馬表・馬連／枠連発走前オッズを実際に確認。現時点で合法かつ無料の自動収集方式は未確定。JRA公式利用案内：https://www.jra.go.jp/use/ 。
4. P1～P8、ALG-01～13、EVO-01～08とP6の仮想投資凍結・EVO-07独立監査を維持し、無断で本番切替しない。

## 判定
**今回の節目は「実際の保存済みHTML原本の所在・ハッシュをGitHub Actionsで測定できる検査経路の実装」。実原本96件の再解析成功は未達。P1-FB第5段階全体は未完了。**
