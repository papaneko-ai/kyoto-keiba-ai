# 京都競馬AI開発｜完全移行パック・2026年11月9日 最終統合版

**目的**：新しいチャットへ移っても、P1～P8の合意・開発正本・実HTML原本・CI合格証拠・未解決事項・実装場所を漏らさず再開し、既済問題の再調査や既存本番の改変を防ぐ。前チャットは「実装06」。これは新規開発ではない。

## 0. 新チャットでの絶対手順（最優先）
1. 最初にGitHub `KYOTO_AI_START_HERE.md` を実際に読み、`docs/diagnostics/kyoto_ai_resume_evidence_registry_v1.json`、`docs/KYOTO_AI_20261109_P1_TO_P6_REAL_CI_AND_BUGFIX_INTEGRATED_MILESTONE.md`、本移行パックを読む。旧2026-11-06移行パックに残る進捗を現在の実績と取り違えない。
2. `papaneko-ai/kyoto-keiba-ai`、開発 `jra-html-diagnostic-20261105` の**その時点のGitHub HEAD**を取得し、毎回`main`と独立バックアップも照合する。以下に記載するHEADは文書作成時の値であり未来の固定HEADではない。
3. GitHub Actionsの**push実行履歴**はGitHub REST `GET /repos/papaneko-ai/kyoto-keiba-ai/actions/runs?branch=jra-html-diagnostic-20261105&per_page=100` → jobs → job logsで確認。PR専用 `fetch_commit_workflow_runs` や空のcombined statusだけで未実行と判定しない。
4. `diagnostics/kyoto_resume_gate.py` を、GitHub Artifact APIメタデータ `13482994623` またはSHA検証済み携帯ZIPとともに実行。失敗なら新規実装より先に証拠・保存先を修復。既存原本の再収集は禁止。合格でもJRA公式への新規自動GETや予測・実馬券購入は許可されない。
5. 開発はP1の未完部分（**未発走開催の合法・安定した出馬表／取消／馬連・枠連発走前オッズ／時刻・原本保全**）を優先。研究用合成テストを増やすだけの「節目」は避け、実行してCI結果まで照合する。
6. `main/app.py`、Turso、Streamlit Secrets、本番データ／実購入、旧公開アプリは変更しない。個人趣味のGitHub＋Streamlit、追加費用原則0円、スマホ軽量優先、業務用Work/Codexと分離。

## 1. 実在する実証済みデータと混同禁止区分
### 歴史的2026-11-07京都競馬（すでに終了）
- JRA由来の保存済み出馬表：**京都1～12R、全148頭、過去走日付396件**。12レースの個別スナップショットと`docs/diagnostics/JRA_KYOTO_FULL_DAY_ACCEPTANCE_20261106.json`に保存。レースカードの馬名・馬番・枠番・プロフィールhref・原本SHAを後発の148頭レジストリと照合済み。
- 詳細プロフィールのレジストリ：**確認済み96頭**＝過去走あり77頭＋履歴なし本人確認済み19頭、**未取得52頭**。累積の有効過去走**592件**。正本 `docs/diagnostics/jra_p1_batch14_96_profiles_20261106/feature_rows_148.json` と `status.json`。
- 2026-11-06保存復旧Artifact `13482994623`、Actions run `42176719321`（保存期限2027-02-04）。保存原本HTML86件＝PC馬プロフィール84件＋SP診断2件。**PC原本SHA一致で再解析できた84頭／485過去走／335特徴量一致**。PC原本が今回のZIPにない**残12頭は各レースの馬番1、記録上107過去走（原本再証明不可）**。84＋12＝96、485＋107＝592。混同して欠損を「未取得52頭」に足さない。
- 外側原本Artifact ZIPのSHA256 `49d61bff4eca82405d9d63e4244092e0fd2650bec5f899eba4f5ed2679c68863`。携帯用オフラインZIP `KYOTO_AI_P1_REAL_ORIGINAL_84_REPLAY_VERIFIED_20261109.zip` のSHA256 `7e16c23a595e13574554a7970cfc8ec3c4de652337f0bcbd7934ce1af4c83bd9`。再解析コード `diagnostics/jra_p1_eod_raw_replay.py`。**既に取得・再解析した原本を所在不明と誤認しない**。
- 11/06 04:05 UTC頃のJRA公式PC/SP画面は**その観測時点ではオッズ未発表**。11/07全日を通じてオッズが存在しなかった証拠ではない。過去10/31の公式最終オッズは馬連120組・枠連36組と解析できているが、**11/07の発走前価格には転用不可**。
- `diagnostics/p1_historical_day_handoff.py` と `docs/diagnostics/JRA_ODDS_READINESS_ACCEPTANCE_20261106.json`、`JRA_HISTORICAL_MATRIX_EVIDENCE_20261106.json` に安全停止の判定を保存。実発走前価格の確認は未達。
- P2履歴特徴量の実CSV：`docs/diagnostics/p2_historical_feature_matrix_20261107_148.csv`（148行・19列、「芝ダ」8観測、過去走あり/履歴なし/未取得の欠損理由を保持）。結果ラベル・最新オッズなし、学習/推奨不可。

