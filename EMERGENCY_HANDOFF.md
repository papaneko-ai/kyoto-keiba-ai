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

## 21. E38-SELF-12 自己修正の実稼働監査・未検知障害（2026-11-28）
- 本番main 1fed7e79796d91de76d2c5f85486f6625d69ef3f の自動障害診断は15:30枠後のrun46117133442（午後補完）、46117138094（クッションskip）、46117216127（調教）で各offline/diagnose/publish全成功、#141の自動コメント7235373154/7235373268/7235385887を確認。調教は欠落検知のみで原因未立証。午後補完は旧診断が『診断対象の欠落未検出』と誤表示。inspect_sourceのauxiliary条件がverified_racesの非空とtrack_observed（任意1項目、観測日未検証）だけを要求するため、部分出馬表・馬体重欠落・古い馬場条件を見逃す。これは今回の実原本比較で確認した追加の重大診断欠陥で、G05日時判定と同時に独立項目別・レース/馬別の欠落検知を修正対象とする。
- #146の限定HTMLナビゲーション候補修復と翌日bounded policy選択機構は本番コードに存在するが、今回の未知の日付制約・重量DOM障害の自動コード修正は未実証。今回の実原本修正はChatGPTによる隔離修正であり自己修正の成功に計上しない。次回自動policyの実適用証拠も未確認。現行診断workflowはcontents:read、publishのみissues:write、候補patch生成/CI起動/承認付きリリースへの自動接続なし。診断成功≠自己修正成功。固定25リスク0/25のまま。次の工程は自動診断の偽陰性修正、原因から隔離候補/回帰/証拠までの自動接続、既存承認手順を保持。main変更なし。

## 22. E38-SELF-13 緊急対応後の固定工程（ユーザー指示）
- 11/29全取得の緊急改修・本番反映・独立検証・最終総合バグチェックを優先。次の開発工程として未知障害の自己修正機能の本格改修を必須化。未知障害を入口に証拠収集、仮説と反証、同根横断探索、隔離候補の生成、実原本・負例・回帰、承認付き本番反映、独立再確認まで接続する。既知ルール適用や台帳記録だけを完成としない。今回の4種の実障害を既存証拠から受入試験に再利用し、手動修正を自動成功に算入しない。未知障害が必ず修復可能との保証は別。診断の偽陰性対策は緊急取得に直接必要な範囲を優先し、本格的な自律コード修正は緊急改修後。固定枠・Secrets/Turso・承認手順・固定25リスクを維持。

## 23. E38-RELEASE-14 緊急統合候補の最終CI・承認待ち（2026-11-28）
- 緊急改修後の自己修正工程は§22のとおり固定。Collector c289c5ec4e6ad322a7e08acf173da3352ed23dba（隔離PR #162）、preflight run46119675702/job140901194619、artifact15252869150 digest sha256:0e2e513d9bb27c49fc03355ceb5dc2daf16f5b016db12d7122f033ffea90c710、822/822成功。実原本run46119693917/job140901252131、artifact15253550662 digest sha256:7d755aa11762e14bb98f8a165a41ab267aa319d574a90441be2b087bd65c94bc、14:30/15:30合計26登録馬、非取消25頭の馬体重・増減25/25ずつ。過去レコード天候・馬場及び11/27観測値は当日値から排除。当日の天候/芝・ダート状態は未確認、日時不明の含水率4値は各原本で別保全。G05の初回3fixture失敗は測定日時のない陽性fixtureに起因、明示日時付き陽性・未記載陰性・複数/時刻不一致を回帰で確認、最終822/822。調教bd800bc30db60919e274eadac419016c963e77de、実原本run46116229567、19原本・26頭・273記録、2/2回帰を再利用。JRA追加通信0。
- 本番統合PR #161 最終HEAD 0fd0d079d60704d3c35fe52d565b272cf3f267d8。初回調教契約が旧基準pinのため失敗したことを記録し、厳格な完全差分・予約・権限の条件は維持したまま現行main基準へ同期。PR証拠欄の必須3見出し欠落も修正。最新の各9種CIは全成功: 46119957839,46119910308,46119910387,46119910296,46119910305,46119910328,46119910316,46119910391,46119910344。5本の本番workflowを現行mainからの指定SHA置換のみと独立全文照合（5/5）、変更13ファイル、クッションsource/sidecar・Secrets/Turso/Cloudflare設定変更なし。main 1fed7e79796d91de76d2c5f85486f6625d69ef3f 不変、未承認・未merge。次はユーザーによるこの正確なHEADの承認→main反映→独立検証→残る緊急診断偽陰性/起動・総合検査。固定25リスク正式0/25、native予約・11/29全取得未証明。手動修正を自己修正の成果に算入しない。

## 24. E38-MERGE-15 PR #161承認済み本番反映
- ユーザー明示承認 HEAD 0fd0d079d60704d3c35fe52d565b272cf3f267d8、最新9種CI合格とbase 1fed7e79796d91de76d2c5f85486f6625d69ef3f を再照合して exact-head merge。main e67174543189dea1faafbbba2a6ba383f52377d8、merge parents旧main/承認HEAD、tree 49e6b306e4eb899418f165eece63fc0f42fec0b2 が承認HEADと完全一致。独立再取得でPR merged/main一致。新しいmain push独立総合検査run46120092162起動。未確認のnative起動・実取得・固定25リスクを閉鎖しない。既存予約・Secrets/Turso/Cloudflare/クッション維持。次は独立検査結果、緊急診断偽陰性、残存起動・取得障害対応。自己修正本格化は緊急後工程。

## 25. E38-MERGE-16 独立検査完了・残存診断候補
- main e67174543189dea1faafbbba2a6ba383f52377d8 の自動独立検査run46120092162、test140902490790/review140902516306/publish140902710851全成功、artifact15253391023 digest sha256:009f4cf357a2f15a42db77a7d8b8259b4dc2971de0ee2cd4bc11175e1f27d5ca。index errors0、28 source runs、13 native slots、固定25行、replay errorなし。出馬表2/12、登録26、馬体重/増減25ずつ、10R分の分母未知。天候/馬場/含水率・両市場・プロフィール等0、現時点の結果/払戻0。調教は別の実原本再生で26頭273件を実証しているがこの日次集計では0（独立の連結不足を別残存課題とする）。全取得・リスク解消認定なし。
- 旧診断偽陰性対策を隔離PR #163 HEAD d7a910a888480bb8c21d04f9dbe0358d2d3c2809に実装。既存exact reader c289c5ec4e6ad322a7e08acf173da3352ed23dba によるJRA通信禁止・鍵非継承の子プロセスでG03/G05を再解析。午後のtarget_races範囲とPCの12R範囲を区別、原本未確認・非取消馬ごとの体重/増減・現在の馬場・日時不明含水率を診断。未公表/欠落≠根本原因確定。固定枠・取得器・クッション・Secrets/Turso/Cloudflare変更なし。隔離actual proof branch repair/impl38-incident-g05-actual-proof-20261128 HEAD73fc1f212d3df12bd6f38e532f1644326ed8b550 起動。CI/実原本比較確認後にexact承認。現状run snapshot [{"id":46120300465,"name":"Impl38 independent incident G05 actual false-negative replay","status":"in_progress","conclusion":null,"head":"73fc1f212d3df12bd6f38e532f1644326ed8b550"},{"id":46120269257,"name":"Kyoto reuse verified work before new development","status":"completed","conclusion":"success","head":"d7a910a888480bb8c21d04f9dbe0358d2d3c2809"},{"id":46120269229,"name":"Impl26 Nov21 protected production pin offline release gate","status":"completed","conclusion":"success","head":"d7a910a888480bb8c21d04f9dbe0358d2d3c2809"},{"id":46120269223,"name":"Kyoto automatic incident evidence and repair worklist","status":"completed","conclusion":"success","head":"d7a910a888480bb8c21d04f9dbe0358d2d3c2809"}]。

## 26. E38-DIAG-17 偽陰性修正を実原本で確認・承認待ち
- #163 exact HEAD d7a910a888480bb8c21d04f9dbe0358d2d3c2809 / main base e67174543189dea1faafbbba2a6ba383f52377d8、mergeable=true、最新3/3 CI成功:46120269257,46120269223,46120269229。実原本run46120300465/job140903127598 SUCCESS、artifact15253930656 digest sha256:b95f5c2ec3e53ca49df683fb942a76f49253b6a19b4e058924f035dba4b87b72。14:30/15:30同一既存原本を認証、exact deployed readerで独立解析。両枠ともAUXILIARY_SOURCE_FIELD_GAPS、7 course field gaps、14:30は11R非取消10頭重量/増減未掲載、15:30原本では同10頭の両重量項目復旧を認識、取消9番を欠落に数えず。12R未検証・発走後対象の未取得などは欠落/未認定として記録し、原因確定や全取得扱いはしない。JRA追加通信0。変更4ファイルは診断・テスト・診断triggerのpath追加のみ。収集器・予約枠・クッション・Secrets/Turso/Cloudflare不変。ユーザーによるexact #163承認を待つ。
- 本番総合点検#141 comment7235793280: 当日午前4+午後4の8 native slots全て未観測、外部形式dispatchで各4実行を確認。夕方以降はこの点検時点未到来。外部provider直接証拠未確認。固定25リスク正式0/25。別に日次調教独立集計の不足（実原本26頭273件を再利用）を緊急残存として管理。本番main #161反映済み。未取得・実行未到来・検査不備を区別し、自己修正本格工程は§22から再開。

