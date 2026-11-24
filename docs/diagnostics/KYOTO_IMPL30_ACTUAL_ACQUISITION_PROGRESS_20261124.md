# 11/28・29実取得に向けた優先改修管理
2026-11-24 実装30。前週の実取得分析を根拠とする。固定5完成認定は変更しない。優先8項目は各々、原因に対する修正・独立試験・本番候補接続を区別し、実開催成功を主張しない。

- P01 11/22成功経路再利用：実観測PCのdoAction→POST accessOを既存取得器で使用。全取得ファミリーの補完接続は未認定。
- P02 11/21取得前停止：3件のG03/G05 bridge回帰に共通する実行日時混入を修正。歴史試験は固定UTC、現行時点ゲート不変。候補 a4b74c01775990ddbdabc2cc1289e155de7e55b1 の run 45334414812 で bridge 11/11 合格。さらに開催枠内での診断繰返しを事前CIへ集約する候補を作成。
- P03 11/22 13:11-13:13 JSTの遅い24市場原本：G03の独立証拠確認直後にG06を起動し、確認済み発走UTCの昇順。G06共通上限720秒、G04共通上限1020秒。別の固定5分のプロフィール用残余を設け、既存AES保全境界を維持。G06入力/出力は従来の12R索引を維持。a4b74c... CIで市場優先順、全Rレシート、失敗隔離が合格。実際の取得所要時間と跨枠再利用は未認定。
- P04 159頭対185プロフィール原本：旧取得器が出走馬行外のリンクを拾っていた。実原本再解析 run 45336620972 / artifact 14894297847 で登録馬159/159・非登録26/26・現行プロフィール及び過去走解析159/159・過去走1652件・解析エラー0を確認。72頭の原本は発走後であり発走前証拠には転用しない。既存の独立G03出走馬限定・発走時刻優先・同日暗号化原本再利用・欠損再取得・開催日単位統合を維持。現行取得器 afee293e9f78e7ec72fe8a4de918d52ed11b412a と実原本再解析候補 3a3932e6dff03d40f8eb2ae53e5df533562f6a86 の関連6ソースのblob一致及び本番候補固定SHAを照合。プロフィール・公式プロフィール掲載過去走の取得改修準備は認定済み。全要求特徴量（恒久ID、過去走別詳細結果、通過順、ラップ等）及び次開催発走前取得は別途未認定。
- P05 馬場・馬体重・調教：既存G05を保存原本に接続済み。調教の独立実源と時点別欠損補完は未完。
- P06 結果・払戻：既存PR #96の全12R取得候補と照合/訂正、予約候補を保全。実原本の全12R確定照合は未認定。
- P07 28日→29日自動改善：既存C12照合・候補選択は保全。自動修正・認定・採用の一貫実証は未完。
- P08 本番反映：PR #94隔離候補。main未変更。予約枠・共有予約・Secretsの保護を継続。

CI 45334414812: 293+11+120+37+18=479 tests passed; artifact 14892549763. Prior tests are not a completion KPI. Do not infer data acquisition from CI. Next work concentrates on actual acquisition item completeness and activation of verified candidate, not accumulating tests.

## 2026-11-24 actual-source milestone
- Fixed eight acquisition preparation priorities: P02/P03/P04 completed = 3/8 (37.5%); previous 2/8 (25%). The denominator and scope of the eight items are unchanged: this is acquisition repair/preparation, not live acquisition or full feature certification. Fixed five overall completion gates remain unchanged.
- Actual encrypted sources: run 44966013490 artifact 14730699156, profile run 44984067104 artifact 14739565028, parser receipt run 44966654858 artifact 14731603935. Replay PR #100, run 45336620972, artifact 14894297847; no new JRA HTTP. No plaintext original or encryption key exported.
- Existing production candidate PR #94 retains collector afee293e9f78e7ec72fe8a4de918d52ed11b412a; actual replay verified unchanged blobs of jra_prior_form_offline.py, kyoto_g04_all_horse_profiles.py, kyoto_impl30_profile_resume.py, jra_multi_capture_20261106.py, jra_pending_profile_plan.py, kyoto_weekend_capture.py.
- Remaining P01/P05/P06/P07/P08 are not promoted. Next priority: independent auxiliary data source and time-sensitive missingness recovery; Saturday-to-Sunday adaptive repair is not yet certified. Main activation requires existing approval; no main or Secrets or Turso changes.