### 新しい2026-11-09実装で追加した未開催日の「入力構造の受入」
- `diagnostics/jra_p1_intake_bridge.py`：手元から渡す原本ZIP・構造化スナップショットのSHA・取得時刻・レース一致・締切時刻を確認するが、**公式原本の真正性は未認証**。
- `diagnostics/p1_prerace_market_coverage.py`（今回新設）：出走馬全組合せの**馬連オッズ欠落・重複・未知馬番・異常値**を検出。18頭立て153組、部分的オッズなら拒否。`inspect_bundle_and_snapshot` に接続。たとえ完全でも`prediction_ready=false`、枠連市場・取消・公式発売情報・モデル較正は未検証。
- GitHub Actions `jra-p1-future-market-completeness.yml` 実行ID `42569049451`、ジョブ `129001941064`、**8+16＝24件PASS**。これは実JRA価格取得ではなく、研究用の構造テストのみ。P1正式合格ではない。

## 2. 実装状況と完成扱いをしないこと
| 段階 | 現実の到達点 | 必須未完 |
|---|---|---|
| P1 | 歴史的出馬表148頭、詳細96頭、PC原本84頭再解析、過去走592件、先行時点／原本・市場受入ゲート | 新開催日の公式出馬表/全馬/取消/実発走前馬連・枠連価格、原本長期保全、合法の自動入力 |
| P2 | 実148頭の履歴19列CSV、欠損理由保全 | 公式結果・払戻の時点分離、未使用時系列の条件発見・学習 |
| P3 | Plackett–Luce／Harville型研究用の馬連確率、同枠込み枠連集約 | 勝率／連対確率の推定・較正・時系列外部検証 |
| P4 | 市場オッズ×確率の研究用期待値・全組合せ検査 | 実発走前オッズ・鮮度・取消・控除率を反映する認定処理 |
| P5 | 予算上限・最大4R・最大3点・見送りの研究用処理 | 実モデルの確率/期待値/信頼度による資金最適化 |
| P6 | LAB専用予想凍結・ディスク追記型台帳・速報/払戻/訂正/返還、ハッシュ・再起動・二重計上防止 | 本物の発走前不変記録、公式結果・払戻自動採点、Tursoへの合法的な安全接続 |
| P7 | EVO-01～08の要件・独立認定とロールバック方針 | 同条件・未使用時系列の候補評価、認定、巻き戻し |
| P8 | 読取専用Streamlit診断アプリ、原本・市場未確認なら停止 | 新スマホ向け実用UI・本番連携。旧公開app.pyを設計参考にしない |

**確定した利用仕様**：1日の予算は上限で使い切り不要、推奨原則2～3レース（最大4）、各レース原則2点（最大3）、馬連/枠連を選択、順位・理由・取得鮮度・信頼度を短く表示、上位へ集中配分、手動調整可能。発走前の仮想投資を不可逆に近い証拠として保存し、実購入と厳密分離。競馬終了後、結果速報→払戻確定→訂正を扱い、的中率・回収率・最大損失・確率較正で検証。新旧モデルを独立時系列比較し悪化時に復帰。EVO-07独立証拠による進化証明とEVO-08意外性/反証仮説を含める。安全な根拠なしに馬券を推薦しない。

