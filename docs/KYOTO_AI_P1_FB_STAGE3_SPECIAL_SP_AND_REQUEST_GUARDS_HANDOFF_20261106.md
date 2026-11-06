# 京都競馬AI｜P1-FB第3段階・複数SP公式原本、特殊履歴、通信前制御 受入・引継ぎ（2026-11-06）

## 結論／次の再開位置
- **P1-FB第3段階のオフライン実装・検証ゲートPASS**：保存済み公式SPプロフィール2頭のSHA照合・原本再解析、地方競馬記録、転入転出、人気欠損、馬名アンカー、双方向切替の通信前制御。
- **本番自動PC/SP通信切替の完成・承認ではない。** `live_auto_fallback_authorized=false`、`training_ready=false`、`prediction_ready=false`。今後はP1-FB第4段階、HTTPアダプターとエラー隔離の統合を、モックHTTP・原本先行保存・公式リンク・時点・レート制御・故障注入で独立検証する。
- 京都2026-11-07の出馬表148頭。P1確定チェックポイント `docs/diagnostics/jra_p1_batch14_96_profiles_20261106/status.json`：**公式プロフィール詳細96頭、未取得52頭、有効過去走592件、京都1R〜8R全頭確認**。比較用SP版2頭目をP1取得済み人数に加算しない。
- 既存ALG01〜13、P1→P8、P1-DUAL-01〜08変更なし。新通信方式を未検証のまま既存P1バッチ15以降に導入しない。

## 原因究明／修正
### 第2公式SPプロフィール原本
- 京都11R馬番2「エティエンヌ」。公式SP版11R出馬表原本から**保存済み公式SPリンク**を使用。新規公式GETは1回、未認可のURL推測や再試行なし。
- 原本取得時刻 `2026-11-06T06:31:44.333054+00:00`、原本SHA256 `88fff685dec67e145b8e4cf68b8d4c738550798dae6a6806779d31351b0cfa45`。通信後に**原本HTML保存→SHA/UTCレシート→解析**の順序を実施。
- 初回SP解析では39行中、過去走26件、転入転出2件、未解析11件。初回失敗レシート `docs/diagnostics/jra_p1_fb_offline_20261106/sp_profile_second_receipt.json`。
- 異常の詳細を**保存原本に対する0 HTTPオフライン再検査**で特定。対象は園田・船橋・水沢・盛岡の地方競馬11行。園田の1行のみ公式ページに人気順位がない。`docs/diagnostics/jra_p1_fb_offline_20261106/sp_second_invalid_evidence.json`。
- `diagnostics/jra_p1_sp_profile_offline.py`を最小修正：4競馬場を`LOCAL`、既存JRAを`JRA`として区別、地方競馬で厳密に「着順のみ」の場合だけ`popularity=None`と`popularity_missing=true`、未確認の競馬場や意味不明な形式は今までどおりinvalid。転入転出2行は`administrative_events`に隔離、実績へ混入させない。障害芝・障害ダートを芝・ダートとして誤分類しない。
- 修正後、**39行＝通常過去走37件（JRA26・地方11）＋管理イベント2件、invalid0件**。人気順位の欠損1件。証拠 `docs/diagnostics/jra_p1_fb_offline_20261106/sp_second_final_identity_replay.json`。**PC版との全行比較は2頭目では未実施**。このSP実験をP1の97頭目として採用していない。

### SPプロフィール馬名の厳密な同定
- 以前はHTML全本文の部分文字列一致を用いていたため、過去走の対戦相手の馬名でも本人と誤認するおそれがあった。
- 公式原本2頭のDOMを独立SHA検証した結果、両馬とも`div.bameiSection`の**正確な独立馬名テキスト**として存在。 `docs/diagnostics/jra_p1_fb_offline_20261106/sp_identity_dom_audit.json`。
- 解析器を**単一`div.bameiSection`の正確な馬名テキスト照合**に修正。相手馬名が本文にあるだけでは拒否する回帰試験を追加。
- 既存の公式SP第1原本（京都11R馬番1「モンドプリューム」）も修正後に再解析。PC版と過去走30行の主要7項目＝210セル全件一致、除外1行一致、invalid0、0 HTTP。証拠 `docs/diagnostics/jra_p1_fb_offline_20261106/sp_first_final_identity_parity.json`。