## 27. E38-MERGE-18 PR #163本番反映と遅延native実証
- ユーザーの明示承認 exact HEAD d7a910a888480bb8c21d04f9dbe0358d2d3c2809、最新CI3/3および実原本46120300465再照合後、main 8ac33226488157759c1b919efa100da427358a4d にmerge。独立API再取得でPR merged、main一致、承認tree/本番tree 399d4508d191b66765253b39434dafa6841eb96c完全一致、parents旧main e67174543189dea1faafbbba2a6ba383f52377d8 と承認HEAD。取得器・固定予約・クッション等変更なし。残存日次調教集計へ進む。
- 新規実証: 11/28 09:15 JST native予定のrun46122141318が16:38:29 JST（7時間23分29秒遅延）にscheduleイベントで実際に起動。PC job140908775524/SP job140908811758双方、OUTSIDE_DAY_WINDOW_NO_HTTPを実ログで確認、取得stepはskipped。これはnative未観測から遅延実証への更新であり、正しい時間帯の取得成功ではない。終了済みレースの事前情報として誤取得する時刻制限は維持し、外部予備起動の成功経路に依存するリスクを別管理。Cloudflare直接証拠は未確認。明日nativeを待つ運用に戻さない。固定25リスク独立閉鎖0/25。

## 28. E38-WORKOUT-19 日次調教統合の実原本合格・承認待ち
- 前回中断時のbranch fix/impl38-day-workout-independent-20261128 に候補 78c555d15ab8c58fb2d7277f161bdf68547ee3dc (parent main 8ac33226488157759c1b919efa100da427358a4d, tree 713d230d9bfd1438ccf92425e49e6ce3f01c7516) が保存済みだったため再開。PR #164 作成。3/3 CI成功: 46124353792,46124353541,46124353363。変更4ファイルは独立日次検査workflow、調教再解析helper、総合検査本体、テストのみ。6本の本番取得workflowのblobと全文、予約枠・collector/調教/クッション/クッション日次pinがmainと完全一致。PR mergeable=true、main不変。
- 実原本検証用branch repair/impl38-workout-day-proof-20261128 HEAD7607d2554943ec2226321f30ed1cdf1f8f8df22d、run46124391613/job140915634376 SUCCESS、artifact15254866978 digest sha256:e7d15705e031cba6120306d27e7cdbdf7c07d83fe42e4ce7d35e62c2eb4a5f9b。14:30/15:30の公式原本と、本番調教run46122176100 artifact15254361059 (sha256:c8c032bd0825607d3528981a6d002847ab30f2a727505fc17a99ba805510c41d) のexact ID/digestを照合、暗号認証19/19、独立再解析の対象7snapshot、10R/11R全26頭、正規273記録。日次coverageの調教0/26→26/26、他の項目はすべて同一、未確定分母10R、source HTTP0、誤run/roster拒否。取得器の再開発なし。ユーザーによる#164 exact HEAD承認前はmergeしない。
- 本番調教の同root修正の実稼働: run46122176100/job140908864878、pin bd800bc30db60919e274eadac419016c963e77de、19 snapshots、2 joined races、26/26 horses、source_requests=2。クッションも本番run46122176181/job140908864768のOFFICIAL_ORIGINAL_PARSED (1 request)、artifact15254316668 sha256:ccd922a4843f3651246c1cd8c69c31a57217f7d65287427a83b0e7857b36d271、診断#141 comment7236084547の認証済みを確認。既存クッション日次sidecarは維持、全レース当日・発走前測定値の認定ではない。
- #124の過去成功証拠を再利用し訂正: comment7211044634は11/27 A2の2件custom HTTP204 provider→GitHub照合、comment7211071649は11/27 12:32 no-op (NO_MATCHING_SLOT) custom log実証済み。無条件の再実験や同証拠の要求は禁止。今回未確認なのは11/28の本番dispatchのCloudflare直接ログと11/29実起動。恒久外部タイマー改修は全取得後という既存方針維持。native7時間超遅延は§27。#163のmain actual新規診断起動は未確認、構成同一・過去実原本合格は確認済み。固定25リスク0/25。次は#164承認、merge後に本番総合検査、残存SP/クッションsidecar・当夜結果/払戻・翌日適応の現行連結確認。未取得を成功扱いしない。自己修正本格化は緊急後。

## 29. E38-MERGE-20 PR #164承認済み反映
- ユーザー承認 exact HEAD 78c555d15ab8c58fb2d7277f161bdf68547ee3dc、CI3/3・実原本46124391613再照合後にmain 1f43aa440f14e91e1aadf08dd428cbcb3c596c4f へmerge。独立API再取得でmain/PR merged一致、承認treeと本番tree 713d230d9bfd1438ccf92425e49e6ce3f01c7516 完全一致。parents旧main 8ac33226488157759c1b919efa100da427358a4d と承認HEAD。6本取得workflow・予約・クッション・Secrets/Turso/Cloudflare無変更。本番push総合検査run46124607021起動、結果を確認。次はSP/クッションの独立証拠接続・当夜結果/払戻・翌日適応の残存リスク。固定25リスク0/25。

## 30. E38-CANCEL-21 本番独立総合検査完了・取消馬集計の追加候補
- #164反映後 main 1f43aa440f14e91e1aadf08dd428cbcb3c596c4f の独立総合検査run46124607021、test140916328697/review140916354134/publish140916664222全成功。artifact15254988581 digest sha256:342f07b03e92f2dc249c859b2e09a287952ae21603f31a2faef585171a52ac11、#141 comment7236433680。31 source runs、13 native slots、25固定リスク、原本再検証errorなし。調教13 archives・247認証snapshots・273正規records、index_complete=true、26/26（10R分の登録馬分母未確定）、体重/増減25/26。前回調教の日次欠落は本番検査で解消。native1枠大幅遅延失敗、午前残3・午後4 native未観測、結果/払戻・21:00引継ぎ未到来。出馬表2/12、両市場・プロフィール・当日馬場等0、固定25リスク正式0/25。
- 体重2項目の分母に公式取消馬を含めていた最終検査側だけの偽欠損を修正した候補 #165 HEAD 8d8a7e533215ee1e77da5bde22de6c5d86ca5022 / base 1f43aa440f14e91e1aadf08dd428cbcb3c596c4f、CI3/3成功 46124843915/46124843950/46124843953、mergeable=true。選択された発走前原本のrun/SHA/UTC/登録馬digestを既存exact G03 verifierで再照合し取消馬を体重と増減のみ対象外にする。登録馬分母・他項目不変、証拠不足時は除外しない。実原本proof run46124861594/job140917122214 SUCCESS、artifact15254819231 sha256:cf9122067fd0685b921e3dcf0312850c2b27a4b8ec808cd2a4c821f500d78187、10R取消なし・11R9番取消1、体重・増減25/25、10R分母未知、replay errors0、source HTTP0。承認前merge禁止。
- 11/29前日公開ソース証拠 docs/diagnostics/KYOTO_20261129_PREDAY_SOURCE_READINESS_IMPL37.json を再利用。11/28実観測PC/SP全12R・151登録行一致、結果/払戻メニュー各1。前日出馬表の確認であり日曜の発走前データ取得・オッズ・当日取消等の保証ではない。日曜選択器のexact deployed receipt（collector c289c5ec4e6ad322a7e08acf173da3352ed23dba/822回帰）と固定pinを確認。今夜の結果取得・署名済み翌日適応の接続は存在、実動作は時刻未到来。追加点検: 土曜保存済みseedがwww originである場合に旧originが固定される可能性を、実原本導線で切り分ける。確定前は障害認定しない。

