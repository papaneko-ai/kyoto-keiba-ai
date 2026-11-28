# 京都競馬AI｜緊急改修・再開正本
更新日: 2026-11-28 JST / checkpoint E37-158-03
状態: 本番反映済み、最終総合検査は未合格。P0-1の隔離検証・修正着手。
対象: papaneko-ai/kyoto-keiba-ai。本書はスマホからの緊急開発・チャット移行用。実装36までの完全移行パックを破棄・置換するものではない。

## 0. 再開時の必須手順
1. GitHub connectorで本書のブランチ handoff/emergency-current の最新HEAD、関連Issue #141（本文と全コメント）、固定25リスク #116、main最新HEADを照合。記録後のPR、実行履歴・障害があれば差分だけ取り込む。古いHEADへの復元や成功済み試験の無条件再実行は禁止。
2. 最新の承認待ちPR・候補SHA・CIを照合。未承認のmainへのマージ禁止。既にマージ済みのPRは再マージしない。承認は指定PR/HEADに限定。
3. 下記P0から実修正・隔離回帰・独立検証を続行。単なる調査報告で止まらない。ユーザーの手動操作は最小限。承認が必要なときだけ具体的なPRとHEADを提示。
4. 変更着手前に対象・予定修正・基準SHAを記録。各重要なコミット、試験結果、失敗、承認待ち、マージ後の独立照合の直後に、作業ブランチ/PR/HEAD/run/job/artifact/根拠・未完了事項をIssue #141に追記し、この固定パスを更新。未完了の途中状態も保存。旧チェックポイントはGit履歴とIssueコメントに残す。再開時は記録と実物を照合する。チャットの停止後に自動で記録されるとみなさない。
5. 最終総合バグチェックを正式なゴールにする。実取得成功、原本保全、解析、独立解消認定を混同しない。固定25リスクの分母を変更しない。

## 1. 目的と保護範囲
11/28失敗を11/29の完全取得に活かす。全12Rの出馬表、全馬プロフィール/過去成績、馬体重と増減、天候・芝/ダート馬場、含水率・クッション値、調教、発走前の馬連AND枠連の全組、取消/除外、結果、払戻・返還・同着・訂正、原本/SHA256/UTC/レースIDを保全。取得データが研究と仮想投資/予測の基礎となる。既存のPC/SP独立照合と相互補完、補助情報源、発走前時点保証を維持。未公表・取得失敗・取得後欠損を区別。SPリンクをPCから生成しない。アクセス拒否や既存通信予算・ペーシングを回避しない。
固定予約、Cloudflare外部予備起動、Secrets、Turso本番/実験DB、既存成功証拠を保護。外部タイマー恒久設計は #124 の方針維持。監視タスクは読み取り専用。緊急改修と区別し、監視側から手動起動・変更しない。
新機能より完全取得の妨げを解消。原因→最小再現→同根探索→隔離修正→反例・回帰→承認されたexact HEAD→本番独立照合→証拠記録。任意の未知障害の完全自動修復は未達。成功保証をしない。

