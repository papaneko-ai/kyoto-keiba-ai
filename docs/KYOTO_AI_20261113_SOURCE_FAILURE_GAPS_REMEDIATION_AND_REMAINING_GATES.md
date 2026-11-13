# 京都競馬AI｜2026年11月13日取得障害再監査・実装修正と残る外部受入条件

## 総合判定
14・15日の「内部コードだけで修正できる」主要な失敗経路（公開Gitへの生HTML配置、失敗をGitHub成功と誤認、旧手動経路からの15日二重取得、原本の改ざん検知、入力の当日欠落）を修正・追加した。ただし**真正なJRA原本の発走前実取得、取得条件、GitHub Secretsや実際のレース固有の入力、他ホストまでの排他**はコードだけでは完了証明できない。実取得の全穴が埋まったとの虚偽の完了認定は禁止。

### 修正済みコード
- `diagnostics/kyoto_nov15_two_original_observer.py`：ユーザーの明示起動を条件にJRA公式PC選択ページを一度読み、実際のページに記載される15日京都開催リンクだけを候補にする。重複・未掲載・HTML異常・不正URLは安全停止。公式選択→公式開催の最大2 GETで停止し、勝手に出馬表・馬連・枠連が取れたと報告しない。
- `.github/workflows/kyoto-nov15-encrypted-observer.yml`：開発ブランチへ`diagnostics/nov15_observation_explicit_activation.txt`（内容 `NOV15-OBSERVE-TWO-ORIGINALS`）を明示的に追加した場合**のみ**起動。1回限りの実行履歴・GitHub再実行の禁止・UTC取得窓・AES256鍵の存在をJRA通信より前に検査。
- `diagnostics/kyoto_nov15_encrypted_evidence.py`：PC選択・京都開催の二原本と受領証をAES-256-GCMで暗号化し、公開GitHub Actionsアーティファクトには暗号文＋照合用manifestだけ保存。復元時は鍵、run ID、SHA256、認証タグ、アーカイブ名を検査し、危険なファイル展開を拒否。
- `.github/workflows/kyoto-nov15-second-day-observed-oneshot.yml`：観測済み二原本は**Gitコミットではなく暗号化された観測Artifactから取得・復号**。日付・レース・馬番/枠・発走予定時刻・二段階リンクを照合し、15日専用取得を一度だけ実行。公式PCリンク404/410のみ、既存の限定的な公式再発見手順を利用。
- `diagnostics/kyoto_nov15_capture_acceptance.py`：実際の取得器が`CAPTURE_BLOCKED`／`OFFICIAL_NOT_PUBLISHED`等を正常終了コードで返してもGitHub Actionsで成功にしない。 `SOURCE_FROZEN`、同一レース、出馬表・馬連・枠連三原本と各受領証のSHA256・バイト数が揃った場合だけ合格。合格でも実際の独立予測／購入許可は偽。
- `diagnostics/kyoto_nov15_full_capture_seal.py`：後続の取得結果・エラー受領証・公式原本を一つのAES-GCM暗号化アーティファクトに保存し、公開artifactに生HTMLを置かない。暗号文改変、鍵相違、run ID相違、パス横断を拒否する。
- `.github/workflows/jra-observed-odds-manual-oneshot.yml`：従来の手動ワークフローでは15日を**取得前に拒否**。新しい観測・実取得ワークフローと取得のconcurrencyグループを共通化し、無制限の平行実行を防ぐ。
- `diagnostics/kyoto_nov15_readiness_check.py`：`--mode encrypted`で**公開HTMLを必要としない**準備状況を判定。15日spec/roster/UTC/観測run IDの不足・日付違い・時計の発走10分前制限・早すぎる起動を確認。CLIでは現在UTCを使用する。旧5原本入力モードは回帰試験用のlegacyとして隔離。

### 独立して残る外部条件と実用上の穴（失敗機会を隠さない）
1. **14日**：11月12日の公式選択GET（Run 43142384975）が`FAILED_CLOSED`となっており、既存14日one-shotを再起動しない。したがって、14日の**事前凍結データを全件揃える実取得経路はまだ独立受入されていない**。既存の別の公式PC/SP手動経路は観測済み実URL・独立ロスターと時刻があれば利用検討できるが、無証拠で架空URLを生成しない。
2. **GitHub Secretsの外部設定**：公開リポジトリで原本を保護するため、Actions Secret `KYOTO_JRA_ARCHIVE_AES256_HEX` に**暗号学的にランダムな64桁16進文字列（32バイト）**が必要。同じ鍵を観測と実取得の両方が使う。秘密鍵は公開Issue・ChatGPT・ログ・追跡ファイルに貼らない。Secretの設定完了はGitHub側で未確認。設定がないとJRA GET前に安全停止する。公開リポジトリのArtifactは暗号文でも保存期限30日であり、機密の根本解消にはアクセス権と保管運用の独立監査が必要。
3. **15日の実原本観測・入力資料**：15日の実際の京都開催を映したオリジナルHTML、当日特定Rの独立観測PC URL・出走馬・開始時刻はまだこの開発ブランチの真正原本として未確認。観測ワークフローは明示起動後、成功すれば暗号化した公式選択／開催HTMLを保存するが、**それだけでレース別出馬表や馬連・枠連は取得完了しない**。残る特定Rのspec／roster／公式開始時刻は真正な証拠から準備する必要がある。
4. **横断重複管理**：同じ開発ブランチの既知の手動経路を制御しているものの、Streamlit・別ホスト・GitHubの別名ワークフローを含めた**共有DBによる予約の実環境受入は未完成**。同一ホストSQLiteの試験合格はこれの証明ではない。
5. **公式サイト運用・通信の外部制約**：公式サイトの利用条件・実際のHTML構造・掲載時刻・オッズ公開状態・市場の欠落・HTTP応答の変化は当日のJRA実通信なしには保証できない。事後の結果取得は可能でも、事前予測に必要だった時点の原本は遡及復元できない。
6. **新設取得ワークフローの本物の受入**：模擬fixtureでは予備試験が成功しても、GitHub Actionsの実行経路で観測成功→暗号化Artifact→別Run復号→同一レース時点保証→馬連・枠連源の取得まで完走したと認定しない。生原本を公開Gitに置く旧入力方式へ戻さない。