## 30. E38-HANDOFF-21 実装38終了・実装39再開正本（2026-11-28 17:14以降 JST）
ユーザー指示: きりの良いところでGitHubに記録しセクション移動。ここで新規改修を止め、承認待ちPR #165を再開ゲートとする。最新mainを再取得してから進む。過去成功の再開発・再試験を禁止し、今回の実原本とCI証拠を再利用する。
- 本番main 1f43aa440f14e91e1aadf08dd428cbcb3c596c4f。#161/#163/#164は明示承認済み・merge済み。#164の本番総合検査 run46124607021、test140916328697/review140916354134/publish140916664222 全成功、artifact15254988581 sha256:342f07b03e92f2dc249c859b2e09a287952ae21603f31a2faef585171a52ac11、#141 comment7236433680。31 source runs、13 native slots、25 risk rows、index/replay errorなし。調教13 archives/247 authenticated snapshots/273 canonical records、index_complete=True、26/26（10R/11Rのみ）。馬体重/増減25/26、取消1。出馬表2/12、10R分の登録馬分母未確定、両市場/プロフィール/過去成績/当日馬場・含水率の認定0、結果払戻は検査時点で予定枠未到来。固定25リスク独立閉鎖0/25。
- 新規候補 PR #165 exact HEAD 8d8a7e533215ee1e77da5bde22de6c5d86ca5022、base 現main、mergeable=true、未merge・未承認。変更2ファイル diagnostics/kyoto_weekend_closure_review.py と tests/test_kyoto_weekend_closure_review.py のみ。既存のG03独立原本検証を再利用、取消状態を選択出馬表のrun/SHA/UTC/roster/startに結び付け、公式取消馬について馬体重・増減のみ対象外とする。登録馬・調教・プロフィールその他の分母を変更しない。未証明の取消や不一致は対象外にしない。CI3/3 SUCCESS 46124843950,46124843953,46124843915。隔離実原本 run46124861594/job140917122214 SUCCESS、artifact15254819231 sha256:cf9122067fd0685b921e3dcf0312850c2b27a4b8ec808cd2a4c821f500d78187。11R馬番9のみ取消、10R取消なし。馬体重・増減とも25/26→25/25（対象外各1）、10レースの未知分母は維持、他項目不変、誤SHA拒否、source HTTP0、replay errors0。本番取得器・予約枠・Secrets/Turso/Cloudflare・調教/クッションpin不変更。次セクションで明示承認を得てexact HEADをmergeし独立確認する。承認を自動で推定しない。
- 夜間処理のコード照合: 現mainの結果・払戻取得は19:00/22:00 JST、引継ぎは21:00 JST。collector c289c5ec4e6ad322a7e08acf173da3352ed23dba の postrace_runtime は allow_missing_seed=True、欠落rosterでも公開ホームから観測したリンクで結果原本を保存する経路あり。照合不能な原本を確定結果/発走前証拠にはしない。翌日適応は認証済みhandoff優先、18秒内の並列metadata fallback、既存実証された11/28 4件の障害IDからMARKET_OR_ROSTER_RECOVERYを選ぶ経路あり。実際の今夜の成果・11/29適用は未確認。SP構造証拠は別ledger、クッション日次sidecarは既存実装・pin301916719e5bc0e3a8e392368434f952c16c05db維持。全取得の総合検査で両者の独立証拠が正しく接続されるかは残存確認事項。既存成功を捨てない。
- 次の優先順: ①#165承認・反映・独立検査 ②11/29全取得を妨げる残存重大障害（PC/SP補完、当日馬場/含水率、馬連/枠連、profile/過去成績、外部起動、当夜結果/払戻/翌日適応、SP/クッション証拠集計）を固定リスク台帳と最新runに照合。特にnativeの7時間23分29秒遅延は§27の既証拠を使用し、外部予備起動を維持。夜間枠・明日の実行が到来していなければ未到来と区別。必要な修正だけ隔離→証拠→承認→merge→独立検証。③最終総合バグチェック。固定25リスク分母・正式0/25を勝手に変更せず、未取得/未認定を成功扱いしない。④緊急改修後に§22の未知障害対応型自己修正機能の本格改修を必須工程として実施。途中の重要節目で正本と#141を追記、#116にも固定リスク進捗を反映。
- 移行方法: スマホで新チャット「京都競馬AI開発・実装39（緊急改修継続）」を作成し、この正本§30と#141・#116、#165、現行mainを直接取得する指示で再開。GitHubに保存済みのコード・証拠を使用するため、この緊急移行ではZIP添付を必須としない。ただし完全移行パックを作成・検査したことを意味しない。ユーザー手動操作は最小化する。

## 31. E39-165-01 実装39再開ゲート（2026-11-28 JST）
- 第30節、第22節、#141本文・62コメント、#116本文・40コメント、現mainを照合。main 1f43aa440f14e91e1aadf08dd428cbcb3c596c4f、#161/#163/#164はmerge済み。#165はopen・mergeable・未承認、HEAD 8d8a7e533215ee1e77da5bde22de6c5d86ca5022、baseは現main。既存CI3/3成功（46124843950/46124843953/46124843915）をAPI確認、実原本proof run46124861594/job140917122214の既存ログでexact checkout、10R取消なし・11R9番取消1、体重・増減とも25/25、未知分母10R、replay errors0、source HTTP0、artifact15254819231 digest sha256:cf9122067fd0685b921e3dcf0312850c2b27a4b8ec808cd2a4c821f500d78187を確認。成功済み試験の再実行なし。
- ここまで再開ゲートの照合のみ。本番main・取得器・固定枠・Secrets/Turso/Cloudflare・調教/クッションpin変更なし。#165の明示承認を得た後にexact HEAD反映・変更範囲の独立検証を行う。全12R完全取得は未認定、固定25リスク0/25（13 BLOCKER）。
- 11/29全取得の最優先順序は第30節を維持。SP/クッション既存証拠の接続、PC/SP両市場・全馬プロフィール/過去成績・当日馬場/含水率、外部予備起動、夜間結果/払戻と翌日適応を重点確認。夜間枠の未到来を失敗と扱わない。緊急改修・最終総合検査の後、第22節の未知障害自己修正本格改修を必須工程とする。既存承認手順を省略しない。

## 31. E38-EVENING-22 結果・払戻の実原本origin修正と最終統合承認待ち
- 実原本診断 run46124993198/job140917511556 SUCCESS、artifact15255378037 sha256:2eb019bb4af96fa594085304bceb921d3fcb04020ff67a63ed6ec542cfb88ed6。保存済み15:30の11R原本のsource_urlは www.jra.go.jp、旧土曜runtimeの固定jra.jp originでは結果/払戻各1のPOST先が異なることを実証（実HTTP失敗は未観測）。隔離修正source b800308169173d9e82cf93db9bf7b381e361cc76 は独立G03認証済みseedのsource_url/host/SHAに束縛し、束縛不能時に既存公式homeを使用。日曜公式home・16+1リクエスト枠・時刻・拒否・暗号化条件維持。実原本再現 run46125110577/job140917872468 SUCCESS、artifact15254774632 sha256:3906d9a53a33bc5a65963291da520343e6306737369ddf36e296aa89d0f76eb0、11R保存seedから結果・払戻POST各1ともwww.jra.go.jp、誤origin拒否、追加JRA HTTP0。exact source preflight run46125076900/job140917776803 SUCCESS 822回帰（412+11+135+39+82+44+79+20）、artifact15255148992 sha256:70ea6157965db091634235993e5aff21feca325908ce7d0d4caaa4e4a6530974。
- 取消馬集計候補8d8a7e533215ee1e77da5bde22de6c5d86ca5022に結果・払戻pin修正を統合。PR #165 最新承認対象HEAD ff6807a575212fa86cb1ed0f1e547f846ccf8c75、tree ad23ae0afe40f64b732961297a651971403ee059、base main 1f43aa440f14e91e1aadf08dd428cbcb3c596c4f、未承認・未merge。最新5種CI全合格 46125200653/46125176435/46125176484/46125176402/46125176403。6本の取得workflow全文独立照合: postraceだけexact pin2箇所 c289c5ec4e6ad322a7e08acf173da3352ed23dba→b800308169173d9e82cf93db9bf7b381e361cc76、他5本完全一致。変更5ファイル、予約8枠/外部予備/Secrets/Turso/クッション/日次sidecar不変。PR #165は旧HEADではなくこのexact HEADのみ承認依頼。#164本番反映・独立総合検査3/3成功済み。19時結果/払戻・21時引継ぎ・22時再確認と11/29実取得の未確認を維持。固定25リスク正式0/25、native起動遅延、自己修正本格化は緊急後。再開時は#165承認状況とmain照合、承認された場合のみmergeし独立検証、実行結果確認へ。既存成功試験・実験の重複禁止。

## 32. E39-165-02 承認対象HEADの移動検出・夜間取得修正の独立照合（2026-11-28 JST）
- ユーザーは旧exact HEAD 8d8a7e533215ee1e77da5bde22de6c5d86ca5022 の本番反映を明示承認。しかしマージ直前の独立API照合で #165 のHEADが ff6807a575212fa86cb1ed0f1e547f846ccf8c75 に移動していたため、既存承認境界に従いmerge呼出しを行わなかった。main 1f43aa440f14e91e1aadf08dd428cbcb3c596c4f 不変。変更主体や並行更新の原因は未確定。旧候補の取消集計2ファイルと検証はそのまま継承され、追加1commit/3ファイルは夜間結果・払戻workflowのcheckout/HEAD検査pin、deploy contract、既存pinテストのみ。候補の全差分5ファイル。
- 旧実原本診断 run46124993198/job140917511556 の既存ログで11Rの保存出馬表実origin www.jra.go.jp に対し旧版結果・払戻の相対POST先が jra.jp になる不整合を確認。実際のHTTP失敗の立証ではない。新postrace source b800308169173d9e82cf93db9bf7b381e361cc76 は旧 c289c5ec4e6ad322a7e08acf173da3352ed23dba の直系1commit、postrace runtimeとテスト2ファイルのみ。独立認証済みG03 URL、SHA256、run/raceを使用し保存seedのoriginを検証、証拠不足は既存公式home fallback、11/29公式home経路維持。現行収集器・朝午後・調教/クッション・固定予約・Secrets/Turso/Cloudflareは変更しない。
- 新sourceの既存実原本 run46125110577/job140917872468 のexact checkout・成功ログを独立照合。結果/払戻ともPOST www.jra.go.jp、誤origin拒否、source HTTP0、artifact15254774632 digest sha256:3906d9a53a33bc5a65963291da520343e6306737369ddf36e296aa89d0f76eb0。既存preflight run46125076900/job140917776803、412+11+135+39+82+44+79+20=822試験全合格、artifact15255148992 digest sha256:70ea6157965db091634235993e5aff21feca325908ce7d0d4caaa4e4a6530974。新#165 HEADのCI6/6成功（46125200653,46125176435,46125176501,46125176484,46125176402,46125176403）、mergeable=true、base現main、open。既存成功の再実行なし。
- 次のゲートは新HEAD ff6807a575212fa86cb1ed0f1e547f846ccf8c75 に対する明示承認。旧承認を新差分へ流用しない。反映後の独立検証、残存緊急改修、最終総合検査は未完。固定25リスク0/25維持。19:00/22:00結果・払戻、21:00引継ぎの実行結果は未確認。自己修正本格工程は§22を維持。

