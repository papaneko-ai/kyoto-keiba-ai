# 京都競馬AI｜P1実データ148頭・3分類レジストリ照合と診断画面修正｜2026-11-09

## 目的
前回の開発HEAD `5bbf369d7506396d2b30d1632a37e8cddc5bd99d` から継続。模擬HTMLを増やすのでなく、GitHubに保存済みの**2026年11月7日京都12レース148頭の個別特徴量レジストリ原本**を直接読み、累積ステータスと突合した。原本や累積記録は改変しない。

## 実データの出典（GitHub保存版）
- `docs/diagnostics/jra_p1_batch14_96_profiles_20261106/feature_rows_148.json`
  - Git blob `cbde475c0d5f8a8b29c4b690b620fa80bbf6e785`
- `docs/diagnostics/jra_p1_batch14_96_profiles_20261106/status.json`
  - Git blob `31638a46f48da2d28cb160f9453bad7d56b70de2`
- 148行をGitHub connectorで直接読み込み、各行の `source_coverage.horse_profile` と `performance_features.prior_valid_finishes_available` を独立再集計。全148レース×馬番キーに重複なし。全12RのレースカードSHAのレース内矛盾なし。全行 `prediction_ready=false`、`training_ready=false`。

## 独立再集計の確定値
| 京都 | 全馬 | 有効過去走あり | 履歴なしを証拠付きで確認 | 未取得 | 有効過去走件数 |
|---|---:|---:|---:|---:|---:|
| 1R | 9 | 9 | 0 | 0 | 14 |
| 2R | 15 | 15 | 0 | 0 | 32 |
| 3R | 13 | 13 | 0 | 0 | 22 |
| 4R | 15 | 15 | 0 | 0 | 22 |
| 5R | 8 | 0 | 8 | 0 | 0 |
| 6R | 11 | 0 | 11 | 0 | 0 |
| 7R | 11 | 11 | 0 | 0 | 156 |
| 8R | 9 | 9 | 0 | 0 | 261 |
| 9R | 10 | 2 | 0 | 8 | 25 |
| 10R | 14 | 1 | 0 | 13 | 8 |
| 11R | 16 | 1 | 0 | 15 | 30 |
| 12R | 17 | 1 | 0 | 16 | 22 |
| **総計** | **148** | **77** | **19** | **52** | **592** |

**重要：5Rと6Rの19頭は未取得ではない。** `VERIFIED_EMPTY_HISTORY` と `NO_HISTORY_TABLE_WITH_IDENTITY_PROOF` が証拠付きで記録されている。1～8Rの91頭は全馬詳細確認済み。9～12Rの追加確認5頭と合わせて合計96頭。以前の診断画面で96と91の差を「未割当」と見せたのは説明不足であり、今回解消した。

## コード修正・証拠
- `diagnostics/p1_registry_reconcile.py` 新規：正本148個別行と累積statusを突合。レース別三分類・過去走件数・馬番一意性・レースカードSHA・profile SHA・本人確認済み空履歴と単なる未取得の区別・全体フラグを検証。不一致は拒否。予測準備を決して立てない。
- `tests/test_p1_registry_reconcile.py` 新規：GitHubに保存された**実際の148行JSON**を直接読む10テストを追加。実データ再集計の値、5R/6Rの履歴なし、9R～12Rの5頭、改ざん、同一性、偽の学習/予測準備を検査。
- `diagnostics/p1_readonly_monitor_app.py` 更新：レース別の3区分を個別JSONから表示。古い累積statusの人数だけでレース別プロフィールを分類しない。原本や総数に不整合がある場合はアプリで表示停止。
- `.github/workflows/jra-p1-readonly-monitor-acceptance.yml` 更新：新しい実レジストリテストと、実Streamlit AppTestでの77/19/52表示検査を追加。
- `docs/diagnostics/jra_p1_historical_registry_reconciliation_148_20261109.json`：**GitHub connector内で148行を実際に独立カウントした結果**を機械可読で保存。状態 `INDEPENDENT_ROW_RECONCILIATION_CONSISTENT_HISTORICAL_ONLY`、矛盾0。

## 合格範囲と未検証
- **今回独立して実行できたこと：** GitHubの実レジストリ148行を読み、77/19/52、592、12Rごとの数値、レース内SHA同一性、個別同定の重複0をチェックし、正本に整合。
- **未実行：** 新規Python10件のローカル/CIテスト、Streamlit実起動、GitHub Actionsのrun/job/log。したがって「新10件PASS」や「Streamlit実起動成功」は宣言しない。
- この検証は保存済みの**特徴量レジストリの内部整合性**。全96プロフィールのオリジナルHTMLバイトを開いて再ハッシュ・再解析した検証ではない。外部時刻証明・JRA公式の最新開催日予測データとしての適格性は主張しない。
- 11/07は終了済みであり、今後この96頭のデータを事後的な発走前予測へ使わない。

## 次の受入条件
1. GitHub Actions 10件のPython実データテスト＋Streamlit画面実行/healthの独立run ID・ログを確認。失敗の場合は当該原因を修正する。
2. 11/07の原本オリジナルHTMLを独立再検査できる実アーカイブ経路を確認する。同じ取得済み情報を再ダウンロードしない。
3. 新しい未開催日の実際の公式出馬表と発走前馬連/枠連オッズを合法的・安定的に取得できる条件を定める。無許可実JRA HTTP GET禁止。PC/SP URLを推測生成しない。
4. 自動出馬表解析→オッズ→最小予測→凍結仮想投資→払戻照合の実装へ移る。P1～P8、ALG-01～13、EVO-01～08とEVO独立監査の範囲は維持。

## 保護
本番 `main/app.py`、本番Turso、Streamlit Secrets、実馬券台帳を変更しない。P1-FB Stage5の**歴史的実レジストリ監査・診断UI補正を今回の節目として達成**。実用予測ゲート自体は未達。
