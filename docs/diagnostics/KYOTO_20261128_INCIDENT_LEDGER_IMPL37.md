# 2026-11-28 実障害の根本原因と Nov29 対策記録

恒久管理: [Issue #141](https://github.com/papaneko-ai/kyoto-keiba-ai/issues/141) / 固定リスク [#116](https://github.com/papaneko-ai/kyoto-keiba-ai/issues/116)。
研究優先順位は全種類の実データ取得。過去の実証を再利用する。原本・SHA256・UTC・レースID・取得/解析/認定の段階を分離する。

| ID | 原因・根拠 | 対策・検証 |
|---|---|---|
| NOV28-01 | 固定 PC GET が公式エラーへの301; no-redirect で選択失敗。実際の公開トップは POST doAction。 | PR #138; 46102021510, 46102320045, 46102786505。公開フォームの原本から厳密に観測した action を使用、12/12リンク・R12原本取得とprovenance成功。 |
| NOV28-02 | SP 出馬表/開催選択が onclick POST、href限定探索では候補ゼロ。 | PR #137/#138; 46100842649, 46102851953。独立SPで3通信、12/12候補。PCからURL生成禁止。 |
| NOV28-03 | 取消馬の数字が PC span.cap / SP td.uban.keshi の取消文字に置換される。 | PR #140; 46102915944, 46103089028。登録馬18頭の馬番・枠・名前が両情報源で一致、16番取消。連番と全登録行の照合、取消の証拠を記録。SP両市場の取消回帰も追加。 |
| NOV28-04 | GitHub job成功でも実取得ゼロ。4外部実行 46087080554, 46092343351, 46096495437, 46100155324 の暗号化原本を独立診断。 | 46100456028, 46100842649。正確な既知run identityを再照合した場合だけ既存MARKET_OR_ROSTER_RECOVERYへ。成功/不足の混同禁止。 |
| NOV28-05 | 実行名はworkflow display nameではなく workflow_dispatch または kyoto-native:<cron>。旧判定で handoff, profile reuse, auxiliary, SP gap plan, evaluation から脱落。 | 実4runのname/path/event/dayを確認。保護されたcronの完全一致、正しいmain/path/dayを要求。旧display名の既存互換性維持。 |
| NOV28-06 | Saturday handoff固定旧SHAとSunday改修SHAの不一致で署名policy拒否。旧readerでは新PC home原本がallowlist外。 | 明示された旧signer SHAのHMAC/recompute検証のみ互換、今回のreader/writerは同じ検証済みcandidateに更新。予算のみ既存policy表、任意コード・secret変更不可。 |
| NOV28-07 | 午後補完も旧PC固定GET。プロフィール再利用が旧host固定。 | Sunday auxiliaryを観測POSTに変更、旧来の15通信/track reserve維持。profile resumeを元カードと同一hostに束縛。 |

今回の候補: 248465ec88fd626df21ba13e25ec9344db7f9eb6 / [exact offline preflight 46104131224](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/46104131224): 780 tests PASS。PC/SP実カード取消照合: [46103089028](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/46103089028)。この文書は本番統合前の証拠記録であり、明日の全データ取得成功を主張しない。

## 保護・未認定
固定8枠、外部タイマー、Turso、Secrets、Saturday observer baseline、暗号化原本保全と予測禁止を維持。全12Rの原本・オッズ・全馬プロフィール・馬場・結果払戻・訂正の実開催成功は未確認。固定GAP-01〜25全件解消を認定しない。postrace別pinの観測経路と実行名・原本reader互換は別途確認。原本は既存暗号化保存、原因要約・run ID・SHA・検証結果はGitHubに恒久記録し期限付きartifactと区別する。


## 追補：結果・払戻の独立取得、前日実サイト検証（2026-11-28）

| ID | 根本原因 | 修正・検証 | 限界 |
|---|---|---|---|
| NOV28-08 | 結果取得側が旧版アーカイブ読取・実行名・固定ホストに依存し、改修済みPC原本や外部起動記録を取りこぼす | 現行の午後補完を維持して新読取互換・正式実行名照合・観測した公式originの引継ぎを追加。候補 4dc34085eb9d9e10c88329ddf7d2933aec5e9958、回帰 787 件成功 [46104549862](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/46104549862) | 実開催の結果・払戻原本は未観測 |
| NOV28-09 | 発走前の出馬表が得られないと結果原本の取得まで停止 | 独立した公式ホームGETを1回のみ許容し、観測した結果・払戻導線を使用。登録馬照合なしでは結果の認定・払戻確定をしない。従来16操作上限、ホーム追加時のみ17、既存時間・拒否・暗号化保護維持 | 実結果の出現後に照合が必要 |

- [前日実サイト検証 46104526918](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/46104526918)：11/29全12RのPC原本・発走時刻・登録馬照合、SP独立原本12/12、馬番・枠番・馬名の一致12/12、登録行151件（取消行含む）。公式ホームの結果・払戻導線各1件。各原本SHA256・UTCを [事前検証台帳](KYOTO_20261129_PREDAY_SOURCE_READINESS_IMPL37.json) に保存。前日の公開情報であり、当日ライブ取得・オッズ・結果・予測認定ではない。
- PR142で反映済みの朝・午後・引継ぎの固定SHAは変更しない。結果取得のみ候補 4dc34085eb9d9e10c88329ddf7d2933aec5e9958 に更新する。固定時刻・秘密情報・Turso・外部タイマー・cushion sidecarは変更しない。FMEA全25項目の完全解消は未認定。
