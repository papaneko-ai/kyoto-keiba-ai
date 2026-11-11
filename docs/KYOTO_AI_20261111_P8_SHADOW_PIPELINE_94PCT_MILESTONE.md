# 京都競馬AI・2026年11月11日 P8-03研究開発94％節目・完全継続復旧

## 1. 現行正本と四つの数値
- 正本 `KYOTO_AI_START_HERE.md`、固定32条件 `docs/diagnostics/kyoto_progress_rubric_v1.json`、証拠 `docs/diagnostics/kyoto_progress_evidence_v1.json`、研究卒業rubric/証拠、原本Artifact `13482994623`、GitHub開発ブランチ `jra-html-diagnostic-20261105`、最新HEAD/Actionsを照合してから継続する。
- **研究・開発工程認定94/100、30/32合格、未達2条件**。前回92/100・29/32から固定P8-03の2点のみ加算。基準・配点の変更なし。
- **研究卒業100.0%（12/12）**、**実開催接続独立検証0/6**、**独立実用能力の検証下限0/100**。研究機能の完了を実運用済みと主張しない。
- 残り **P3-02（4点、実データで市場とモデルの同条件比較）**、**P8-04（2点、公開環境の動作・復元・費用検証）**。
- ユーザー指示：当日は16:00終業。区切りでは同一SHAのCIと復旧ZIPを保存。main、Turso、Secrets、旧公開app.py、実購入機能は無断変更しない。

## 2. P8-03実装した実行可能な研究診断機能
- `diagnostics/p8_uploaded_archive_replay_lab.py`：ユーザーが保持するP1三原本ZIPと別途保存した独立SHA256、研究用固定モデルJSON、観測UTC、凍結UTC、上限予算、任意の結果HTML・取得UTCを受け取り、既存P1 archive→P4原本連動EV→P5研究用レース順位・買い目→P6-02事前凍結→P6-03研究用払戻精算の一連の処理を実行。ネットワーク要求0、実購入0、実開催認証0。
- `diagnostics/p8_uploaded_archive_shadow_app.py`：既存旧公開アプリと別のモバイル向けStreamlit診断UI。原本ZIP、外部記録SHA、モデルJSONを必須とし、研究用結果HTMLは任意。利用者へ非公式・未認証の警告を明示。
- `tests/test_p8_uploaded_archive_replay_lab.py`：馬連・枠連両市場、仮想精算、凍結のみ、見送り、SHA改変、不正モデル、日時、異日結果、AppTest、無ネットワーク・無購入経路を確認。テストファイルには継承テスト含む28件が走る。
- 初回失敗 run `42932100497` は、ZIP末尾の余分なバイトが標準zipfileに許容され得ることを検出。後続で`diagnostics/p8_uploaded_archive_replay_lab.py`に正規3メンバーZIPの**完全バイト再構成一致**を追加し、末尾追記・非正規入力を拒否。独立SHAは同じ不正ファイルから計算したものではなく、別途保全された原本の値を要求するようUIも修正。試験条件の緩和ではない。
- コードの成功 CI **run `42932268997` / job `130233685091` / SHA `ce5cb399f798dad0247a7adabe43874bc018f41e`**。
- 固定採点証拠台帳にP8-03を登録し、再採点 CI **run `42932504177` / job `130234456973` / SHA `505b5be38af7a45a4b113098066a6ef58e0b0ffd`** でsuccess。ログ：`KYOTO_PROGRESS_VERIFIED=94%`、`KYOTO_RESEARCH_GRADUATION=100.0%`、`KYOTO_RESEARCH_TO_LIVE_VERIFIED=0/6`、`KYOTO_OPERATIONAL_VERIFIED=0/100`。

## 3. 重大な限界を保持する
- GitHub Actionsが成功したのは**外部から与えられる保存原本と合成研究モデル**のパイプラインであり、独立JRA公式取得、真正UTC、発売・取消、未使用実開催による確率較正、公式結果照合の外部実証ではない。実用点0/100から恣意的に加点しない。
- 研究結果の回収率や見送り判定を実購入の推奨・実績として表示しない。過去の確定オッズを発走前データに転用しない。既存のALG01～13・EVO01～08・P1～P8は維持する。

## 4. 同一SHAの復旧
- この文書のpushで `.github/workflows/kyoto-ai-milestone-recovery-archive.yml` を発火。ソースZIP・SHA256SUMS・RECOVERY_MANIFESTと同じHEADのcontinuity CI successを最後に確認して復旧完了とする。
- 新規バックアップbranch `backup/kyoto-ai-development-94pct-20261111` を同じSHAに作成。既存92%保全branchとArtifact `13816467764`、別保全の元JRA HTML Artifact `13482994623` は削除しない。
- 同一SHAの最終run/job/artifact/digestは実際のAPIで確認した値だけを報告する。

## 5. 次回指示
「`papaneko-ai/kyoto-keiba-ai`の開発ブランチ`jra-html-diagnostic-20261105`を継続。`KYOTO_AI_START_HERE.md`、本94％パック、固定採点台帳、研究卒業12条件、原本Artifact、最新HEAD/Actions/復旧ZIPを読み、固定工程94％(30/32)、研究卒業100％、実開催接続0/6、実用下限0/100を区別する。未達はP3-02(4点)、P8-04(2点)。既存のP1原本/P4モデル市場EV/P5リスク配分/P6事前凍結と結果照合/P8研究用スマホ再現を作り直さない。実開催の公式発走前データ・時刻・発売/取消・外部真正性・未使用時系列評価の確立を優先し、main/Turso/Secrets/旧公開アプリ/実購入を無断変更しない。節目は固定得点と成功run/job/SHA、同一SHA復旧で認定する。」