## 2. 本番・固定版（今回再取得確認）
- main: 1fed7e79796d91de76d2c5f85486f6625d69ef3f
- #158 承認HEAD be6228320bb6b6996f015eca2afe5680aa323166, merged=true, 上記mainに反映。候補→main内容差分0。既存6取得workflowの承認範囲外変更0（4本pin更新、調教・クッションは同一）。
- 日曜朝の選択候補、午後、夕方、handoff、独立reader: ba7d5bb4c05698dfb92119460b45e730b5eb512b。隔離PR #157、run 46113899999/job 140883276948、延べ816回帰成功、artifact 15250008446 SHA256 9cb5145c137a7c767163968deaa89230b468623042acdda4a9048548e174a5aa。
- 土曜朝baseline: 3f4b3d77357745ead05a9f78db34eb6ac2d78637。11/29は既検証receipt経路で意図しない旧版への後退を防止。
- 調教reader: 5855874f3f6dc9711d9b6f0444786ea2be0e05e7。隔離PR #151, run 46112279070, 47回帰成功。
- クッション取得: 47cd7f9e881aa989b9f932373cfaf5278dea223a。クッション日次統合: 301916719e5bc0e3a8e392368434f952c16c05db。
- 固定リスク台帳: 日曜collector内 docs/diagnostics/KYOTO_REVERSE_FMEA_GAP_REGISTER_20261116.json, git blob 72856cf227e6a369f3e1650641dfacec0cdc0d73。25リスク、13 BLOCKER、103対象面。独立解消認定0/25。
- #158 CI 8/8: 46114052039,46114051990,46114052070,46114052043,46114052001,46114052134,46114052031,46114052103。
- 最終総合検査実行 46114223286、test/review/publishの3/3成功。artifact 15249964330、ZIP SHA256 a5b16fa4f44741c59b7d369b1bd6b6985066e0069f51d44b909386953d6aa77d、review.json canonical SHA256 fa0a56bb8effc21b03d33f2e48edf563c83c0857f2e9bccf35ef9222f4ec5619。ZIP実取得・CRC・digestを今回確認。2026-11-28T05:55:22Z時点の監査。25件の固定リスク行、25 source runs、13 native slots。原本再検証工程は完走したが、出馬表0/12、全馬分母不明、完全取得認定false。最新のライブ情報は再開時に差分確認すること。

## 3. 反映済み修正の索引（再開時に過去の成果を使う）
| PR | 修正 | mainへの反映コミット |
|---|---|---|
| #142 | PC/SP公式導線、取消、翌日適応・引継ぎ | 093e18584d8cac349f05f201c6d13b559c29caea |
| #143 | 独立結果払戻・前日12R証拠 | f9022b2e4c8511aeb301cba4d5619317ea3a6726 |
| #145 | 自動障害証拠・修復worklist | 8a7d14069d6b08514162864b26724d55a94bd41f |
| #146 | 既知のナビゲーション自動適応 | e69e73575ea8e31a4c469408ce2de849ade377ce |
| #147 | 土日午後補完 | feca264cff3abd61c7d426b4f578759c36238be0 |
| #148 | 全日欠損・回帰の独立検査 | edb48e6ad13eb7897d0261a1ccba8bff923dae7e |
| #149 | 本番検査自動起動・証拠回復 | 6dce39936013495a7b417a047479cb3ecba61467 |
| #150 | 原本保全・翌日引継ぎの回復 | b61cc2677451232137bed191964a74a6c551868d |
| #152 | 調教側の新旧原本形式互換 | f0da276dabd197e5f12b00fed06300e7ea5c60ed |
| #153 | 検証済み日曜取得器の後退防止 | 10ba44c030663ca99fc62088deacc3319df5a919 |
| #154 | スキップ/原本欠損の区別と診断停止防止 | bf2f54e299f6494ee5fb738077b8b19f68f59ae8 |
| #156 | G05取消馬・馬体重解析のレース単位隔離 | d6db8a8e02d543654a2b074890ca9c2c03f2525a |
| #158 | 公式馬場URL・HTTP障害証拠 | 1fed7e79796d91de76d2c5f85486f6625d69ef3f |
すべて今回GitHub PR mergedを確認。詳しい根拠は #141 と #116。承認待ちの新規候補はこの記録では未作成。未取得のPR一覧は再開時に確認。