## 通信前フォールバック制御（まだ通信は行わない）
- `diagnostics/jra_p1_fb_request_budget_policy.py` を追加。PC→SP／SP→PCについて、公式固定プロフィールURL・出馬表によるリンク証明・レース馬番号氏名・原本ハッシュ根拠・障害レシート・取得期限・2秒間隔・同URL二度試行禁止・既成功データの再取得禁止をオフライン判定。
- 解析/形式エラー時は取得原本と障害証拠、HTTP応答前の失敗で生HTMLが存在しない場合は**失敗レシート**を必須にする（原本が存在したと偽らない）。
- 判定の正例であっても戻り値は`DRY_RUN_ELIGIBLE`であり、**HTTPを実行する処理ではない**。既定は無効。実運用の自動切替を許可していない。
- `tests/test_jra_p1_fb_request_budget_policy.py` に通信間隔、重複・時点・通信失敗・原本失敗・本人同定等の16回帰ケース。

## 実際に確認したCI
- [42174986970](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42174986970)：2頭目SPの一回限定取得と解析前原本保存。取得CIは成功だがSP解析は`PARSER_INVALID_ROWS`で、その事実を保存。
- [42175065925](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42175065925)：11未解析行の原本SHA付き診断、HTTP0で成功。
- [42175253458](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42175253458)：2頭目の不具合修正後再解析、1頭目のPC/SP無改変比較、SP専用回帰成功。
- [42175455126](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42175455126)：通信前予算・重複禁止のオフライン制御成功。
- [42175562838](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42175562838)：2頭の独立SP原本で馬名DOMを特定、HTTP0で成功。
- **最終 [42175674425](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42175674425)：SP特殊行11件＋取得予算16件＋双方向判断15件＝42テスト成功。** 最終の2頭公式SP原本をSHA照合し、1頭目の210セルPC/SP一致と2頭目39履歴行の正確な分類を再検証。全ジョブ成功、追加HTTPなし。

## 未完了・事故防止（厳守）
1. **本番の双方向ネットワーク自動切替は未実装、未テスト、未承認。** `P1-DUAL-01～08`全体が完了したと宣言しない。
2. 現在のSP対応は2頭だけ。2頭目はPC全履歴との比較がなく、SP版の未知の特殊形式、全地方競馬場、取消等、他レース・他馬を網羅していない。SP固定運用・全馬一致を宣言しない。
3. **取得時刻に依存した過去情報利用可否**は各実データゲートで検査。SPの生HTMLを学習・予測用の入力へ直接流さず、未来・同日イベントが混ざると拒否する統合ゲートをさらに実装する。
4. PC版とSP版のフィールド不一致は自動採用しない。SP実験で得た人気欠損は埋めず、モデル特徴の欠損として保持する。地方競馬の過去走をJRAの過去走と誤認しない。
5. 元HTMLはGitHub Actionsの期限付きArtifactが中心（3日間）。恒久アーカイブ・利用条件・運用時の保存先はまだ未完了。証拠SHAと正規化サマリーだけで原本の恒久復元を保証しない。
6. `main/app.py`、本番Turso、公開予測モデル、実馬券購入記録は変更禁止。業務のWork/Codexを混ぜない。

## 次の工程（新チャットでも厳守）
**P1-FB第4段階**：取得アダプターの安全な統合を「モックHTTPでPC失敗→SP成功」「SP失敗→PC成功」「双方失敗」「内容矛盾」「HTTPで原本なし」「解析失敗で原本あり」「期限切れ」「同URL再試行拒否」「候補URLが未同定」を実証し、各障害ID・原本の耐久レシートを取得。プロバイダー利用条件と費用を確認したうえで限定した実公式ソースを検証。新機能を無審査でライブ有効化しない。
第4段階PASS後、P1残り52頭の`batch_15`以降の工程へ復帰。既確認96頭を再取得しない。複数馬SP実験だけでP1プロフィール詳細人数を増やさない。
