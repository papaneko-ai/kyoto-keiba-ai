# 京都競馬AI｜2026-11-09 P1-FB第5段階 オフライン安全性ゲート到達／次回引継ぎ

## 1．到達した大きな節目
**P1-FB Stage5 のオフライン取得・出馬表同定・耐障害保存サブゲートはPASS。Stage5全体の実通信・自動フォールバック・本番採用は未PASS。** 前回のStage4（mock 59件）から安全な実装を継続した。誤って「PC/SP実通信が可能」「予測できる」と報告しない。

- GitHub Actions run `42545936023`、job `128930848806`：全ステップ success。19（stage5）＋10（公式出馬表台帳結合）＋17（stage4）＋16（通信予算）＋11（SP特殊行）＋15（PC/SP双方向判定）＝**88件全部成功**。Python compile成功、`OFFLINE_ONLY_GATE_PASSED`。
- 途中の失敗を消去しない。前回の原子保存テストの失敗 run `42545309575` を訂正し、`42545363980` で49件 success、その後今回88件の全回帰に合格。
- JRAへの追加HTTP GET **0**。実通信の成功・公式PC/SP全馬照合・新開催の実出馬表取得は実証していない。
- GitHubに機械可読のゲート `docs/diagnostics/jra_p1_fb_stage5_20261109_acceptance.json` を保存。

## 2．今回追加・強化した実装
1. `diagnostics/jra_p1_fb_stage5_guarded_replay.py`：公式と同定済みの馬・レース・馬番・原本SHA・取得UTC・URLを事前検査。発走前カットオフ・既検証馬/既取得URLを検査。PC/SP双方向モック結果を検証。実HTTPクライアントは組み込まない。
2. HTML原本は同一ディレクトリの一時ファイルを `fsync` 後、既存ファイルを上書きしない `os.link` で確定し、ディレクトリを `fsync`。失敗ならfail-closed。原本の長期別媒体保存は別課題。
3. 解析器側の進捗receiptは`atomic_receipt`を注入し、途中で半端なJSONが露出しないよう一時ファイル＋`os.replace`＋ディレクトリ`fsync`。旧ファイルを残す故障注入試験にPASS。
4. `diagnostics/jra_p1_fb_stage5_registry_binding.py`：GitHub保存済み`docs/diagnostics/jra_p1_batch14_96_profiles_20261106/feature_rows_148.json`から、レース・馬番・馬名・公式出馬表のSHA・観測済みPCプロフィールhrefを一致させ、**未取得52頭だけ**を選択可能にする。既確認96頭、別馬、重複、改ざんした台帳、非公式ホスト、不一致の開催時点を拒否。
5. **SP版プロフィールURLは公式出馬表からの独立同定が全馬で未証明**なので、PC版のCNAMEトークンから勝手に生成せず`sp_url=None`とする。SP実通信自動切替が有効と偽らない。
6. 過去走の日付判定を固定値`2026-11-07`から、実際の対象開催日`roster.meeting_date`へ変更。次の将来開催で過去走・開催当日情報を混同しない。

## 3．時点保証の重大制約
- 保存済みのP1実績：**2026-11-07京都12R148頭、詳細96/148頭、未取得52頭、有効過去走592件**。京都1R～8R確認済み。最新の実証status `docs/diagnostics/jra_p1_batch14_96_profiles_20261106/status.json`。
- 本日は**2026-11-09**。残52頭を今取得しても11/07の発走前に取得した原本としては扱えない。**batch_15を過去開催の予測時点を偽って実行しない。**
- 追加収集の安全性をテストするには、別の未開催の公式出馬表・実在馬ID・発走予定/オッズ締切・原本時点を新たに固定する必要がある。事後データは歴史的ラベル用として別扱いにし、凍結した予想を作り直さない。

## 4．次の具体的な未完ゲート
- **P1-FB Stage5 の次のサブゲート**：①公式PC/SPそれぞれの証明付き同一馬リンク照合、②初期状態で無効なHTTPアダプターの設計と法令/利用条件/通信回数/レート/レース締切の実制御、③プロセス間の同時重複取得防止（現在のincident-folderだけではグローバルなURL重複防止を証明しない）、④障害回復と原本保存の長期耐久性を独立に検証する。
- **実HTTPを勝手に有効にしない**。`offline_replay_only`というPython属性はネットワーク不通を強制するセキュリティ境界ではないことを明示する。
- P1-FBの公式実通信ゲート未通過なら旧来の制限付き単一路線のみを検討。SP/PC自動切替を本番実装済みと主張しない。
- 将来の次開催で正式な出馬表取得・時点保証を確立するまで、模型データや結果後の出馬表で本番の買い目を生成しない。

## 5．開発原則・実践投入優先
- 工程P1→P8とALG-01～13、EVO-01～08を保持。特にP6の仮想投資・レース後公式馬連/枠連の的中払戻、P7の自己進化認定監査とEVO-08の「閃き」・反証型仮説発見を保全。
- 旧公開アプリの設計は流用しない。本番 `main/app.py`、Turso、公開予想モデル、実馬券取引記録は無承認変更禁止。追加費用原則0円、個人趣味と業務Work/Codex分離。
- 設計を増やすことだけに費やさず、既存の成果を再利用して**実装・実証・失敗記録・原本保存**を進める。次回の実作業はP1-FB第5段階の上記未通過ゲートから順次開始する。
- 新しいチャットでは本ファイルと`docs/diagnostics/jra_p1_fb_stage5_20261109_acceptance.json`を読み、最新HEADと公式status/CIを照合してからコードに触る。

## 6．変更点と非変更点
- 実装したPython：`diagnostics/jra_p1_fb_stage4_mock_adapter.py`（日付・receipt writerを注入できるよう後方互換で追加）、`diagnostics/jra_p1_fb_stage5_guarded_replay.py`、`diagnostics/jra_p1_fb_stage5_registry_binding.py`。
- 回帰テスト：`tests/test_jra_p1_fb_stage5_guarded_replay.py`、`tests/test_jra_p1_fb_stage5_registry_binding.py`＋旧4組。
- CI：`.github/workflows/jra-p1-fb-stage5-offline.yml`を拡充。
- **まだ実装していないもの：** JRAへの自動取得、全馬SP公式プロフィールURL取得、オッズ・調教・天候等の学習入力、実際の予測、仮想投資の公式払戻採点、自己進化。実践投入は未到達。