## 3. 引継ぎ失敗から導入した恒久管理
- 2026-11-06の原本Artifactを見落とし、既済工程を繰り返しかけた事故を反省し、ルート `KYOTO_AI_START_HERE.md`、24件以上の固定Git SHAを含む `docs/diagnostics/kyoto_ai_resume_evidence_registry_v1.json`、`diagnostics/kyoto_resume_gate.py`、13回帰テスト、GitHub Actionsを実装。バージョンv1を黙って上書きせず、追加更新は明示的な版・監査記録で管理。
- `docs/diagnostics/kyoto_ai_full_resume_ci_reconciliation_20261109.json` に、過去の失敗と修正済み成功を記録。コード・CIを安易に新規作成する前に読む。
- GitHub Actionsでは`main`を触らず開発ブランチ上で保存。別のバックアップブランチを節目ごとに作成。外部アーティファクトに保存期限があり、携帯ZIPはユーザー側の別保全が必要。
- 重要バグ① P6計算で`stake`が最終買い目額に上書きされる→`ticket_stake`に分離して修正。② 診断アプリがPython 3.11のf-stringで構文エラー、さらにAppTestの非存在属性を参照→修正済み。**再調査せず過去の根本原因と修正runを参照**。

## 4. 実際にGitHub Actions実行を確認した証拠
- 再開ゲート `42568017053`：SUCCESS（13件）。
- 既存原本84頭再解析 `42565633708`：SUCCESS（84頭・485件・335項目）。
- 保存済み12R出馬表とオッズ分離 `42567681829`：SUCCESS（12件、148頭・396日付）。
- P3～P6研究系 `42567612106`：SUCCESS（20+18+15=53件、収支バグ修正済み）。
- P6バイト同一性 `42567627196`：SUCCESS（15件）。
- 読取専用Streamlit診断画面 `42567945287`：SUCCESS（67回帰・AppTest）。また新しい取込ゲート変更後の `42569030528`：SUCCESS。
- 今回の馬連全組合せ受入 `42569049451`：SUCCESS（8+16=24件、18頭153組確認）。
- 最新の成功は**該当コミットでの検査**であり、将来の別コミットへの成功保証ではない。変更後に対象CIを再確認する。

## 5. 次の技術的・運用的な障害
**最重要：新開催日の正しい公式出馬表・発売中の馬連/枠連オッズを合法・安定・無料で取得する方法は未実証。** JRAページの包括的な自動収集許可は未確認。JRA-VAN有料Windows環境への無断移行禁止。いま採用できるのは、すでに正規に保存された手元ファイルの**読取専用オフライン検証**。入力の出典・取得時刻・全組合せ・取消・公式発売状態の検証が通るまでP3～P6を実予測へ昇格しない。

次の大きな節目は**入力経路の正式な利用条件確認→新開催日の許容された公式原本の入手→発走前オッズ両市場・取消と時刻→予測と仮想投資記録の時系列独立検証**。無許可のスクレイピング・実購入・Turso書込なし。

## 6. 前回以前の本番とバックアップ保護
- 本番mainの既知SHA：`471b60e632d878b52b6dcb4aa1a622becba40882`。変更前後に実照合。
- 直前の開発HEAD：`414a9bf6043058f0abe3628dffe6252258e3365a`。**本ファイル発行後の最新HEADはGitHub APIで確認すること。**
- 直前バックアップ `backup/kyoto-ai-p1-to-p6-real-ci-bugfix-20261109`。新節目の独立バックアップも作成後に比較して移行する。
- GitHub履歴は削除しない。正式なモデルデータ・オッズ・利益率などの数値を過去開催日から創作しない。

## 7. 移行時の必要物
1. 本書（完全移行パック）
2. GitHubルート `KYOTO_AI_START_HERE.md`
3. `docs/diagnostics/kyoto_ai_resume_evidence_registry_v1.json` と `docs/diagnostics/kyoto_ai_full_resume_ci_reconciliation_20261109.json`
4. `docs/KYOTO_AI_ALGORITHM_REQUIREMENTS_REGISTER_v1_20261106.md`、`docs/KYOTO_AI_ALGORITHM_AND_EXECUTION_ROADMAP_20261106.md`
5. 新チャット開始用指示文 `docs/KYOTO_AI_NEXT_CHAT_START_20261109.md`
6. GitHub最新HEAD・CI・独立バックアップ。携帯原本ZIP（必要時のみ、原本をチャットへ自動転載しない）。

**移行判定**：この統合版と開始用指示文を保存し、最新HEAD・バックアップ・本番mainを照合してから新チャットへ移行する。今のチャットでこれ以上同じ既済P1・P6を繰り返さない。