## 4. 最優先残存工程（着手前の再開位置）
### P0-1 取得成功→再解析0件の原因を確定し修正する
実績: 午後補完 run 46112551733/job 140879102270 はb66249fbef412f76befba022f406ff422fbd3ffd、verified_races=[10,11]、observed_field_values=0、HTTP15。artifact 15250785307、ZIP SHA256 444a678b0c8a98f475b369bd3acd858b3be96e1adf64527bc8ca5f4adf780b2c。今回ZIPを取得しdigest/CRC、manifestのrepo/day/run_id、ciphertextのSHA一致、g03 racecard 1〜11を含む18ファイル名を確認。AES認証・平文原本再解析は未実施（秘密を外部に出さない）。ファイル名の存在は有効データの証明ではない。
対照: 本番日次検査 46114223286 は同じauxiliary artifactをPRESENTと記録するが roster_verified_races=[]。rejected_runsは午前PC4実行のPartialProofRejectedのみ。auxiliaryの個別拒否理由が日次概要に出ていない。
コードで確認した不整合:
- 日曜候補 diagnostics/jra_one_shot_market_capture.py のObservedRaceSpec.validateは www.jra.go.jp を11/29だけ許可。一方 diagnostics/kyoto_g03_all_races.py は11/28・29の両日を許可。
- 同様の日付条件が diagnostics/jra_market_source_chain.py、diagnostics/kyoto_impl30_profile_resume.py、diagnostics/kyoto_g04_all_horse_profiles.py に存在。11/28補完側はpublic_form_navigationを両日に使用。G03からG06へのadapterがrace_specを検証し、失敗はskip_invalid_racesでNoneになる。
- これらはコード上の実在する不整合。ただし実原本がこれにより拒否されたとする直接原因の断定は未可。
次の実作業: GitHub内の既存暗号化原本・既存secret参照を使う隔離読み取り専用再解析で、実際の拒否段階/安全なreason codeを出す。ネットワークはGitHubの原本取得のみ、JRA追加通信なし、鍵・平文・氏名の出力禁止。既存fixtureとactual artifactに対して両日・旧/現公式ホスト・同一レース・発走前・反例の回帰を行う。単なるホスト許容の一括緩和や時点保証の撤廃は禁止。実際の原因を直し、後工程（PC/SP、午後、結果・払戻、調教、日次集計）の互換性を確認。既存版の全回帰を再利用し、変更点の必要な試験のみ追加。修正候補・CI・独立検証を経て承認依頼。
完了条件: 同一暗号化原本から少なくとも有効な10R/11Rを独立再解析できるか、拒否された場合は真正な具体的原因を説明。誤った0件集計や理由消失を解消し、時点/日付/ホスト誤りを拒否する。11/29実取得認定とは分離。

### P0-2 既存の調教・クッション・SP実装を再利用し、最終総合検査で照合する
- 訂正（前回セクションの成果を再確認）: 調教・クッション値の取得機能は実装済み、本番反映済み。両機能を未実装として作り直さない。PR #129（午後原本で調教馬照合）、#132（欠損分だけの再取得）、#133（前日調教原本再利用）、#134（時計の別観測保全）、#130（独立クッション取得）、#131（既存日次handoffの独立クッション照合）、#152（調教新旧原本互換）はすべてmergedを今回直接確認。#154もmerged（skipと保存欠損区別）。
- 現main 1fed7e79796d91de76d2c5f85486f6625d69ef3f。調教pin 5855874f3f6dc9711d9b6f0444786ea2be0e05e7、クッション取得pin 47cd7f9e881aa989b9f932373cfaf5278dea223a、既存の日次クッション照合pin 301916719e5bc0e3a8e392368434f952c16c05db を実workflowから直接照合済み。#131の日次クッション照合はhandoff後に独立jobとして既に組込み済み。既存6取得workflow・設定は変更しない。
- 既存検証成果を再利用: #130の26/26、#131の8/8、#132の22/22、#133の6/6および実暗号化前日原本7/7、#134の17/17および実原本の39観測馬・417正規記録・21追加時計値、#152の47/47。今回PR記録で確認した過去の成果であり、無条件再実行や現開催の完全取得認定はしない。
- 実開催の残存事項: 調教 run 46112621733/job 140879308613 のログで現調教pin、19 snapshots、公式馬照合0・結合0Rを確認。公式出馬表との独立照合（P0-1優先）が必要。クッション値は既存の独立取得・日次照合を利用し、実際の公開時点・取得原本・発走前の各レース照合を確認する。#154で4件のskipを分類済みだが正当性は未認定。
- 最終総合検査（#148）の標準coverageには独立調教artifact/クッションsidecarを直接取り込まない設計が残る。既存の別系統証拠を正しく参照・照合できるかを確認し、実在する欠落だけを追加修正する。クッション日次機能を未実装として扱わない。既存sidecarを無用に再構築しない。SP構造証拠も別ledgerとして既存実装を再利用し、PC分母や市場証明と混同しない。固定18分類と追加証拠の区別、時点・原本・SHA・run ID・取消・未公表の区別を維持。
- P0-2の受入: 既存機能の本番保全、実データの認証と照合、最終総合検査への証拠反映を区別。問題がない既存部分に追加実装・再検査を要求しない。実データ完全取得は未認定。

