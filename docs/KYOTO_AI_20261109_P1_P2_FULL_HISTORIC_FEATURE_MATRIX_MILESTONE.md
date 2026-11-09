# 京都競馬AI｜実装06・P1歴史的原本照合基盤＋P2実特徴量148頭の一括節目（2026-11-09）

## 今回は区切りを拡大
前回HEAD `51d958ca90dbeeed6c099f8619f580a883ffc199` を基準として、従来の単一検査部品追加ではなく、**保存済み実データの安全な再利用→特徴量マトリクス生成→原本の所在監査→スマートフォン用診断画面→双方の独立CI→機械可読証拠**をまとめて実施する。既存P1～P8・ALG-01～13・EVO-01～08の工程順・要件は破棄しない。

## 1. 実際のJRA由来の既存レジストリを解析
入力正本:
- `docs/diagnostics/jra_p1_batch14_96_profiles_20261106/feature_rows_148.json`、Git blob SHA `cbde475c0d5f8a8b29c4b690b620fa80bbf6e785`
- `docs/diagnostics/jra_p1_batch14_96_profiles_20261106/status.json`、Git blob SHA `31638a46f48da2d28cb160f9453bad7d56b70de2`

2026年11月7日京都12R・148頭、プロフィール状態は**過去走あり77頭／履歴なしを確認済み19頭／未取得52頭**。有効過去走592件。11/07の終了済み開催の情報であり、新開催日の予測値として表示しない。

## 2. P2履歴特徴量マトリクスを生成
- `diagnostics/p2_historical_feature_matrix.py`：本番予測器とは独立したP2研究用構造化・CSV出力処理。P1個別レジストリとstatusの一致を先に検査し、レース・馬番順で決定的に整列。出典SHA、欠損理由、過去走件数、直近3走の距離・着順割合・勝利数・馬場種別、90日履歴日付指標を保存。
- `docs/diagnostics/p2_historical_feature_matrix_20261107_148.csv`：**実際の148頭分の19列CSV**をGitHub connector内で生成・保存。Git blob SHA `ebdf629227c9671c9696fa8e868b8849f2d2fdcd`。
- 元の`recent_three_surface_counts`には`芝ダ`8件が存在。最初の出力で独立の列を欠落させていたため、同一節目内に原因を修正して`recent_three_mixed_turf_dirt_count`列を追加。8件すべてを情報欠落なしで保存した。
- 未取得52頭と履歴なし確認済み19頭を同じ`0`で埋めない。いずれも過去走実測のない項目は空欄、情報の状態を別列で持つ。
- 競馬当日のオッズ、結果、正解ラベル、払戻金は入力に含めない。`source_row_status=HISTORICAL_NOT_MODEL_ELIGIBLE`を全行に固定。現段階のモデル訓練・投資推奨は不許可。
- `docs/diagnostics/p2_historical_feature_matrix_evidence_20261109.json`：元データ／CSVのGit blob SHA、各レース内訳、特徴量取得数、元の`芝ダ`8件、利用禁止を保存。

### GitHub connector上での独立実測
保存済みCSVの実148行・19列を、正本148頭の馬番・馬名・レース・原本SHA・プロフィール状態・過去走・混合馬場の値に逐一照合して**不一致0**。全過去走数592、三状態77/19/52、芝ダ8件と一致。これは**実行済みの個別データとCSVの整合性検査**であり、PythonのCI成功やHTML原本の再解析結果ではない。

## 3. UIとテスト・CI
- `diagnostics/p1_readonly_monitor_app.py`：既存スマホ対応診断画面へ、個別148頭レジストリから生成した特徴量の取得率と、履歴CSVのダウンロードを追加。履歴研究専用・予測不可の警告を維持。
- `tests/test_p2_historical_feature_matrix.py`：現在14件のケースを設定。148頭の正本、欠損区分、決定性、ラベル混入禁止、実公開CSVとの数値一致、異常値と馬場分類欠落の拒否を対象とする。
- `.github/workflows/jra-p2-historical-feature-matrix.yml`：GitHub Actionsの無償Python環境でP2特徴量再生成・テスト・発行制約の検査を定義。CI artifact保存は7日。ファイルをJRAへ再取得するものではない。
- `.github/workflows/jra-p1-readonly-monitor-acceptance.yml`：履歴特徴量生成の実テスト、アプリのAppTest、以前の原本SHA所在監査とローカルHTTPヘルス検証を一括して対象にした。
- 現在のGitHub connectorは新しいGitHub Actions run/job IDを確認できていない。**新規14件のPythonテスト成功・Streamlit実起動・新CI PASSは未確認**。GitHubへのソース保存とCI定義追加を合格の代用にしない。

## 4. 保存済みHTML原本の取扱い
- 前節目で用意した `diagnostics/jra_p1_historical_raw_inventory.py` は既存HTMLファイルのSHAが保存済み96頭に一致するか調べるが、当該新CIの走査結果は未確認。
- 旧GitHub Actions run `42549866841` / job `128942805561` の154テストsuccessは、別のオフライン検証として尊重する。旧runでartifactが0件だったことを別途確認済み。
- **96頭の元HTMLバイトが全て存在し、その原本を再パースできたとは断定しない。** このP2データはGitHubにすでに保存された「解析済み特徴量」のマトリクスであり、原本HTMLの真正性証明ではない。

## 5. この節目を経て次に進む条件
1. 新P2 CIで全テストとCSV再生成・receipt一致をrun/job/logで検証。診断画面のAppTestとダウンロード確認も実行証拠を残す。
2. 原本SHA所在スキャンのartifactを取得し、実在する原本だけを既存HTMLパーサーで再解析。欠損原本を推測値で埋めない。
3. JRA公式データの自動取得許諾と利用形態を独立に確認する。包括許諾未確認の自動GETやPCからSP URLの合成はしない。追加費用を伴うデータサービスの無断採用なし。
4. 新開催日の公式出馬表・馬ID・発走前馬連/枠連オッズと正式発走時刻を原本/UTC/SHAで固定し、P1の合格データだけをP2～P5へ流す。
5. P6の発走前凍結型ペーパートレード・結果自動採点・P7進化検証と巻き戻し、EVO-07/EVO-08へつなぐ。今回の過去データに事後正解ラベルを付けて同一レースで精度を誇張しない。

## 保護・判定
- 本番 `main/app.py`、Turso、Streamlit Secrets、購入履歴、JRA自動HTTP、旧公開アプリは変更なし。
- **今回の幅広い実装節目：既存の実データ148頭の特徴量CSVが生成・監査・GitHub保存され、スマートフォン診断画面と再生成CIにつながった。**
- **未達：GitHub Actions新テスト成功、原本HTML96件再解析、新開催日ライブ取得、P2予測精度、実用投資とP1-FB Stage5全体の受入。** 完成と誤認させない。
