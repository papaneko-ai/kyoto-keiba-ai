# 京都競馬AI・64%認定節目／完全継続・復旧指示（2026-11-10）

## 0. この文書の意味
既存プロジェクト `papaneko-ai/kyoto-keiba-ai` の固定32項目に基づく研究・開発工程認定 **61%→64% (+3点、21/32条件合格、11条件未達)** の証拠記録。これは「本番の完成度64%」「勝率64%」「モデルが実運用で進化済み」という意味ではない。独立検証済み実用能力の下限は **0/100**。

## 1. 正本とGitHub証拠
- ブランチ `jra-html-diagnostic-20261105` を唯一の開発対象とし、毎回最新HEADをAPIで確認する。
- まずルート `KYOTO_AI_START_HERE.md`、本書、前回 `docs/KYOTO_AI_20261110_COMPLETE_MIGRATION_PACK_61PCT.md` を読む。
- 固定基準 `docs/diagnostics/kyoto_progress_rubric_v1.json`、証拠 `docs/diagnostics/kyoto_progress_evidence_v1.json`、採点器 `diagnostics/kyoto_progress_metrics.py` を変更せず監査する。
- P7-02研究用アルゴリズム受入：Actions [run 42758568349](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42758568349)、job `129638601943`、SHA `6c6e7ad276d45321205391f5f615ea56044f146b`、success。独立研究用Brier・符号検定・多重比較保護12件合格。
- 固定採点：Actions [run 42758669822](https://github.com/papaneko-ai/kyoto-keiba-ai/actions/runs/42758669822)、job `129638928419`、SHA `2f63f29da63920dce961ab77bf5ee6c08541875d`、success。CIログに `KYOTO_PROGRESS_VERIFIED=64%`、`KYOTO_PROGRESS_DELTA=3`、`KYOTO_PROGRESS_REMAINING=11`、`KYOTO_OPERATIONAL_VERIFIED=0/100`。
- 認定対象P7-02は**研究用の独立判定アルゴリズムの受入**に限る。実世界での外部由来・時刻・モデル性能の独立証明は存在しない。正式モデル進化認定や自動昇格は未実装。

## 2. 今回の実装（既存機構の拡張）
1. `diagnostics/p7_independent_holdout_research.py`: 訓練完了→研究計画固定→未知時系列の同一レース比較、重複/追加レース・時間逆転・不適切な役割分離を拒否し、研究候補を判定。
2. `diagnostics/p7_independent_research_certification.py`: 別計算経路のBrier損失、レース単位の正確片側符号検定、多重比較（Bonferroni）を導入。独立アルゴリズム同士が改善方向で不一致なら拒否。
3. `tests/test_p7_independent_holdout_research.py` と `tests/test_p7_independent_research_certification.py`：各12件の正常・破壊テスト。未来漏洩、試験対象差替え、成績悪化、偶然の一勝、多数候補比較、メタデータ改変、権限分離を含む。
4. 既存 `.github/workflows/kyoto-ai-always-run-continuity.yml` で上記を常時回帰検証。P7-01/P7-03/P7-04既存実装・P1の保存済み原本は変更していない。
5. `.github/workflows/kyoto-ai-milestone-recovery-archive.yml` は本書へのpush時だけ開発ブランチのGit追跡ファイルZIPとSHA256SUMSを保存する。**Artifactの成功run/jobとdigestを確認するまでバックアップ完成と扱わない。**

## 3. 復旧
- P1原本の既存復旧用 GitHub Actions Artifact `13482994623` と保存済み別ZIPを失わない。復旧原本84頭（485過去走、335特徴量）、2026-11-07京都12R148頭の出馬表、96頭プロフィール／原本未復元12頭、未取得52頭はそれぞれ別母数。再取得して成果を水増ししない。
- 再開ゲート：
```bash
gh api repos/papaneko-ai/kyoto-keiba-ai/actions/artifacts/13482994623 > /tmp/kyoto_recovery_metadata.json
python -m diagnostics.kyoto_resume_gate --root . --artifact-json /tmp/kyoto_recovery_metadata.json --out /tmp/kyoto_resume_receipt.json
```
- GitHub Actionsの同一SHAの連続成功、固定採点Artifact、運用能力Artifactを検証。証拠なしにHEADや得点を転載しない。
- 復旧ブランチまたはGitHub Actions Archiveを参照する場合は、生成元HEAD・SHA・ZIP checksumを実照合する。

## 4. 次の優先順位と変更禁止
- 未達最優先はP1-03/P1-04の**許諾された新開催日のJRA公式PC/SP出馬表と、発走前馬連／枠連の実オッズ・発売状況・取消・収集UTCの独立証拠**。許諾なし自動HTTPは行わない。
- 次に実データ同一時点予測P3-02、EV P4-02/03、レース/資金選択P5-02/03、事前登録・公式確定払戻P6-02/03、実世界独立進化認定P7、実開催E2E P8へ順次統合。旧開催の最終オッズを発走前価格とすること、研究データを実績と呼ぶことを禁止。
- ALG-01..13、EVO-01..08、P1..P8、仮想投資/実購入分離、未使用時系列、モデル悪化復帰、ビッグデータ勝利条件発見、スマホ軽量、原則無料を保持。
- **main、旧公開app.py、Turso、Secrets、公開モデル、実購入履歴・機能を無断変更しない。** 趣味プロジェクトを業務用Work/Codexと分離する。
- 毎回終了時は固定32条件の現在点、前回点、差分、増減理由、残り、Actions run/job/SHAと別途実用能力下限を表示。単純資料作成や研究用テストの数だけで加点しない。

## 5. 追加検証上の未達
今回の独立計算はLABの**二値確率**サロゲートに対するもの。馬連・枠連全組合せの実予測確率評価、実JRA公式同時点の独立証明、真正な監査者の外部署名や時刻証明、実レースでの統計的効力、正式進化証明書と本番昇格は依然未達。これらは「P7-02研究用3点」の付与によって完了したことにはならない。

## 6. チャット移行用指示
「京都競馬AI既存開発を継続。GitHubの`KYOTO_AI_START_HERE.md`と本64%パック・固定採点・P1原本台帳を実読し、最新HEAD/Actions/復旧Artifactを再照合。64%は研究・開発工程21/32条件の認定値、独立検証済み実用能力の下限0/100とは分ける。実データ新開催日のPC/SP出馬表・馬連枠連発走前オッズ・発売取消/時刻の独立証拠を最優先。過去の84頭復旧や成功テストを無駄に繰り返さず、P1..P8/ALG01..13/EVO01..08を保持し、次の実機能+同一SHA CI得点上昇まで開発。main/Turso/Secrets/旧アプリ/実購入を変更しない。」