### P0-3 取得から翌日改善まで最終横断検査
- 6取得workflowのexact pinと保護設定、native/externalの実起動、PC→SP、両市場AND、全馬、馬場、調教、夕方結果・払戻・訂正、暗号化保全、日次独立再解析、署名済みhandoff、次日適応を連携確認。
- 11/28の馬場HTTPErrorは旧URLのstatus不明。#158で観測済み正規公式URLへ変更、失敗status保存追加。旧障害の根本原因は未認定。明日の実取得成功は未認定。
- 固定25件（13 BLOCKER）を #116 と最新blobに対し根拠ベースで管理。CI全合格のみで閉鎖しない。自動改善は既知パターンへの限定適応・診断・証拠保全まで本番実装済み。任意の未知障害を自動特定修復した証明なし。
- 終業/節目の報告では完了・未完了・根拠・最新HEADと次の作業を明示。無意味な細切れ指示要求を避ける。

## 5. 予約枠（JST・変更禁止）
11/28: 朝09:15/10:15/11:05/11:50、午後12:30/13:30/14:30/15:30、19:00結果、21:00handoff、22:00訂正。調教11/27 20:30・11/28 07:30。
11/29: 朝09:15/10:15/11:10/11:55、午後12:30/13:30/14:30/15:30、19:00結果、21:00handoff、22:00訂正。調教11/28 20:30・11/29 07:30。日次検査11/28 16:15/22:40、11/29 16:15/23:40、11/30 08:10再照合。既存外部予備枠と連動調教・クッションを維持。Cloudflare直接ログ・設定の確認は未実施、時刻保証なし。

## 6. 恒久参照
- https://github.com/papaneko-ai/kyoto-keiba-ai/issues/141 (実障害・修正の全記録)
- https://github.com/papaneko-ai/kyoto-keiba-ai/issues/116 (固定25件)
- https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/46114223286 (最新点検)
- https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/46112551733 (午後補完)
- https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/46104526918 (11/29前日PC/SP 12R/151行一致のログ、原本再復号未確認)
- https://github.com/papaneko-ai/kyoto-keiba-ai/blob/f9022b2e4c8511aeb301cba4d5619317ea3a6726/docs/diagnostics/KYOTO_20261129_PREDAY_SOURCE_READINESS_IMPL37.json
- https://github.com/papaneko-ai/kyoto-keiba-ai/blob/f9022b2e4c8511aeb301cba4d5619317ea3a6726/docs/diagnostics/KYOTO_20261128_INCIDENT_LEDGER_IMPL37.md

## 7. 再開用短文
京都競馬AIの緊急改修を再開。papaneko-ai/kyoto-keiba-ai の handoff/emergency-current ブランチにある EMERGENCY_HANDOFF.md と Issue #141 の最新記録を読み、main・未完了PR・実行証拠を照合し、前回の続きから最終総合バグチェックまで進めてください。既存合意・承認手順を維持し、重要工程ごとにGitHubの再開正本を更新してください。

## 8. 作業中チェックポイント E37-158-02
- main 1fed7e79796d91de76d2c5f85486f6625d69ef3f の不変を再確認。
- P0-1の基準collector ba7d5bb4c05698dfb92119460b45e730b5eb512b。隔離作業ブランチ repair/impl37-cross-day-original-replay-20261128 を作成予定。既存の実artifact 15250785307を再利用し、旧版と修正版のG03/G06 adapter/日次集計の差を数値・安全な理由コードのみで比較する。既存のAES鍵はGitHub内の認証済み読取処理でのみ利用し、外部に出さない。JRA通信・本番変更なし。成功済みの検査の無条件反復なし。
- 状態: 着手前記録。候補の試験・承認・本番反映は未実施。