### 11月15日の安全な実行順序
1. GitHubの設定画面で暗号鍵Secretをユーザー本人が設定する。OpenAIはSecret値を受け取らない。
2. 観測のみの`diagnostics/nov15_observation_explicit_activation.txt` を明示起動する（事前にUTC受付時刻・公式利用条件を確認）。同一失敗を無条件再実行しない。
3. GitHub Actionsの観測Run・暗号化artifactの記録を照合。原本不足・暗号化不合格ならそこで停止。
4. 同じ11月15日の独立に確認できたレース用`docs/diagnostics/nov15_pc_observed_race_spec.json`、`nov15_pc_current_roster.json`、`nov15_pc_verified_start_utc.txt`、`nov15_observer_run_id.txt`を揃え、`python -m diagnostics.kyoto_nov15_readiness_check --mode encrypted`で不足を点検する。**公開リポジトリに公式HTML原本をコミットしない。** JSONも転載可否・個人情報・著作権条件を検討。
5. `diagnostics/nov15_pc_explicit_activation.txt`に`NOV15-ONE-SHOT-READ-ONLY`だけを書き、明示起動する。GitHub Actionsで観測Artifact復元、事前原本照合、1回限りPC取得、両市場原本・受領証整合性、暗号化保存まで実施する。ワークフローの「SUCCESS」を実市場取得の独立認定に流用しない。

**追加費用なしの完全無人取得、外部Secret未設定・公式原本未取得のままの完遂は、今回の実装では実証していない。** 事実と違う完了報告はしない。既存P1～P8、EVO-01～08と研究成果、固定32/32=100%、実開催0/6、実用能力0/100、最終20ゲート35/100を維持。本番main・Turso・公開Streamlit・Secrets自体・実馬券購入は変更しない。


## 11月13日・追加の根本原因修正（旧記述より優先）
- 過去Runの存在だけで「取得済み」と見なす制御を改め、`diagnostics/kyoto_p1_github_attempt_history_gate.py`で**取得ステップが明確にSKIPPED、かつそのRunが終了済みと証明できる場合だけ**同一日の設定修正後再試行を許可する。GETが開始された可能性がある場合、履歴APIが不完全・利用不可の場合、対象ステップの状態が欠落する場合は**必ず停止**する。単なるRunの失敗を「JRA取得に失敗」と誤認しない。
- 上記は11月15日公式選択ページ観測と、後続の馬連・枠連取得の両ワークフローに接続。各ワークフローは同一のActions排他グループを使用。旧手動取得器は11月15日の対象を取得前に拒否する。
- `tests/test_kyoto_p1_github_attempt_history_gate.py`の12異常系試験により、失敗前の安全な再挑戦と曖昧・既消費GETの拒否を区別。 `tests/test_kyoto_nov15_two_stage_encrypted_pipeline_lab.py`で、合成データに限り二原本観測→暗号化→復元→レース紐付け→三原本の受領証照合→暗号化保管→再復元の縦断動作を検証する。**研究fixtureでのPASSはJRAライブ取得のPASSではない。**
- 最新アーキテクチャでは、生の公式HTMLを開発ブランチへコミットしない。以前の「公開HTML5入力が必要」という実装記述は旧方式であり採用しない。現在の`python -m diagnostics.kyoto_nov15_readiness_check --mode encrypted`はspec／roster／UTC開始時刻／前段観測Run IDを検査する。実行前には暗号鍵のSecrets側設定も別途必要。
- GitHubの公開リポジトリで生原本を保存・公開しないことを徹底する。暗号化したActions Artifactであっても保管期間、復元鍵のバックアップ、通信やデータ利用の運用条件は独立管理する。

**未解決の外部受入条件**：真正なJRAページの実際の掲載・発走前の三原本取得、15日の当日レースの独立したspec／roster／UTC、Actions Secret設定、別ホストからのアクセスまで含めた共有取得予約は、事前の合成回帰試験だけでは証明できない。解消まで実開催0/6・実用能力0/100・最終20ゲート35/100を据え置く。