## 33. E39-MERGE-03 PR #165最新版の本番反映（2026-11-28 JST）
- ユーザー明示承認 ff6807a575212fa86cb1ed0f1e547f846ccf8c75、CI6/6・base main 1f43aa440f14e91e1aadf08dd428cbcb3c596c4f 一致のうえexpected_head_sha付きmerge成功。新main d6db3de1c9f37622128454f47a615f6a433e0750、独立再取得で#165 merged/main一致、git tree ad23ae0afe40f64b732961297a651971403ee059 が承認HEADと完全一致。merge parentsは旧mainと承認HEAD。旧mainからの差分は承認5ファイルのみ（結果払戻workflowの2pin、deploy contract、pin test、取消集計とテスト）。本番収集器の他lane、固定枠、Secrets/Turso/Cloudflare設定変更なし。
- pushによる本番独立総合検査 run46125712697 を確認、現時点in_progress。結果確認後、残存するSP独立証拠/クッション日次sidecar集計、夜間引継ぎと翌日適応などを優先。固定25リスク独立閉鎖0/25。自己修正本格化は§22の後続必須工程。

## 34. E39-SUPPLEMENTAL-04 PR #165反映後検査完了・SP/クッション既存証拠の接続候補（2026-11-28 JST）
- main d6db3de1c9f37622128454f47a615f6a433e0750 の本番自動独立検査 run46125712697、test140919736344/review140919762822/publish140920070746 全成功。artifact15256055433 sha256:7ef777547cac61d5dad94e02a2ac81269c546bbac40b3a66b6a5a17448d87409。31 source runs、13 native slots、25固定リスク、index/replay errorなし。馬体重・増減25/25、調教26/26、出馬表2/12R、10R分母未知。馬連・枠連・プロフィール・過去成績・当日馬場/含水率の認定0、結果払戻は予定枠未到来。公式取消に関する#165本番修正効果を確認。正式リスク解消0/25。
- 残存の総合検査統合不足を隔離PR #166へ。exact HEAD f4da936dbcaec79f3a0b3ea757f74acad12d6296、base d6db3de1c9f37622128454f47a615f6a433e0750、mergeable=true、未承認/未merge。変更4ファイルのみ: diagnostics/kyoto_day_supplemental_replay.py、diagnostics/kyoto_weekend_closure_review.py、tests/test_kyoto_weekend_closure_review.py、総合検査workflow。既存SP独立再解析/aggregate（c289c5ec4e6ad322a7e08acf173da3352ed23dba）、既存クッション原本replay/combine（301916719e5bc0e3a8e392368434f952c16c05db）を再利用。別ledgerのまま、原本未認証・skipと実取得を区別し、SPをPC分母/両市場/発走前証明へ昇格させない。固定18分類・固定25リスク・6本取得workflow・予約枠・Secrets/Turso/Cloudflare変更なし。
- exact #166 CI: closure run46125994656（21 tests PASS、追加2試験含む）、protected pin gate46125994764 SUCCESS、reuse gate46126053127 SUCCESS。初回reuse gate46125994672はPR説明の必須見出し不足で失敗、説明のみ修正し同HEADの最新gateで合格。初期隔離コミット2a953949294877c55f670eb46e90afff50f47906のf-string引用符を修正して上記最終HEADとした。本番未反映。既存成功試験の無条件反復なし。
- 新規統合の実原本proof専用branch repair/impl39-supplemental-original-proof-20261128、HEAD87dac11406f1cc0357cf3ecce023cada6d156233、run46126024916/job140920699926 SUCCESS、artifact15255637257 sha256:2f45d149e63210657f4b1ac3a83c166c32482a17d74376fff042d4ba72fca2ed。既存main review46125712697の認証済みG03取消証拠/metadataを再利用して同一cutoffで追加接続のみ検証。クッション4原本（46087151962,46092412738,46103343334,46122176181）認証・replay errors0、10/11Rの2/12に発走前原本を独立確認、他10Rは時点分母未確定。SP4実行監査済み、構造認定native/dispatch各0R、遅延native46122141318はSP_ORIGINAL_NOT_VERIFIED（原本証明なし）。source HTTP0、PC分母不変、全取得認定なし。実原本の取得機能そのものの再開発をしていない。
- 次: #166 exact明示承認→本番反映・独立検査。取得自体の残存課題（出馬表全12R、馬連/枠連、プロフィール/過去成績、馬場/含水率、外部予備起動、今夜結果・払戻/引継ぎと11/29適応）を維持。11/28 19:00以後の実行と11/29全取得は未確認。最終総合バグチェックの全体完了認定なし。未知障害自己修正本格改修は§22の必須後続工程。

## 34. E39-SUPPLEMENT-04 #165反映後の独立検証完了・#166検証合格（2026-11-28 JST）
- #165 main d6db3de1c9f37622128454f47a615f6a433e0750 自動独立総合検査 run46125712697 test140919736344/review140919762822/publish140920070746 全成功。artifact15256055433 sha256:7ef777547cac61d5dad94e02a2ac81269c546bbac40b3a66b6a5a17448d87409、#141 comment7236585398。31 source runs、13 native slots、25固定リスク、index/replay errorなし。馬体重と増減は25/25（取消各1対象外）、調教26/26・273正規記録、13 archives/247 authenticated snapshots、出馬表2/12、10R分の未知分母維持。両市場・プロフィール・過去成績・馬場/含水率等は0認定、結果/払戻・handoffは当該検査時点で未到来。固定25リスク独立閉鎖0/25。
- 残存検査接続だけを隔離修正した PR #166 exact HEAD f4da936dbcaec79f3a0b3ea757f74acad12d6296、base現main、mergeable=true、未承認/未merge。変更4ファイルは総合検査workflow、本体、追加replay adapter、テスト。既存SP assess_laneとaggregate（trusted-reader c289c5ec4e6ad322a7e08acf173da3352ed23dba）、既存クッションreplayとcombine（301916719e5bc0e3a8e392368434f952c16c05db）を再利用。PC/市場/発走前証明へSP構造を転用せず、クッションは既存原本/時点照合の別ledger。取得workflow全6本のblob SHAを独立照合して完全一致。固定枠・Secrets/Turso/Cloudflare・固定18分類/25リスク分母変更なし。
- CIの有効な3種は全成功：46125994656（job140920606365、exact HEAD checkout、21試験、追加2試験含む）、46125994764（protected release gate）、46126053127（reuse gate、job140920790942）。先行reuse gate46125994672はPR本文の必須2見出し不足で失敗、本文を修正し後続同gate成功。隔離初期候補2a953949294877c55f670eb46e90afff50f47906のPython3.11 f-string引用符をf4da936に修正済み。本番変更なし。
- 実原本統合proof run46126024916/job140920699926 SUCCESS、artifact15255637257 sha256:2f45d149e63210657f4b1ac3a83c166c32482a17d74376fff042d4ba72fca2ed。#165独立検査artifactのdigestと取消証拠を再利用。クッション原本4/4 AES認証・再解析（46087151962/46092412738/46103343334/46122176181）、発走前照合2/12（10R/11R）、残10Rは分母不明、replay errors0。SP独立監査4run、native/dispatchの構造認定各0/12、遅延native46122141318はSP_ORIGINAL_NOT_VERIFIED / SP_AUDIT_UNAVAILABLE。SP未取得を解消扱いしない。source HTTP0、PC分母不変、全取得認定false。新規adapterの実原本統合試験であり、#166のmain自動総合検査は未実行。
- 次はユーザー明示承認を得て#166 exact HEADをmerge、承認tree・main・6取得workflow不変を独立照合し、main自動総合検査で別ledger接続を確認。残存する11/29の実取得対策・当夜結果/払戻・署名handoff/翌日適応、PC/SP両市場・プロフィール/過去成績・馬場/含水率・外部起動、固定25リスクの根拠確認を継続。緊急改修と最終総合バグチェック後に§22未知障害自己修正を必須工程とする。過去成功の無条件再実行なし。