## 9. 作業中チェックポイント E37-158-03
- P0-1隔離候補 PR #159、HEAD c3b15355ba5a184e22cd87c34bc645538ce33200、基準 ba7d5bb4c05698dfb92119460b45e730b5eb512b、base repair/impl37-cross-day-original-replay-base-20261128。公式ホスト許容条件の4か所をG03の既存土日条件に整合。11/28・29の12R結合、プロフィール、両市場、誤ホスト/日付/経路/発走後の反例を追加。FMEAの対象3 blobを再開、リスク閉鎖なし。旧ホスト/他日/既存時点基準は維持。書込接続断1回後、旧HEAD確認し修正書込みを完了。
- 現時点CI: [{"id":46115187062,"name":"Nov22 keep saved official R1 and preserve AES/12R source checks","status":"in_progress","conclusion":null},{"id":46115187068,"name":"Kyoto Impl30 Nov28-29 offline release preflight","status":"in_progress","conclusion":null},{"id":46115187113,"name":"Nov22 independently observed SP anchor repair and AES guard","status":"in_progress","conclusion":null},{"id":46115187050,"name":"Nov22 actual official JRA mobile app host and full SP provenance","status":"in_progress","conclusion":null}]。実artifact 15250785307のAES認証・平文再解析は未実施。次は exact HEAD の既存offline preflight結果を読み、失敗原因を修正。実原本で直接原因を確認できる証拠を確保。承認済みmainへの反映は未実施。P0-2/3未完。
- main 1fed7e79796d91de76d2c5f85486f6625d69ef3f。本番取得・予約・Secrets/Turso・外部タイマーに変更なし。追加JRA通信なし。

- E37-158-03 追加確認: 隔離PR #159 CI 4/4成功。[{"id":46115187050,"name":"Nov22 actual official JRA mobile app host and full SP provenance","status":"completed","conclusion":"success"},{"id":46115187113,"name":"Nov22 independently observed SP anchor repair and AES guard","status":"completed","conclusion":"success"},{"id":46115187062,"name":"Nov22 keep saved official R1 and preserve AES/12R source checks","status":"completed","conclusion":"success"},{"id":46115187068,"name":"Kyoto Impl30 Nov28-29 offline release preflight","status":"completed","conclusion":"success"}]。本番main 1fed7e79796d91de76d2c5f85486f6625d69ef3f。P0-1は修正候補作成済み、実原本再解析と本番反映は未完。次の作業は最終CIログ照合と実原本の原因立証、必要な本番候補作成。P0-2/P0-3未完。

- E37-158-04: ユーザー指摘によりP0-2を訂正。前回の調教・クッション取得およびクッション日次照合は本番反映済み。追加作業を既存証拠の実照合・総合検査への参照確認に限定する。PR #159 はP0-1として引き続き隔離候補、main変更なし。

## 10. E38-159-01 再開・実原本比較着手（2026-11-28 JST）
- main 1fed7e79796d91de76d2c5f85486f6625d69ef3f、再開正本旧HEAD 7d621799e50eb3a293dd41cda0868169109bda0e、#141/#116の本文・全コメント、#159 HEAD c3b15355ba5a184e22cd87c34bc645538ce33200 を照合。#159 CI4/4成功、preflight job 140887300165 のexact checkoutと延べ818試験（410+11+135+39+80+44+79+20）成功をログ確認。成功試験の再実行なし。
- P0-1実原本: run 46112551733、artifact 15250785307、digest sha256:444a678b0c8a98f475b369bd3acd858b3be96e1adf64527bc8ca5f4adf780b2c、mainの正規午後workflowをAPIで照合。基準 ba7d5bb4c05698dfb92119460b45e730b5eb512b と#159 exact候補の独立同一原本比較を隔離PRで行う。既存AES鍵のGitHub内限定利用、原本/鍵/氏名出力なし、JRA通信なし。検査専用ブランチ repair/impl38-actual-aux-replay-base-20261128 / repair/impl38-actual-aux-replay-20261128 を予定。認証・G03・adapterの理由コード・日次coverage・夕方入力を個別確認。main/予約/Secrets/Turso変更なし。調教・クッション・日次統合は既存成果を再利用。固定25リスク0/25、最終検査未合格。

