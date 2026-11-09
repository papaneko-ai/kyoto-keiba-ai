# 京都競馬AI｜2026-11-09 P1-FB第5段階・厳格事前通信ゲートの節目（123テスト）

## 判定
**オフライン通信前安全ゲートPASS。実HTTP通信、正式PC/SP自動切替、本番採用は未PASS。** 2026年11月9日にGitHub Actions `42547524417`（job `128935646813`）が計123件の全オフライン回帰テストに成功。JRA追加GETは0件。

## 今回実装・検証
- `diagnostics/jra_p1_fb_stage5_live_preflight_disabled.py`：発走前の根拠を持つ公式レース/馬ID/プロフィールURLの厳密検査。CNAME余分パラメータ、偽ホスト、認証情報、ポート、非HTTPS、リダイレクトURL等を事前拒否。PC/SP実在の根拠なきURLは遮断。
- `verify_request`：公式出馬表の原本SHA、取得日時、開催日の整合、予測締切、タイムスタンプとURLの一致をチェック。異常値を拒否し、`network_allowed:false`のみ返す。
- `reserve_offline_simulation`：注入型clock/monotonic時計の間隔と、既存SQLite一回限り予約台帳を統合。2秒未満なら予約不可、予約後の重複は不可。ただし**模擬時計の検証であり実通信の測定ではない**。
- `deny_network_execution`：呼び出しても常に`LiveNetworkDisabled`で拒否。**実際のHTTPクライアントは未実装で、無許可の実通信は不可**。
- `tests/test_jra_p1_fb_stage5_live_preflight_disabled.py`：13件新設。前回110件も全件再検証成功。
- 機械可読ゲート `docs/diagnostics/jra_p1_fb_stage5_live_disabled_preflight_gate_20261109.json` を同時保全。

## 進行中・実践投入への未完ゲート
1. **通信の本当の安全性**：公式の取得利用条件/自動化の許容、認可、接続先・HTTPレスポンスの上限、リダイレクト拒否、実時間2秒間隔、通信/失敗件数の持続的な保全の独立確認。テスト中の`last_call_monotonic`は現状呼び出し側が供給する値であり、本番の耐改ざん・プロセス間同期には未到達。
2. **PC/SPの独立リンク証拠**：残り52頭について既存PC URLは原本から同定できるが、SP版プロフィールURLは全頭の公式根拠がない。根拠のない変換は禁止。
3. **複数クラウドホストをまたぐ二重取得**：同一SQLiteパスにアクセスするローカルの排他は実証済み。Streamlit/GitHub Actionsなど異なるホストの台帳は未接続。本番Tursoは無承認変更しない。
4. **予想対象の時点**：2026-11-07京都12R148頭、詳細96頭、過去走592件を保存。2026-11-09に事後取得したデータを11/07発走前に存在したと偽装しない。次の未開催日の実際の出馬表・発走時刻・PC/SPリンク証拠を将来別途固定する。
5. **実践投入への最低限**：P1実データの適法な継続取得・凍結→P2～P5の買い目選択→P6仮想投資と公式払戻自動照合。EVO-01～08/ALG-01～13の必須要件は維持し、P7自己進化監査を後続する。

## 作業保存と次回再開
- 正本は本書と`docs/diagnostics/jra_p1_fb_stage5_live_disabled_preflight_gate_20261109.json`。旧資料`docs/KYOTO_AI_20261109_P1_FB_STAGE5_SHARED_LEDGER_MILESTONE_HANDOFF.md`（110件）は履歴として保持。今回は123件成功であるが第5段階の実通信ゲートは未PASS。
- 次回は**P1-FB Stage5の実HTTP通信セキュリティ/利用条件・SP公式リンク独立証拠・異ホスト共有台帳**を優先。P2に飛ばさない。
- 本番`main/app.py`・Turso・実購入履歴・既存バックアップは変更しない。旧公開アプリから予想やUIを設計しない。趣味/業務混在なし、追加費用原則0円。