## 35. E39-MERGE-05 PR #166本番反映（2026-11-28 JST）
- ユーザー明示承認 f4da936dbcaec79f3a0b3ea757f74acad12d6296、最新3種CI全成功、旧main d6db3de1c9f37622128454f47a615f6a433e0750 一致後expected_head_sha付きmerge成功。新main 9900c911352fca84dac5c883add5f9c29dbc8318、独立再取得で#166 merged/main一致、承認treeと本番tree afda0b39b9c6dbf7ffc07a9d4c183b3a74d5fb4b 完全一致、parents旧mainと承認HEAD。差分4ファイルのみ（総合検査workflow、本体、補完replay adapter、テスト）、6取得workflow・予約枠・Secrets/Turso/Cloudflare不変。
- 本番push独立総合検査 run46126431639 起動確認、現時点in_progress。SP構造とクッション原本の別ledger接続確認、実取得を妨げる残存原因の対策、最終総合検査へ進む。固定25リスク0/25維持。自己修正本格化は§22の後続必須工程。

## 36. E39-NEXTDAY-06 #166独立検証完了・翌日適応の追加故障注入対策（2026-11-28 JST）
- #166反映後main 9900c911352fca84dac5c883add5f9c29dbc8318 独立総合検査46126431639、test140921939475/review140921967751/publish140922266880すべてSUCCESS。artifact15254959808 digest sha256:e99b7cb3f02aaffe238dd313b1fc0c187b5deb382ea7d61d48038f04e985d5bd、#141 comment7236683842。31 source runs/13 native slots/25 risk rows、index/replay errorなし。SP独立4run監査、構造認定0/12、クッション4原本・2/12発走前照合・再解析エラー0。調教26/26、273記録、馬体重増減各25/25、出馬表2/12、10R未知分母、両市場・プロフィール・当日馬場等0認定。固定リスク0/25。
- 実取得優先の横断点検: mainの日曜選択exact receipt c289c5ec4e6ad322a7e08acf173da3352ed23dba、#165夜間pin b800308169173d9e82cf93db9bf7b381e361cc76、固定6取得workflow/8枠、署名handoff c289、SP分離・G03→G06→G05/G04、既存のsource pacing/時点/保全を確認。11/29前日公開PC/SP 12R・151行は既存証拠46104526918を再利用。#124の前日A2実験2件とno-op証拠を再利用、11/28の直接Cloudflare実行ログは未取得。夜間実行・明日の実取得を未認定のまま維持。
- 追加故障注入対象: 現collectorのrecover_from_metadataは独立認証済み4件のincidentを完全なrun indexで照合済みでも、その後の最大4件の個別job APIに失敗すると既知の回復判断まで失う。実API障害の発生を主張しない。既存4run 46087080554/46092343351/46096495437/46100155324 のactual APIを再取得、exact main/workflow_dispatch/completed/同日/同repo/path一致、既存原本実障害証拠は#141を再利用。隔離候補 37f47235d1f5803ea897844924ce2ed78b6b5457 (branch fix/impl30-nov29-impl39-nextday-metadata-isolation-20261128、親c289c5e、変更3ファイルのみ): 完全な既知incident identityを先に照合し同じ限定回復modeを選択、未知runの個別metadata取得失敗は他runの正の証拠を消さない、証拠なしはbaseline+明示不完全理由。現行の土曜handoff署名元c289c5eを厳格なexact signer互換に追加し、将来Sunday-only pin更新でも認証を維持。新規故障注入・反例2試験、既存署名テスト拡張。18秒境界・予算表・JRA通信・固定枠・設定を変更しない。CI自動起動を確認中、本番未反映。exact CIとactual run index fault replayの合格後に必要最小の本番候補・明示承認を求める。既存#166以降の本番変更なし。自己修正本格化は§22を維持。

## 37. E39-NEXTDAY-07 翌日適応の故障注入対策合格・PR #167承認待ち（2026-11-28 JST）
- 隔離source 37f47235d1f5803ea897844924ce2ed78b6b5457、親c289c5ec4e6ad322a7e08acf173da3352ed23dba、変更3ファイルのみ。exact preflight run46126637728/job140922568393 SUCCESS、414+11+135+39+82+44+79+20=824試験合格、artifact15255952475 digest sha256:c5ebe17e9eb474e46177d7489710570c8ee5e8c51a4673c8910a694863c71d84。新規の個別metadata障害2試験、wrong identity/no evidence反例、旧/現在のexact土曜署名元互換を確認。4件の実障害run identity照合は§36を使用。故障注入であり実API障害発生の立証ではない。
- 本番候補PR #167 exact HEAD a1fedd4a473c560e3f8f5f8b03bfd3c4b1784913、base main 9900c911352fca84dac5c883add5f9c29dbc8318、mergeable=true・未承認・未merge。変更4ファイル：Sunday observer固定pin、exact preflight receipt、保護契約、テスト。Sunday pinだけ37f47235へ、既存handoff署名元c289c5eを維持。6取得workflowのうち他5本blob完全一致、observerは1行SHA置換のみ。夜間結果/払戻、午後補完、調教、クッション、固定8枠、Secrets/Turso/Cloudflare不変。
- exact PR CI6/6全成功: 46126760227 protected gate、46126760274 reuse、46126760234 deployment contract、46126760236 retention、46126760247 cushion integration、46126760243 seal reserve。次はユーザーによる#167 exact明示承認、merge後独立検証、最終横断点検を続ける。11/29実取得、実際の翌日適応適用、固定25リスクの正式解消は未認定（0/25）。既存検査の成功を全取得と混同しない。自己修正本格化は§22の必須工程。

## 38. E39-FINAL-08 PR #167本番反映・事前最終横断点検（2026-11-28 JST）
- ユーザー明示承認 exact HEAD a1fedd4a473c560e3f8f5f8b03bfd3c4b1784913、旧main 9900c911352fca84dac5c883add5f9c29dbc8318、最新CI6/6確認後 expected_head_sha付きmerge成功。新main 12146c7000fe61d78cd4330aaafccc4bf58915f3。PR merged/mainを独立再取得、parents旧mainと承認HEAD、承認tree=本番tree 94c7b231dfa14d5a0a0e1ac197efaf58ed8e5188。承認差分4ファイルのみ。6取得workflowを旧mainと全文比較し、observerだけSunday overrideの1行置換、他5本完全一致。固定8枠、土曜baseline、夜間結果/払戻、handoff、調教、クッションのpin・設定参照を維持。Secrets/Turso/Cloudflare実設定は今回操作せず、外部サービスの実設定を直接再確認したとはしない。
- 事前最終横断点検: 日曜observer source37f47235d1f5803ea897844924ce2ed78b6b5457はc289c5e直系1commit、実行コードの変更はnextday adaptationのみ、他2ファイルは回帰。exact preflight46126637728はpush・same repo/path/head・completed/success、artifact15255952475 digest sha256:c5ebe17e9eb474e46177d7489710570c8ee5e8c51a4673c8910a694863c71d84、現mainのreceipt一致、824/824の既存ログを再利用。土曜実障害4runの同日・同repo・main dispatch・completed identityを確認。署名handoffはc289c5e、Sunday readerはそのexact signerに対応。夜間postrace b800308169173d9e82cf93db9bf7b381e361cc76、午後c289c5e、調教bd800bc30db60919e274eadac419016c963e77de、クッション47cd7f9e881aa989b9f932373cfaf5278dea223a、日次クッションreader301916719e5bc0e3a8e392368434f952c16c05dbを再確認。PC/SP共有固定版・PC→SP・既存保全・両市場/全馬/時点条件の変更なし。
- #166本番独立総合検査46126431639のtest/review/publish3/3成功、#141 comment7236683842を再利用。今回#167の差分は総合検査pushのpaths対象外、新規原本再解析を実行していない。総合検査workflow、本体、補完adapter、固定risk worklist、incident recovery本体とworkflowのblob6/6不変。main run最新100件の範囲で同review以後の新しい対象取得runなし。既存の成功証拠の無条件再実行を避け、最新版の構成・差分照合を独立検証とする。全workflow一覧APIはconnectorの許可endpoint制限で未取得、登録/実行状態を全件直接確認したとはしない。
- 現時点で確認した変更範囲の本番反映後8/8照合合格（tree、4差分、Sunday pin、他5取得workflow、固定8枠、署名互換、exact preflight、総合検査保全）。事前の横断構成点検に追加の具体的コード不整合を特定できなかったため、推測だけの新規修正や固定枠変更は行わない。最終総合検査の運用・実取得部分は未完：11/28の発走前出馬表2/12、重量増減各25/25・調教26/26（10R分母未知）、クッション原本4件/発走前2/12、SP独立構造0/12、両市場・プロフィール/過去成績・馬場等0認定。今日のnative遅延・未起動（run46122141318 failure、他7枠未観測）、Cloudflare直接実行ログ、今夜19:00結果/払戻、20:30翌日調教、21:00署名handoff、22:00再照合、11/29起動と全取得、取得環境全損の回復は未認定。夜間予定の未到来を失敗扱いしない。固定25リスク正式0/25（13 BLOCKER）、既存スコアを変更しない。
- 再開ゲート: 現mainを再取得し、夜間の各実行/保存原本/署名policyと#141の自動診断を確認。新しい実障害があれば既存証拠から原因確定→隔離最小修正→反例/回帰→明示承認→独立検証。新規修正候補は今回作成しない。11/29全データ完全取得が最優先。§22未知障害自己修正本格改修は事前緊急改修・最終総合検査の後続必須工程。現状の限定方針適応を完全な自律修復と呼ばない。固定25リスクを根拠なく閉じない。

