# 京都競馬AI・研究卒業66.7％節目／完全引継ぎ・復旧記録（2026-11-10）

## 1. 確定得点と定義

開発ブランチ `jra-html-diagnostic-20261105`。
- **研究・開発工程認定得点：64/100（固定32条件中21条件、前回比±0）**。固定基準は `docs/diagnostics/kyoto_progress_rubric_v1.json`、証拠 `docs/diagnostics/kyoto_progress_evidence_v1.json`。64％はアプリ全体の実用完成率ではない。
- **研究段階卒業基準達成率：66.7％（固定12条件中8条件、前回58.3％から+8.4ポイント）**。別基準は `docs/diagnostics/kyoto_research_graduation_rubric_v1.json`。研究用個別機能6/6、統合工程2/6。未達4条件 RG-03B、RG-04B、RG-05B、RG-06B。
- **独立検証済み実競馬接続：0/6分野**、**独立検証済み実用能力の下限：0/100**（ソース未検証を意味しない）。研究卒業66.7％を実開催の予測精度や収益率と混同しない。

## 2. 新合格・RG-01Bの実装

既存の `diagnostics/p3_p6_research_no_bet.py`（馬連・枠連分布、理論期待値）と、`diagnostics/p6_virtual_settlement_fixture_lab.py`（研究用事前凍結・結果精算）および `diagnostics/p6_fixture_durable_ledger.py`（SHA連鎖、追記・再開）を新規実装で置き換えることなく統合した。

- `diagnostics/rg01_prediction_freeze_settlement_lab.py`：予測→市場EV→買い目→発走前凍結→外部状態の追記→結果再開読取を1研究用シナリオで通す。
- 発走前時刻の前後関係、母集団・枠一致、全市場価格、肯定的下限EV、見送り、馬連と同枠含む枠連を扱う。
- 結果は研究用FIXTUREの速報を精算しない。確定後だけ損益を算出。確定金額訂正は追加累計でなく置換。旧ヘッド・原本改竄・重複イベント・最終→速報逆転・結果前倒しを拒否。
- `tests/test_rg01_prediction_freeze_settlement_lab.py` に14件の統合・破壊テスト。研究用計算のみ。実JRA HTTP、実払戻、実購入、外部書込み、本番モデル変更はない。
- 確率は未較正の研究用理論分布。発走前価格および原本の真正・時刻を外部認証したものではない。

## 3. GitHub Actions認定証拠

### 研究用統合14件・最初のCI成功
- Run **42760771693** / Job **129645670787** / SHA **9d1e1a54ae8ed4c53ba4cbb13b5cfde8f9de2b49**。
- `test_rg01_prediction_freeze_settlement_lab.py`: 14 tests passed。過去に認定済みのRG-02Bも既存のまま残す。

### 固定卒業採点
- Run **42760892857** / Job **129646053022** / SHA **512ae9e8b539aa43f4d0e55b8ce201bb8a6e2076**、**success**。
- CIログ：`KYOTO_PROGRESS_VERIFIED=64%`、`KYOTO_RESEARCH_GRADUATION=66.7%`、`KYOTO_RESEARCH_GRADUATION_CONDITIONS=8/12`、`KYOTO_RESEARCH_GRADUATION_INTEGRATED=2/6`、`KYOTO_RESEARCH_TO_LIVE_VERIFIED=0/6`、`KYOTO_OPERATIONAL_VERIFIED=0/100`。
- 固定卒業基準の証拠台帳 `docs/diagnostics/kyoto_research_graduation_integration_claims_v1.json` にRG-01B（今回）とRG-02B（前回）を登録。採点器はGitHubのrun/job/SHA、CI実行時のworkflowテスト、祖先関係・元コード・現在HEAD再テストのすべてを照合。

## 4. 原本・復旧

- 既存P1原本復旧Artifact `13482994623`、バックアップブランチ `backup/kyoto-ai-64pct-20261110` 及び前回のソースZIPを維持。既に成功した原本取得工程の再試験や公開版の再構築はしない。
- 本書作成コミットで `.github/workflows/kyoto-ai-milestone-recovery-archive.yml` によるGit追跡ファイルのソースZIP、SHA256SUMS、コミット記録の保存を発火させる。**最終backupのrun/job/digestは、成功を現認してから追加・報告する。**
- GitHub HEAD/Actions/Artifactを最初に照合し、毎回次のコマンドで復旧ゲートを実行する：
```sh
gh api repos/papaneko-ai/kyoto-keiba-ai/actions/artifacts/13482994623 > /tmp/kyoto_recovery_metadata.json
python -m diagnostics.kyoto_resume_gate --root . --artifact-json /tmp/kyoto_recovery_metadata.json --out /tmp/kyoto_resume_receipt.json
```

## 5. 次に開発する条件・実競馬への接続

- RG-03B：一体経路で未来情報遮断、時系列未使用期間、クラッシュ復旧の破壊検証。
- RG-04B：同一レース評価の独立候補生成→事前固定→拒否/旧モデル保持・復帰の統合。
- RG-05B：欠損・不正価格・取消・原本不一致をP1から最終精算までの全経路で停止。
- RG-06B：研究用E2E決定論性とスマホ画面操作を一体で確認。
- 各研究用統合には実開催データ受け口を同時に設計・保全する。JRA公式PC/SP発走前出馬表、馬連/枠連オッズ、発売・取消・観測時刻の**許諾済み独立証拠**を用意できた場合のみ、同じ検証済み経路に投入する。
- 研究用シミュレーションだけを増やして最終的な実用化と切り離さない。研究卒業率、固定P1–P8進捗率、実開催への接続、独立実用検証得点を常に別々に示す。

## 6. 不変更の確定方針

ALG-01..13、EVO-01..08、P1..P8、馬連・枠連、予算上限、事前登録型仮想投資、実購入との分離、未使用時系列検証、悪化時旧モデル保持、ビッグデータ勝利条件発見、スマホ軽量・無料優先を維持。
**main、Turso、Secrets、旧公開app.py、実購入機能を無断変更しない。** Work/Codexの業務用途と趣味プロジェクトを混在させない。

## 7. 新チャットでの完全継続指示

「既存 `papaneko-ai/kyoto-keiba-ai` の開発ブランチ `jra-html-diagnostic-20261105` を継続し、新規作り直し禁止。必ず `KYOTO_AI_START_HERE.md`・本66.7％節目パック・前回64％パック・固定32条件と12条件のルーブリック・GitHub最新HEAD/Actions/保存済みP1原本Artifactを確認。研究開発64％、研究卒業66.7％（8/12、統合2/6）、実競馬独立接続0/6、実用能力下限0/100を区別。RG-03B/04B/05B/06Bを既存機能から統合し、実開催発走前の公式データ受入と並行して開発。成果はCI同一SHAで証明し、run/job/SHA、比較増減理由、バックアップを記録。main/Turso/Secrets/旧アプリ/実購入機能を変更しない。」
