# 京都競馬AI開発・実装37｜再開指示・納品検査記録
2026-11-27 JST. 3分割完全移行の正本はChatGPT納品ZIP。GitHubのみは暫定復旧。
- 最終main 6ac6e7bf53ae45bf9985fb33d61244bc1d239af3、PR126–136承認済み。本番再反映、成功試験繰返し禁止。
- 固定指標（名称・順序・分母固定）実取得対策認定率7/8=87.5%、固定5項目の完成率0/5、自動改善機能追加強化5/5=100%、研究・開発工程認定率32/32、研究卒業認定率12/12、実開催接続認定率0/6、実用能力独立検証下限0/100。P05未認定。固定25全解消未認定。
- 最優先11/27 20:30翌日分調教、20:32外部予備、11/28・29京都24R全データ取得。出馬表・全馬プロフィール・過去成績・馬場/気象/含水率/クッション値・調教・馬体重・馬連AND枠連・結果/払戻/取消/返還/同着/訂正。原本SHA/UTC/ID/取得時点。PC/SP・補助相互補完。欠損を残すだけで諦めない。既存26枠、Cloudflare、Turso、Secrets不変更。A2認定済み、12:32 NO_MATCHING_SLOT確認済み。同じログ不要。
- core/aux/handoff 3f4b3d77357745ead05a9f78db34eb6ac2d78637、postrace 1fa2a43fcd17f5100b0b9b9b3dde43dec5a2981f、workout 3274283595eac679f6a5e5fb9d658c2080149f62、cushion 47cd7f9e881aa989b9f932373cfaf5278dea223a、cushion_day 301916719e5bc0e3a8e392368434f952c16c05db。全6本active、日曜overrideなし。Turso SELECT実成功、予約書込み未検証。R08事前範囲合格。強制runner消失、起動遅延、全頭全項目実取得、実handoff未確認。新規本番変更は具体的障害時に限り従来の正確HEAD承認。
- 個人研究、無料運用、P1–P8/ALG01–13/EVO01–08/R01–R08、ChatGPT直接予測超え、仮想投資、独立評価、Work/Codex分離、過去研究再利用、16:00終業時完全パック。次の大きな節目まで進む。実開催を待つだけで停止しない。
- 3巻のうち任意から AUTO_RESTORE_IMPL37_THREE.py と THREE_VOLUME_MANIFEST.json を取出し、Python3 -Sで3巻を指定、Git必要。順不同。CHECKPOINT再利用、priorityは暫定、旧34/35/36・新37全PASSでのみ完全復元。ユーザー手動結合禁止。通常Python ClientError時は可視Python経路を使い、標準ライブラリ子プロセス -S。元ZIPを再作成しない。
- 旧正本832816103 SHA256 21c482807a4fefd48253f17f2c1ca813267912ad7d586c035b936c0292e68936。新正本846334274 SHA256 2c03329666b0cd1ad05f9882573d57a6c3cbb69ac13108a546093fc434257c3d。3巻CRC合格、実復元順3,1,2、28.64秒、exit0、旧34/35/36・新37全PASS。納品記録 #116 comment7211766013。
- GitHub source/evidence backup run45953002354 artifacts15177333807/15177109314、isolated history run45953116416 artifact15177174205。Git refs10、proof refs29、run metadata29、merged PR11。外部Turso本DB、Secrets/PAT、未取得Cloudflareログ、未来の開催データ、期限切れ外部artifactを含まない。GitHubに846MB正本そのものは未アップロード。添付ZIPの専用指示書が優先。