## 39. E39-SCHEDULER-09 外部起動優先の再確認・native予約遅延の原因切り分け（2026-11-28 JST）
- ユーザー再指摘に従いGitHub native予約に依存しない既存運用を維持。ただし原因調査は継続。#124の恒久外部タイマー設計は全取得確立後。明日の既存外部起動・固定枠・Secrets/Tursoを変更せず実取得障害を優先する。
- 実run46122141318: 09:15予定、created_at=run_started_at=2026-11-28T07:38:29Z（16:38:29 JST、7h23m29s遅延）、updated_at=07:38:57Z（28秒で終了）、event=schedule、main、name=kyoto-native:15 0 28 11 *。PC/SP双方OUTSIDE_DAY_WINDOW_NO_HTTPの既存実ログ§27。標準予約のrun登録前段階の遅延を示すが、GitHub内部キューの正確な原因は未確定。09:17:22 dispatch46087080554はcreated=start、約42秒で終了。朝dispatch4件（46087080554/46092343351/46096495437/46100155324）、午後4件（46103324991/46108004433/46112551733/46117060392）のcreated=start、success、予定外部予備枠に対応。provider直接ログ未照合、実取得成功とは区別する。
- main最新100 run index（2026-11-21〜11-28 08:34:11Z、総288件）の範囲に当日午前午後対象nativeは上記1件のみ。他7枠は未観測で、完全な消失は断定しない。workflow別APIはconnector許可endpoint外。repository default=main、public、not archived/disabled。朝dispatch時main 6ac6e7bf53ae45bf9985fb33d61244bc1d239af3、遅延run時e67174543189dea1faafbbba2a6ba383f52377d8、現main 12146c7000fe61d78cd4330aaafccc4bf58915f3 のobserver cron8枠/同日concurrency group/cancel-in-progress=false/queue=max一致。UTC/JSTの設定誤りは確認されず、長時間runner実行やJRA処理起因の7h遅延ではない。actorの権限変更等と内部schedulerの混雑・イベント処理は未確定。
- 公式 https://docs.github.com/en/actions/how-tos/troubleshoot-workflows および https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows は高負荷時schedule遅延/欠落可能性、default branch条件、actor停止の可能性を明記。https://www.githubstatus.com/ では11/28確認時点の公表障害なし。一般仕様は今回の内部原因の立証ではない。恒久対応では予約予定→run作成→run開始→job→原本保存を個別計測、外部dispatchと比較、欠落記録、必要時GitHub Supportへのrun ID付き照会。実取得が優先のためnative救済だけを目的とした時刻窓拡張や追加スケジュール・JRA通信を行わない。未終了レースの取得機会喪失は別途根拠に基づき評価。今回main/code変更なし、固定25正式0/25維持。

## 40. E39-SP-FEEDBACK-10 外部起動のSP取得改善への接続不備（2026-11-28 JST）
- ユーザー了承の§39外部起動優先、native原因調査を継続。現main 12146c7000fe61d78cd4330aaafccc4bf58915f3、Sunday source37f47235d1f5803ea897844924ce2ed78b6b5457。実4午前dispatchと既存原本失敗を再利用。追加JRA通信なし。
- 同根原因（run event identityとnative偏重）を検索し、diagnostics/kyoto_impl31_sp_gap_plan.py get_plan が過去SPのfeedback候補をevent==scheduleに限定していることを確認。外部timerに対応するmain workflow_dispatchの過去SP feedbackが除外される。さらに最新のnative原本欠落/例外で過去の有効feedbackを使えず、current PC planまで失う経路がある。今日の旧collectorでSP feedbackが実際に存在したとは主張しない。明日の修正済み取得器での回復を妨げる設計不整合。
- 隔離source d588d8a749d7bde37d62c742bfa201d31fc5cbea（parent37f47235、branch fix/impl30-nov29-impl39-sp-dispatch-feedback-20261128）、2ファイルのみ。same repo/path/day/indexに加えmain branch、completed、厳格なSP認証・run/day/window/causal falseを要求、native/dispatch両方を候補にする。最新2件まで既存12秒内で検索し、欠落・例外でcurrent PC計画を捨てない。取得URL/予算・JRA通信/保護条件変更なし。既存暗号化fixtureを再利用しnative・dispatch・混在遅延/timeout・wrong run・wrong branchを検証するテスト拡張。isolated preflight46127810705 in_progress、未合格・未反映。成功後にexact Sunday pinとreceiptだけの本番候補を用意し明示承認。固定25正式0/25維持。今夜のhandoff、固定枠、Cloudflare/Turso/Secrets不変。

## 41. E39-SP-FEEDBACK-11 外部起動SP改善接続・PR #168承認待ち（2026-11-28 JST）
- 隔離source d588d8a749d7bde37d62c742bfa201d31fc5cbea、親37f47235d1f5803ea897844924ce2ed78b6b5457、実装と既存テスト2ファイルのみ。exact preflight46127810705/job140926186771 SUCCESS、414+11+135+39+82+44+79+20=824/824成功。artifact15256168435 digest sha256:b1d48034ac6cd4f623ae8d30fba1aec4ed0e8be18fd1fdb26cc1cfd608d4dc52。既存暗号化fixtureのテストをnative/dispatch、混在/timeout、誤run/branchへ拡張、同じテスト内で反例を検証。実11/28のSP feedbackが存在したこと、11/29改善適用は未認定。
- 本番候補PR #168 exact HEAD 2f638275da67a94a0b7705e25be3e991ccaee9b6、base main12146c7000fe61d78cd4330aaafccc4bf58915f3、mergeable=true、未承認/未merge。変更3ファイル、Sunday observer pin、exact preflight receipt、保護契約。observerを全文比較しSunday pinの1行のみ変更、他5取得workflowのblob完全一致。固定枠・夜間署名handoff・Cloudflare/Secrets/Turso等を維持。CI6/6 SUCCESS 46127935907/46127935923/46127935910/46127935914/46127935908/46127935919。次はexact承認→本番merge→独立検証、残存する取得障害を優先。固定25リスク正式0/25。追加JRA通信なし。
- 同根検索で diagnostics/kyoto_impl31_improvement_evaluation.py にnative-only評価が残存。evaluateはdispatchを除外し8 native laneを必須、load_saturdayはnative成功1件のみとし既存土曜signer互換もない。これは取得処理を妨げるものではなく、外部起動経由の自己改善効果を未評価にする不備。後続の自動改善評価修正として必須管理し、native/dispatch別の母集団・exact認証・重複排除・未知分母を維持する。既存§22の未知障害自己修正本格工程と#124の標準予約原因調査を継続。今回その評価器は変更していない。今夜の実行・明日全取得は未認定。

## 42. E39-MERGE-12 PR #168本番反映・独立照合（2026-11-28 JST）
- ユーザー明示承認 exact HEAD 2f638275da67a94a0b7705e25be3e991ccaee9b6、旧main12146c7000fe61d78cd4330aaafccc4bf58915f3、最新CI6/6成功、expected_head_sha付きmerge成功。新main425ba294b939a819038afa446a6158d83e2eef40、承認treeと本番tree ac3631585136fb9b89a9ab28af7eb119fa2626bf 完全一致、merge parents旧mainと承認HEAD、承認3差分のみ。observer全文比較はSunday pin1行だけ、他5取得workflowは完全一致。固定8枠、土曜handoff、午後、夜間結果払戻、調教、クッション、設定参照を維持。Cloudflare/Secrets/Turso実設定変更なし、直接確認とはしない。現main receiptはsource d588d8a749d7bde37d62c742bfa201d31fc5cbea、preflight46127810705/job140926186771、artifact15256168435/digest b1d48034ac6cd4f623ae8d30fba1aec4ed0e8be18fd1fdb26cc1cfd608d4dc52 と一致。既存824/824検証を再利用。
- 新規実障害：native 10:15枠 run46127895288 が17:53:25 JSTに登録/起動、PC/SP job140926496313/140926532260 guard OUTSIDE_DAY_WINDOW_NO_HTTP、取得step skip。後続クッション46127940166/job140926589833 は17:54:10 JST cushion_live_guard_no_http、未生成artifactのupload/retry failure。#141自動診断comment7236890280/7236893483 は両件をARCHIVE UNKNOWNとし、直接原因に到達していない。遅延nativeを正常取得に見せない、保護guardを解除しない。遅延時の誤診断・安全停止の証拠分類を追加確認。明日の外部起動は優先維持。固定25正式0/25、全取得・夜間実行未認定。

