# 京都競馬AI｜P8公開配備の実証準備と検証不能事項（2026-11-11）

**分類：実装・障害調査チェックポイント。認定率上昇による「大きな節目」ではない。**

## 1．固定された進捗と節目条件

- 対象は `papaneko-ai/kyoto-keiba-ai`、開発ブランチ `jra-html-diagnostic-20261105`。本番`main/app.py`、Turso、Secrets、実購入機能は触れない。
- 直前の確定研究・開発工程認定率は **94％（30/32項目）**、研究段階卒業 **100％（12/12）**、実開催接続独立検証 **0/6**、実用能力の独立検証下限 **0/100**。
- **ユーザーの新指示：「次の大きな節目」とは、研究・開発工程認定率が直前確定値を上回ること。変更指示があるまで常時適用。** よって94％のままの調査、CI成功、書類追加、バックアップは「節目達成」と扱わない。
- 未達は固定 P3-02 **4点**（実データで市場とモデルの同条件比較）と P8-04 **2点**（公開環境の動作・復元・費用検証）。いずれも実証とCIが揃った場合だけ認定。現時点では加点していない。固定ルーブリックや点数を緩めない。

## 2．公開済み旧診断Cloudの外部確認結果

- 過去に別途設定済みの独立診断URL `https://kyoto-ai-cloud-probe.streamlit.app` をGitHub Actionsの**読み取り専用の外部観測**で確認。研究用新P8シャドーアプリとは別物。
- `diagnostics/p8_existing_cloud_readonly_probe.py` と `.github/workflows/kyoto-ai-existing-cloud-observation.yml` を追加。GitHubから当該Streamlitドメインの `/_stcore/health` と `/` だけをHTTPSで確認し、JRAにはアクセスせず、Secretsや本番を変更しない。
- 実測 run `42936843953`、job `130248909540` は技術的にsuccessだが、2つのHTTPS応答はいずれも `HTTPError`。ログの `KYOTO_EXISTING_CLOUD_HEALTH_OK=FALSE`、`KYOTO_P8_04_PUBLIC_CLOUD_CERTIFIED=FALSE` を確認。確認できない状況を「成功」と混同しない。保存Artifact `13818896080` は初回観測run `42936605305` の結果。
- 旧Cloud診断アプリが健全だったとしても、新P8アプリの動作・復元・費用まで自動的に合格するものではない。

## 3．今回新しく用意した公開配備の入口と照合

- `diagnostics/requirements.txt`：研究用シャドー画面の限定依存関係。ルート`requirements.txt`を変更せず、本番アプリへの副作用を避ける。
- `diagnostics/p8_cloud_source_identity.py`：実行中環境のGit HEAD 40桁SHAを読み取り専用で取得。Gitを読めない場合は `UNKNOWN_NOT_CERTIFIED` と明示し、誤った真正性認定を防止。
- `diagnostics/p8_uploaded_archive_shadow_app.py` に「起動コードのGitHubコミット」を表示。研究診断専用であり、実購入・JRA自動通信を行わない。
- `diagnostics/p8_cloud_release_gate.py`：ユーザー自身が配備した**新P8アプリのURL**に対し、HTTPS、Streamlitドメイン、起動SHA、スマホ幅390px、研究用警告、未入力での計算禁止、実購入ボタン不在を、独立Chromiumで2回のクリーンブラウザセッションから検証。旧Cloud診断を新P8の証拠に流用しない。
- `.github/workflows/kyoto-ai-p8-remote-release-verification.yml`：新P8 URLを入力して手動開始する**外部実測専用**Actions。実行時HEADのSHAと、実際に配備されたUI表示SHAを突合する。成功時にはSHA付きの独立観測Artifactを保存する。
- `tests/test_p8_cloud_release_gate.py`：不正なドメイン・非HTTPS・情報混入URL・短縮SHA・Git不在・タイムアウト・本番改変を拒否する13件を固定の全体CIへ追加。
- **別途Cloud環境への新規アプリ作成やCloud再起動を行ったとは主張しない**。公開URLとソースSHAの一致が認められても、GitHub ActionsからCloud管理画面の実際の再起動操作や課金プランを独立に確認できないため、現段階でP8-04の認定は保留する。

## 4．Streamlit Community Cloudで必要な唯一の配備操作（mainは変更しない）

Community Cloudの既存アカウントで `https://share.streamlit.io` を開き、GitHub所有者に対応するワークスペースで「Create app」→「Yup, I have an app」を選ぶ。**新しい独立アプリ**の入力項目は次のとおり。

- Repository: `papaneko-ai/kyoto-keiba-ai`
- Branch: `jra-html-diagnostic-20261105`
- Main file path: `diagnostics/p8_uploaded_archive_shadow_app.py`
- Python: **3.11**（GitHub Actionsと合わせる）
- App URL: 新規の自動割当URLでよい。入力名を推測・作成済みと見なさない。
- Secrets: 不要。追加料金を要するAPI/DB/サービスはこのシャドー画面では使用しない。既存`app.py`の配備やSecretsを変更しない。

Cloudに新アプリが存在して正確なURLを確認できたら、GitHub Actionsで `Kyoto P8 external shadow deployment identity acceptance (manual, no changes)` の `app_url` に**実際の新アプリURL**を入力し、外部から2回のUI検証を実施する。その後、Streamlit管理画面から**新しい診断アプリだけ**をRebootし、再起動後にも同一SHAで正常動作することを別runで確認。Cloudの費用と利用プランはCloud管理画面の記録で裏付ける。**この3つの独立証拠が揃うまでP8-04の2点は増やさない。**

公式ドキュメント：
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization
- https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/reboot-your-app

## 5．再開・報告の不変契約