## 11. E38-160-02 実原本比較の隔離実行
- PR #160（診断専用、mainマージ禁止）、HEAD 9885c943716e23927a445f34e11d79e2b6db0f46、run 46115746435 / job 140889067752 を起動。原本run/ID/digest照合と同一暗号化artifact取得は成功。旧/候補の独立認証、G03・adapter・coverage・夕方補完の数値のみ比較中。鍵・平文はGitHub runner内の一時領域のみ、JRA通信なし。未完のため原因閉鎖なし。
- 本番候補の必要差分: #159を採用する場合、日曜朝・午後・結果・handoffの4pin、独立検査/診断readerのpin、exact preflight receipt (run46115187068/job140887300165/artifact15251670211/digest fc59b385e6e45d44d0392257568fb51b1a579221753144025a87752388842d48)、FMEA register blob 3acb52965375909ea97b50d7f37a7633bd5456d1 と検査契約のみ同期。土曜朝・調教・クッション・日次sidecar・予約等を維持。旧本番main 1fed7e79796d91de76d2c5f85486f6625d69ef3f。承認待ちのmain PRはまだ作成していない。

## 12. E38-160-03 NOV28-15 実原本による直接原因の立証（2026-11-28）
- 隔離PR #160 run46115746435/job140889067752 SUCCESS。artifact 15251442288 digest sha256:9dd7b5afc1b82916a49aa609216030bc2c378356937020f61ddbd6027167df7e。旧/新とも実原本15250785307をAES-GCM認証、同一ciphertext SHA256 6e207cbf1fd75acc846c351d9b8d8b549825bff203db8c20bbef26bc448fb2f4。G03は両版10R/11R検証。旧版adapterは両Rを race_spec_unverified:unverified_official_racecard_url で拒否、coverage 0R/0頭・postrace補完0R。#159 exact HEAD c3b15355ba5a184e22cd87c34bc645538ce33200 は両Rを復旧、coverage 2R/26登録馬・天候2R・postrace補完2R/seedあり。1〜9Rは両版発走後拒否、12Rは原本未検証。追加JRA通信0、鍵/平文出力なし。馬体重・両市場等は未取得であり全取得認定なし。
- 根本原因は旧G03と後工程4箇所の土日公式host条件不一致。#159の818回帰成功に加え、同一実原本で直接修正効果を立証。隔離修正済み、本番反映は未実施。次は本番候補作成・CI、exact HEAD承認。本番main 1fed7e79796d91de76d2c5f85486f6625d69ef3f 不変。固定25リスク正式閉鎖0/25。

## 13. E38-161-04 本番候補と追加同根障害（2026-11-28）
- #161 main候補 HEAD 40421a1709d15cfbfe6b229f0e0d02cca222f2ec (base 1fed7e79796d91de76d2c5f85486f6625d69ef3f), 11ファイルのpin/receipt/register/契約差分。8/8 CI成功: 46116104367,46116104426,46116104404,46116104456,46116104398,46116104437,46116104417,46116104376。未承認・未merge。
- ユーザーの14:56監視指摘を受け、既存調教版5855874f3f6dc9711d9b6f0444786ea2be0e05e7 の official() が同じadapterを使用し、ObservedRaceSpecのwww.jra.go.jp許可が11/29限定、market source chainにも同根の条件が残ることを直接確認。実調教artifact 15250370911 (run46112621733, digest e1d93ff1c0be9dda7b389359a628ba2f6941af49ae357f4be1e33262d07c85dd)、既存午後artifact 15250785307を再利用。調教は再開発せず既存2条件の差分と土日・実原本結合の回帰を隔離修正。予定branch repair/impl38-workout-same-root-20261128。馬体重・馬場の0件はG05 layout/実原本に別原因の可能性、G05 DOMを安全な件数/列情報だけ確認。native起動なし・外部直接証明未確認は別障害。固定枠・Cushion/Turso/Secrets変更なし。固定25リスク正式0/25。

## 14. E38-161-05 調教同根修正・既存原本比較の起動
- 既存調教pin 5855874f3f6dc9711d9b6f0444786ea2be0e05e7 から2箇所の同根公式host条件だけ修正し、土日・誤host/誤日・改ざん回帰を追加。隔離候補 bd800bc30db60919e274eadac419016c963e77de (repair/impl38-workout-same-root-20261128)。検証専用branch repair/impl38-workout-replay-20261128 HEAD 16f347d3a35c7833ab67e8f74f960432c02fbc45、run46116229567/job140890572809 起動。既存調教19原本と午後10/11RをAES認証し、保存済み原本だけで旧/新調教結合を比較。G05実原本の列構造・重量書式・観測値件数を値や馬名を出さず診断。追加JRA通信なし。CI/実再解析は実行中、まだ合格としない。
- #161は8/8 CI合格・mergeable=true。未承認。本番main 1fed7e79796d91de76d2c5f85486f6625d69ef3f 不変。#161の調教pinは未変更のため、追加修正の検証後に本番候補へ統合するか別exact PRを作成する。15:30枠を手動起動しない。native予約の未観測は別問題。