## 43. E39-NATIVE-ISOLATION-13 標準予約の干渉リスク・隔離方針の検討（2026-11-28 JST）
- ユーザー指摘：native予約併用そのものが障害要因になり得る。実run46122141318（09:15→16:38:29）、46127895288（10:15→17:53:25）および後続cushion46127940166の時間外停止は実証済み。現main observer/auxiliaryは同日共有concurrency group、cancel-in-progress=false、queue=max。native・dispatchの共有キューによる干渉可能性と、Cloudflare既存fresh-in-progress抑止の誤抑止リスクを識別。今日の外部起動が実際に妨害されたことは未立証。外部予定対応朝4/午後4のdispatch実行は既証拠、Cloudflare直接ログ・明日の全対象起動保証は未確認。
- 提案：当面の実取得は外部dispatchを主経路、手動dispatchを独立予備とし、nativeを実取得の共用キューから隔離する方向。今夜結果/払戻・署名handoff・明日調教を含む外部全slot対応、現在のWorker抑止条件、外部停止時の代替、予約済みrunの扱い、日付/時点保護、後続のworkflow_run/監査・自己改善への影響を先に照合。固定予約変更は明示承認と独立検証を要する。native原因調査は通信なしの隔離診断で継続。標準予約を無条件に即時削除しない。
- #169 HEAD e48e85a7370ffcc31fc4d5905d1a3e7ef38cfc37 は取得前停止をARCHIVE障害と混同する診断不備の隔離候補。PR open/未merge、今回CI未確認。取得競合そのものの対策ではない。本番main425ba294b939a819038afa446a6158d83e2eef40、固定枠・設定変更なし。固定25リスク正式0/25。11/29全取得を最優先。

## 44. E39-NATIVE-RESEARCH-14 標準予約復旧研究と毎週手動設定の撤廃（2026-11-28 JST）
- ユーザー方針：11/29の緊急取得とは別に、標準タイマーの異常遅延を仕様の一言で片付けず、正確な自動起動を実現できるか継続研究する。真の目的は毎週の手動タイマー設定をなくすこと。#124の恒久工程を拡張し、緊急実取得を妨げない。GitHub内部schedulerをこちらから直接修正できるとはしない。
- 公式 https://docs.github.com/en/actions/how-tos/troubleshoot-workflows / https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax の遅延・欠落、既定branch、actor、時刻指定を確認。communityの類似利用者報告 https://github.com/orgs/community/discussions/201738 (2026-07-13 8–14h), https://github.com/orgs/community/discussions/209507 (2026-10-04 非00分でも数時間), https://github.com/orgs/community/discussions/211421 (2026-10-27 4–7h), https://github.com/orgs/community/discussions/211632 (run creation前の長時間gap) は症状類似の補助証拠であり今回内部原因の立証ではない。過去§39/42実runの7h23m29s/7h38m25sを再利用。repo新旧や無料plan優先順位を未立証の原因としない。
- 恒久研究案（未実行）：既存Nov16 dummy/rehearsal receiptと§39/42のmetadataを先に再利用。無JRA・no shared live lock・no source secretsの固定診断workflowを、毎時0分対非混雑分、日付指定対曜日/日次、固定版対変更ありの要因を一つずつ比較。予定UTC、cron identity、run created/start、job開始、終了、欠落/重複/遅延の証拠を完全な期間分母で記録、dispatchは別台帳。少数の一度成功では復帰不可。実施前に閾値を合意し、複数日・開催同等時刻で遅延許容・欠落・重複・最大値を判定。GitHub内部の登録/キュー/スロット欠落原因は必要に応じてSupport/communityへexact run ID付き調査依頼（今回未送信）。未検証の有料化やself-hosted runnerを解決としない。
- 標準予約復旧とは独立に、固定周期Cloudflare Worker + GitHub/Turso上の自動生成取得予定表（開催日程/発走時刻/公式公開時点、時点別日付、署名または認証済みversion、失敗時に直前有効版を保持、exact slot idempotence、未取得/重複防止、外部dispatch証拠）を恒久候補にする。人は原則毎週cronを変更しない。無料枠・CPU・通信/API予算・認証更新・障害復帰を検証。今回Worker実設定/Secrets/Turso変更なし、研究実装・新規実験未開始。明日の全取得と未知障害自己修正本格化の必須工程を優先維持。
- 直前の緊急隔離候補#169 exact HEAD a108144d5f04b11895810a12fa144eb196b16acc（base 425ba294b939a819038afa446a6158d83e2eef40）のCIは10実行成功（9種、reuse2回含む）46128890036/46128862067/46128862064/46128862073/46128862095/46128862078/46128862057/46128862091/46128862066/46128862051。既存26 native cronを無通信の別診断workflowに移設し、6取得workflowはdispatchおよびdispatch起点の補完hookだけ、旧共有live lockからnativeを隔離。元の取得器/reader pin、手動input、既存外部slot表26/26、保護条件維持の差分検査合格。初期候補e48e85aのregex不具合で2試験失敗し最新版修正。現main未変更、#169未merge、明示exact承認必須。Cloudflare直接ログ/全26枠の実動作は未確認（8朝午後+調教2dispatch実績、計画と実績を区別）。旧SHAで既に登録済みの実行への遡及制御不可。最新100件run indexでは対象6workflowの進行中/queuedなし、完全な状態一覧とはしない。診断/取得分母を混同しない。固定25正式0/25維持。

## 45. E39-MERGE-15 PR #169本番反映・標準予約隔離の独立照合（2026-11-28 JST）
- ユーザー明示承認 exact HEAD a108144d5f04b11895810a12fa144eb196b16acc。先行承認処理の中断後、#169 open/未merge、旧main425ba294b939a819038afa446a6158d83e2eef40、最新9種CI成功（10実行）を再取得してexpected_head_sha付きmerge成功。新main 457fcf075143b7f80a769b259fa1b9f5d2987abf、PR merged/main一致、承認treeと本番tree 6bfe5bd33f9eb4730d5c5d023a221ec6b8b2230b 完全一致、merge parents旧mainと承認HEAD。承認差分18ファイルのみ。
- 本番6取得workflowを独立取得、全てcron0、元のworkflow名・dispatch race_day/confirmation維持。observer Sunday pin d588d8a749d7bde37d62c742bfa201d31fc5cbea、aux/handoff c289c5ec4e6ad322a7e08acf173da3352ed23dba、postrace b800308169173d9e82cf93db9bf7b381e361cc76、workout bd800bc30db60919e274eadac419016c963e77de、cushion 47cd7f9e881aa989b9f932373cfaf5278dea223a、cushion day reader301916719e5bc0e3a8e392368434f952c16c05db不変。observer/aux/postraceはdispatch日付単位source lock、その他はunique isolated group。workout/cushion hookは同repo/mainのdispatch親のみ。診断専用native-scheduler-diagnosticに旧26枠、権限{}、source HTTP0、dispatchなし、共有lockなし、取得成功認定なし。承認CIで元設定とのexact YAML差分を検証済み。今回同一treeの既存CIを再利用し無条件再実行なし。
- 最新100件main run index（全294件中、11/21〜11/28 08:54:47Z）では旧対象workflowのqueued/in_progressなし。ただしworkflow別全件の確認および既に登録済み旧SHA実行の遡及制御は不可。Cloudflare側は#124承認済みv3の26枠計画・本日朝午後8dispatch/調教2dispatch・過去のprovider実ログを再利用。現在のWorker/token/実設定・明日全枠動作は未直接確認、変更なし。手動dispatchの入力条件維持。標準予約内部原因と固定周期+自動予定表の恒久研究は§44で継続。固定25正式0/25、実取得は未認定。

## 46. E39-EXTERNAL-WATCH-16 外部主起動への監視切替と11/29取得対策（2026-11-28 JST）
- #169反映後、既存のChatGPT読み取り専用「京都AI起動履歴監視」の指示を更新成功。毎時・11/29終了の既存設定は変更なし。旧native予約は新しい無通信診断専用workflowに分離して評価し、実取得成功や外部dispatch成功に流用しない。11/28 19:02結果/払戻、20:32翌日調教、21:02署名handoff、22:02結果/払戻、22:40総合検査、11/29 07:32調教、09:17/10:17/11:12/11:57 PC/SP、12:32/13:32/14:32/15:32補完、19:02/21:02/22:02夜間、23:40総合検査を明示監視。dispatch親起点の調教・クッションも対象。新重大障害のみ実run/対象日/時点/成果物/必要な手動起動入口を報告。監視による自動dispatchや秒・分単位フェイルオーバーは不可、読み取り専用。外部起動の主体・抑止理由はprovider直接ログなしでは断定しない。
- 今夜・明日の既存26枠の計画、手動入力条件、collector/reader pinは§44/45のexact証拠を再利用。新規JRA通信・追加予約・Cloudflare/Secrets/Turso操作なし。利用可能なGitHub connectorに新規workflow_dispatch操作はないため、未起動時は既存Run workflowの手動予備を残す。旧run再実行で発走前データを捏造しない。現時点の追加取得器変更なし。実データ取得および外部全枠実行保証は未認定。
- 残存検査上の課題：既存kyoto_weekend_closure_review.pyのnative_slotsおよび§41 improvement evaluationのnative分母は、隔離前の歴史的指標として保持し、#169以後の意図的なnative取得停止と外部未起動を同一視しない。独立した外部slot証拠ledgerへの正式統合は未実装、今夜の既存独立検査出力を読む際は区別する。取得自体を阻害する証拠なし、既存成功を再検証しない。固定25正式0/25、未知障害自己修正本格工程・標準予約正常化・自動予定表恒久工程維持。現main 457fcf075143b7f80a769b259fa1b9f5d2987abf。