- 常に最新GitHub HEADと同一SHAの全体CI、元P1原本保全Artifact `13482994623`、復旧zipとブランチを確認する。
- 本文末尾の7行2列の形式に戻さず、ユーザー指定の**緑の％進捗バー＋4列5行表**を固定。列は「管理指標／前回／今回／増減」、行は「研究・開発工程認定率」「固定32項目の合格数」「研究段階卒業達成率」「実開催接続の独立検証」「実用能力の独立検証下限」。
- 同一率の間は「次の大きな節目に到達」と言わない。認定率の増加と復旧・全体CIの成功を、同じHEADにおいて確認して初めて達成。
- P3-02はこれまでの `diagnostics/p3_same_cutoff_market_model_bridge.py` を再利用し、実開催で真正な発走前出馬表/馬連枠連全オッズ、時点固定した実モデルを取得できるまで追加得点を認定しない。


## 2026-11-11 実装09追補：公開済みP8シャドーと外部ブラウザ描画失敗（98％維持）
- 別Streamlit Community Cloudアプリ `https://kyoto-keiba-ai-5opazxhrw7xwh4imfemey6.streamlit.app` を実際に配備。利用者提供スクリーンショットにより研究用画面とGit commit `3ac9e19f4e099e69c40ba093be811a16a1760a27` の表示、管理画面からのReboot後の画面復帰を確認。ただしこのスクリーンショットはGitHub CIによる独立Cloud管理操作の証明ではない。
- 初回Cloud起動は `ModuleNotFoundError: No module named 'diagnostics'`。原因はサブディレクトリエントリポイントからのパッケージ import path。不変のrepository rootを起動ファイルの `sys.path` に追加し、同原因の回帰テストを追加。修正CI run `42947946289` success。
- GitHub Actions手動 `workflow_dispatch` はdefault branch `main` にワークフローがないためユーザーのActions画面で Not found。mainを変更せず、開発ブランチのpushトリガーと固定公開URLで読み取り専用の検証を開始できるようにした。
- 外部ブラウザ検証 run `42948883556` failure：研究画面の見出しが55秒以内に表示されず。失敗の原因不明状態を解消するため、公開ページのHTTP/本文/ブラウザイベント/WebSocket/失敗スクリーンショットの診断を追加。run `42949494887` failure、証拠Artifact `13823614726`：HTTP 200・ページtitleあり・body空。
- run `42949696674` failure：HTTP 200、ページtitleあり、本文空、`data-testid=stApp`要素0、ブラウザconsoleの403/404リソースエラーあり、Streamlit `/~/+/_stcore/stream` へのWebSocket生成あり。**外部GitHub runnerからStreamlitフロントエンドの動作はまだ独立検証できていない**。ソースSHAや安全ゲートを緩めて合格とすることは禁止。具体的403/404リソースの応答先とWebSocket通信失敗の切分けを次の研究課題とする。
- 利用者提供のStreamlit Workspace Limits画面は1 app 2.7 GB・private app 1・public apps unlimitedを確認できるが、実請求金額0円の領収/請求記録ではない。無料運用については課金実績の独立証拠を引き続き必要とする。
- **研究開発認定率98/100（31/32）を維持。残るP8-04の2点は未認定。実開催接続0/6・独立実用能力下限0/100も不変。** 既存main/Secrets/Turso/実購入/旧公開アプリには変更なし。


## 2026-11-11 実装09追加確定：外部Cloud描画障害の端末依存性切分け（98％維持）
- P8独立外部確認をfail-closedのまま深掘り。外部検証器 `diagnostics/p8_cloud_release_gate.py` に、通信失敗のURLパス・HTTP status・WebSocketイベントを機密情報なしで限定出力する診断を追加。run `42951216319`：HTTP 200、タイトル正常、本文0文字、`stApp`生成0。403/404の発生場所を分類。未合格。
- 具体的な応答失敗は、`/api/v1/app/event/open` の403、`/api/v2/user/details` の404、外部分析 `cdn.heapanalytics.com/js/heap-.js` の404。Streamlit `/~/+/_stcore/stream` WebSocket生成は観測したが、それだけでは双方向通信の成功や画面表示を保証しない。個別の403/404が根本原因と確定したものではない。
- 同じ閲覧専用URLでモバイル（390px）失敗時にデスクトップ（1280px）対照観測を実行。run `42951431815`：どちらもHTTP 200だが本文0文字、`stApp`生成0。**モバイル固有のレイアウト問題ではなく、GitHub runner環境からのCloud画面描画不成立**と切り分けた。端末差の切り分け結果をモバイル認定に流用しない。
- 現在の外部ブラウザ経路では画面表示の独立証拠を取得できない。HTTP 200・タイトル一致・ユーザーの実画面スクリーンショット・Cloud上の再起動後の表示は別々の証拠として維持。無根拠のCAPTCHA/アクセス制限回避、特定の403握り潰し、テストの緩和、100％加点を禁止。
- 残る独立確認は公開環境での第三者再現可能な画面検証と実際の管理画面上の費用/請求実績である。既存のスクリーンショットによりWorkspace Limits（公開アプリ無制限、1アプリ2.7GB）を確認したが、請求実績0円の認証ではない。
- 次工程では認可された別の外部ブラウザ経路またはユーザー提供のCloud管理画面/実行証拠の独立照合を検討する。別経路が未提供なら障害記録を保持して待機し、同じ環境で無意味な失敗を繰り返さない。
- **固定研究・開発認定98/100（31/32）維持。P8-04の2点未達。研究段階卒業12/12、実開催接続0/6、実用下限0/100**。main/Turso/Secrets/旧公開app.py/実購入機能は不変更。