## 15. E38-161-06 調教実原本での同根障害解消・馬体重の独立診断
- run46116229567/job140890572809 SUCCESS。artifact15252176096 digest sha256:73ea992b95212a2865eb00a59088c45ae14728459fc09c597a696d71ad77afd3。追加回帰2/2（両日12R、wrong host/day、原本tamper）。旧/新とも19調教原本AES認証、拒否0。旧版roster 0R。候補bd800bc30db60919e274eadac419016c963e77de は10R15登録馬/118正規記録、11R11登録馬/155正規記録、全26登録馬照合、計273正規記録、別時計候補19群、prestart snapshot 7件。新規JRA通信0。調教取得/時計機能は変更せず2同根host条件のみ修正、本番未反映。
- G05同run独立再解析では10R/11Rの天候2件、体重0・増減0・馬場状態0。実DOMの表には独立体重列がなく th.horse に馬体重見出し、td.horse は名前等を含む複合セル。10Rの全15頭で数値状文字列は存在するが現時点で体重値と断定せず、11Rでは未公表/取消可能性。次は専用の子要素・数字書式・明示ラベルを安全な構造情報だけ抽出して最小修正。過去成績や斤量を体重に誤認しない。G05条件欠落は残存。
- #161 main候補の6取得workflow独立byte照合成功、4pin置換のみ、調教/クッション2本・日次クッションsidecarは完全一致。#161は8/8合格。調教の実証済み追加pin候補を統合してから最終HEADの承認を依頼する。main未変更、固定25リスク0/25、native起動未解決。 

## 16. E38-G05-07 NOV28-16 実DOMから馬体重・馬場の具体的原因を確定
- run46116349346/job140890948043 SUCCESS、artifact15252231098 digest sha256:88b2e0c26cbcb39925339415f92893917476c6f30cdfb28c13d8cb8e53f43992。元artifact15250785307を再認証。10Rの全15登録馬の th.horse に対応する td.horse > div.result_line > div.cell.weight に現在の体重/増減形式 NNNkg (+N/-N/N) が存在、子 span.transition。11Rの同要素は全行不在（取消1）。過去成績・斤量を誤認しない。芝状態は両Rの div.record_unit.mt30 > div.data > div.inner > div.cell.date > span に専用ラベル（芝：良形式）。旧G05は馬名複合セル全文をmass regexに掛け、当該芝状態の専用構造も見ていなかった。旧再解析天候2、重量0、増減0、芝0。次は exact source c3b15355ba5a184e22cd87c34bc645538ce33200 からこの構造のみ追加、未掲載/取消/紛らわしい過去成績・複数候補・時点不一致を負例で拒否。新しいG05候補とFMEA登録を作り、実原本差分・必要CIを検証。調教候補bd800bc30db60919e274eadac419016c963e77deは合格済み、クッションは維持。本番#161のHEADはまだ未承認・main未変更。

## 17. E38-MON-08 15:32緊急監視報告と新実原本を反映
- 自動監視最新run fc3ad96e-3868-832e-8f04-dda6a880ebb5（15:32 JST）を直接取得。既報の実原本10/11R・26頭・調教273件・G05構造原因と一致。15:30 native未確認、15:32:13 workflow_dispatch起動、Cloudflare直接ログ未確認。GitHub独立再照合では run46117060392/job140893135640 SUCCESS、旧本番main 1fed7e79796d91de76d2c5f85486f6625d69ef3f、artifact15252141771 digest sha256:e1d2c29a26b62adde8d743b9aee77aeae8cc071830f4fb586976fba0ebc44e1f。原本11R・observed_field_values=1（旧版）、15 HTTP。15:30原本はG05追補検査に追加。起動成功と全取得を区別。
- G05候補58a75eab856c4eb81f28bb48c8750d3caa382d54、preflight46116443971/job140891250118 SUCCESS（延べ821試験）、artifact15251538379。実原本比較run46116472162/job140891340049はFAIL：体重15/15・増減15/15復旧、天候2R、計32値、ただし芝状態0Rで期待34値に未達。証拠artifact15251219863保存。これは模擬合格でも実原本未達が残るため全合格としない。次の候補は両時刻の認証済み原本で芝header正確形式を特定、未掲載値を捏造せず体重と日次統合を確認。#161・調教候補未merge。本番承認手順維持。