## 47. E39-AUDIT-17 11/28実取得失敗の精密監査・暫定残存事項（2026-11-28 JST）
- 監査対象main 457fcf075143b7f80a769b259fa1b9f5d2987abf、Sunday朝d588d8a749d7bde37d62c742bfa201d31fc5cbea、午後/handoff c289c5ec4e6ad322a7e08acf173da3352ed23dba、夜間b800308169173d9e82cf93db9bf7b381e361cc76。NOV28-01〜16、§12〜46、#141/#116、#169反映・監視指示更新を照合。既存試験の無条件再実行なし。
- 実証: 46126431639/job140921967751、artifact15254959808 sha256:e99b7cb3f02aaffe238dd313b1fc0c187b5deb382ea7d61d48038f04e985d5bd。出馬表2/12、馬連/枠連/同slot両市場0/12、profile/prior_form0/26（10R分母不明）、馬体重/増減25/25・workout26/26（各10R分母不明）、天候/芝ダート/4含水率各0/12、SP構造0/12、cushion認証4件・発走前2/12。朝午後対応dispatch8/8は取得成功ではない。前日11/29の46104526918はPC/SP12/12・151行一致のログ、artifact API空、原本再利用可能性未立証。#169遅延guard診断job140929403781の16試験は合格、実ログ直接再診断とは区別。固定25正式0/25、13 BLOCKER。
- A01 P0 午後補完救済不足。現行aux固定版c289c5eのkyoto_impl30_auxiliary_refresh.py collect()69〜139行、main()169〜186行、workflowの原本uploadはG03/G05のみ。朝4枠で欠損したG04/G06を午後4枠から直接救済する経路なし。既存G06 item-level recoveryは再利用。未発走レースの未取得項目に限定し、既存15通信/180秒・AES seal・拒否条件との両立を検証。
- A02 P0 独立SP市場原本の日次結合不足。kyoto_weekend_capture.py170〜195/344〜437行、kyoto_weekend_day21_artifact_triage.py85〜161行、kyoto_impl30_day_coverage.py62〜150行、kyoto_impl32_sp_handoff.py、kyoto_day_supplemental_replay.py。独立SP取得/保存・既存G06 hybridは存在するが、独立SPの市場原本からG06日次認定への接続が不足。認証済み同日/同レース/馬・取消/時点/市場別照合を既存機能で行い、SP構造やPC分母を無条件に市場認定しない。
- A03 P0 外部起動欠落時救済未証明。#169で6 live cron0、26診断cronへ隔離、#124計画26/26と今日8dispatch対応実績確認。Cloudflare現設定/token/直接ログと明日全枠実行未確認。毎時監視はread-only、connectorに新規dispatchなし、手動入口は維持。独立予備起動は未実装/未証明。
- A04 P0/P1 外部起動評価欠落。kyoto_impl31_improvement_evaluation.py52〜95,97〜124行はnativeのみ8 lane、native署名理由必須。main kyoto_weekend_closure_review.py67〜80,278〜319,387〜390行は旧live native_slots評価。意図的隔離を失敗と混同せず外部slot・実run・認証済みpolicy/原本を別ledgerへ。直接取得停止の証拠はなし。
- A05 P0 当日馬場/含水率・全馬/両市場の実原本不足。#158/#161 URL/DOM/日時判定は反映済み、同日値0件。公開時点/公式導線/再観測/項目別保全の検証。前日値を当日値扱いしない。
- A06 P0 夜間結果/払戻/署名handoff実動作。#165 origin、#167 metadata fallback、#168 SP feedbackは反映済み。19:02/20:32/21:02/22:02/22:40の実取得・認証・訂正照合は未確認。未到来を失敗としない。
- A07 P1 runner強制喪失時の保存・90日artifact長期保全・共有Turso実証。GAP08/11/16未認定。未知障害自己修正・標準予約原因究明は必須後続工程、診断と自動修復を混同しない。
- 暫定判定: 全対策終了を否定。A01/A02/A03を優先しA04/A05/A06を続ける。外部直接ログ・全対象原本バイト不足、署名case/validator未実施により正式IETAP v4.0.2 auditはBLOCK（署名状態未開始、RELEASEDなし）、今回の所見はGitHub実ログ・固定コードによる暫定判定。正式監査合格を主張しない。main/取得器/予約/Secrets/Turso/Cloudflare変更なし、追加JRA通信なし。今回記録処理の変数定義漏れで初回書込前停止、mainと正本確認後再開。修正候補は既存exact HEAD承認手順を維持。

## 48. E39-FIX-18 午後救済・市場再読込修正の隔離checkpoint（11/28 JST）
- main 457fcf075143b7f80a769b259fa1b9f5d2987abf 不変。source branch fix/impl30-nov29-impl39-aux-gap-recovery-20261128、現HEAD d530fb4e8199d190cdb56367eb66ad193e7e3779。A01: 日曜午後のみ既存15通信/180秒の原本収集後、未発走・未認証市場/プロフィールを既存G06/G04で救済。追加最大20通信、合計35、総300秒、共有pacer/拒否フラグ、個別締切、profile予約、既存原本の暗号化失敗時保全。追加予算は候補のみで未承認・未本番。A02関連の同根PC公式host両日不整合をitem-level/missing-market retryで修正。独立SP日次結合は未完。
- 2850c77282160a61ddc9c28a544c48167ea01312 は46130351293/job140933893789 827試験成功。55e3bf2b11b9340c4364b9840e3f780d43f533f3 の46130535682/job140934461673 は先行7群808試験成功、FMEA末尾20件中2件エラー（変更source blobの再開要求）。検査器を緩めず d530fb4 で旧/新blobと未解消25件を維持して再開登録、11/28・29市場原本正規host/異常host回帰追加。46130734716 は確認時in_progress、未合格扱い。
- A03 Cloudflare接続候補なし・手動fallback維持。A04/A05/A06/A07の§47所見維持。今夜のsigner、夜間pin、26枠、設定、mainに未変更。合格後に既存のexact HEAD承認手順で本番候補へ。

## 49. E39-FULL-CHAIN-19 緊急本番統合候補 PR #170 検証済み・承認待ち（2026-11-28 JST）
- #47 A01/A02/A04に対する実装修正。隔離source 9ceb07be0c4754bd5119ea8f87c2a87a44103f73（fix/impl30-nov29-impl39-aux-gap-recovery-20261128）、exact preflight 46131166931/job140936398359 SUCCESS、416+11+135+39+82+44+84+20=831/831成功、artifact15258256025 SHA256 5aad71babf893c0cd0a471e409ffc7c2267a70f92510352c7403b3683c161c5c。途中55e3bf2のFMEA blob変更検知2件は再開登録で解消、検査条件緩和なし。d530fb4午後/両日host修正と65481f9 SP統合の合格を再利用、最終sourceのみ全回帰。
- A01 日曜午後、旧15通信/180秒の原本収集を維持、最大20追加・計35通信/300秒、共通pacer・拒否停止・発走前cutoff・プロフィール用予約、既存G04/G06再利用。先行暗号化原本を作成、追加seal失敗時保持。runner強制消失・rename中断窓・全量保証は未閉鎖。A02 SP独立原本を認証/保存導線/PC馬番枠馬名/発走時点/取消/市場matrixで結合。SPのみでPC分母や馬profileを認定しない。A04 nativeと外部dispatchを別ledger、実run候補重複・欠落・署名policy採用/効果を検査、provider受領証明ではない。
- 本番候補 #170 exact HEAD 01775cbf1e352defc2a08d6082867d38ae2830bc、base main457fcf075143b7f80a769b259fa1b9f5d2987abf、tree bb49369017d99ecd05dd5be2d376ac9a09188e6d、差分9ファイル。Sunday observer exact receipt更新、午後/handoff/独立review reader日曜のみ新source。独立reviewは日曜bounded原本再開でSP市場を判定し、SP許可runを市場以外に流用しない反例テスト追加。土曜signer・postrace/workout/cushion pin維持。26診断枠・native隔離・外部手動入口・全保護条件・Cloudflare/Secrets/Turso不変、追加JRA通信なし。初回PR metadataの必須reuse3項目記述漏れにより46131488872のみFAIL、PR本文修正（HEAD不変）後46131551743 SUCCESS。最新7種CI全成功: 46131488887/46131488916/46131488923/46131488908/46131488886/46131488881/46131551743。open,mergeable=true,未承認/未merge。
- A03 providerログ/独立自動予備起動未証明（監視read-only、既存手動予備）、A05同日馬場等・全馬/両市場実原本、A06今夜結果/払戻/署名handoff、A07 runner強制喪失/長期保全/Tursoは未閉鎖。固定25正式0/25、13 BLOCKER、明日全取得は未認定。§47固定分母を維持。次はexact HEAD明示承認→本番merge→merge tree/parents/pin/保護条件独立照合。未知障害自己修正本格工程・標準予約正常化/固定周期自動予定表は後続必須。