## 18. E38-MON-09 新15:30枠の連動調教と馬場誤認防止
- 連動調教run46117133457/job140893359650 SUCCESS、artifact15251809142 digest sha256:d127b97c256ecc0684b1e5d01563bd665ee2789932f2b299d3e911e504ee7、旧本番main。19原本、照合0R/0頭、2 source requests。既立証の調教reader同根修正を優先し、再開発しない。
- 馬場のレコードタイム欄を現況と誤認する懸念があるため、G05候補58a75eab856c4eb81f28bb48c8750d3caa382d54の追加selectorを未承認のまま保留。15:30新原本と14:30旧原本の両方で現在/過去の構造を独立確認する隔離run46118281957/job140896886286（HEAD c032696dda0b72b2e1b124826f7294ce5f975e2b）を開始。JRA追加通信なし。結果が出るまでは芝状態の回復を主張しない。主修正と調教候補の実証は再利用。現在の取得済み証拠・固定25リスク・本番承認ゲートを維持。

## 19. E38-MON-10 15:30追加実原本で非取消25頭の馬体重・増減を全復旧
- run46118281957/job140896886286 SUCCESS、artifact15252846663 digest sha256:6d7edef10a8a9de3f6575b0da405c1d87f44b6ef4437d2e1a340ebda29a64129。旧14:30原本10R 15頭、新15:30原本11R 10頭で各重量/増減25値、計50値、非取消分25/25。既存の日次unionでracecard2R/26登録馬・天候2R・重量25・増減25を独立確認。14:30の11Rに無かった重量要素は15:30原本で10頭掲載、取消1を未知扱い維持。追加通信0。
- 訂正：先のレコード欄は div.record_unit の見出し「レコード」配下の晴/芝：良（過去記録時）であり当日馬場ではないことを実証。58a75eab856c4eb81f28bb48c8750d3caa382d54のそのselectorを撤去し、過去条件を明確に拒否する負例へ変更する。両原本の別独立馬場ページは正しい同日見出しを認証済み、SAME_DAY_KYOTO_SOURCE_SAVED_FIELDS_UNVERIFIED。保存済み新馬場HTMLの実構造を調べるrun46118361838/job140897139200（HEAD332d6dff0b06e1c5f3867bdab9c273a0c6748c63）を開始。再開時はその結果を使用して必要最小限の修正。現時点で芝・ダート状態の回復を主張しない。調教候補bd800bc30db60919e274eadac419016c963e77deと#159実証結果は再利用。main未変更・承認待ち・固定25リスク0/25。

## 20. E38-TRACK-11 馬場公式原本の観測日時不一致を特定
- run46118361838/job140897139200 SUCCESS、artifact15252697157 digest sha256:ce51085e47a24098eb0681107b20963c7d1f3e1e45d46145c97968fd1f473840。15:30原本の開催見出し11/28は正しいが、div.line.condition > h3 の明記は「馬場状態（11月27日（金曜）正午現在）」で前日。現行parserは4含水率を抽出するが、測定日時欄は「測定時刻 変更」だけで日付不明。過去/当日の取り違えを防ぐため条件・含水率各観測日時を独立判定し、日付未証明の含水率は観測値として別保全・当日coverageには加算しない。現在日と明示時刻の一致、未来時刻・前日・複数候補・過去レコード・欠落の負例を追加。実際の重量25/25、調教26/26、既存#159修正は再利用。クッションpin・日次sidecar・予約枠不変更。mainは1fed7e79796d91de76d2c5f85486f6625d69ef3f、#161未merge。
