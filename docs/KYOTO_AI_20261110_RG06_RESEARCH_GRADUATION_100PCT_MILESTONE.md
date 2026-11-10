# 京都競馬AI｜研究卒業100％確定記録・次工程への移行（2026-11-10）

## 再開入口
対象 `papaneko-ai/kyoto-keiba-ai`、開発ブランチ `jra-html-diagnostic-20261105`。`KYOTO_AI_START_HERE.md` と本書、`docs/diagnostics/kyoto_progress_rubric_v1.json`、`docs/diagnostics/kyoto_research_graduation_rubric_v1.json`、`docs/diagnostics/kyoto_research_graduation_integration_claims_v1.json`、P1原本Artifact `13482994623`、最新HEAD/Actionsを照合する。既存実装のやり直し禁止。

## 固定基準の実測
- 研究・開発工程認定 **64/100、21/32**。前回比±0。実用完成率ではない。
- 研究段階卒業 **100.0％、12/12条件、統合6/6**。前回91.7％→100％（+8.3ポイント）。研究段階の固定12条件を完了。
- 独立検証済みの実競馬接続 **0/6**、独立検証済み実用能力の下限 **0/100**。これらは別々の指標。

## RG-06B新規実装
- `diagnostics/rg06_repeatable_mobile_e2e_lab.py`。既存研究用馬連/枠連確率・EV・予算・凍結・P6精算を、一時台帳2個に同条件で再実行し同じSHA256レシートを検証。2026-11-07保存済み実履歴status bytesはハッシュと母数に使い、架空オッズ/モデルを混ぜない。
- `diagnostics/p8_mobile_readonly_planner_app.py`。既存スマホ診断UIの券種・予算入力に研究用E2E再現表示を追加。実購入ボタン・実オッズや予測の虚偽表示なし。
- `tests/test_rg06_repeatable_mobile_e2e_lab.py` 10件成功。さらに `tests/rg06_mobile_browser_check.py` はStreamlitをローカル390px幅Chromium touch viewportで操作し、券種切替、研究表示、横はみ出し防止を検査。
- `diagnostics/kyoto_research_graduation.py` はGitHub run/job/SHAと過去workflow内の両テストおよびブラウザーステップ成功を実照合。現HEADでも再検証。
- 初回run `42763340477` はAppTestの不存在 `.message` 属性によりfailure。正しいテストへ修正して再実行。
- 合格初回run `42763420457`、job `129654211172`、SHA `20d53eb84cb46588dcde1b4e75d70e5b7287bfa2` success。
- 研究卒業100％採点 run `42763596635`、job `129654789638`、SHA `5bf88d6aa81c8a39660f4f612962ff3a5dd769e1` success。ログ `KYOTO_RESEARCH_GRADUATION=100.0%`、`KYOTO_RESEARCH_GRADUATION_CONDITIONS=12/12`、`KYOTO_PROGRESS_VERIFIED=64%`、`KYOTO_RESEARCH_TO_LIVE_VERIFIED=0/6`。

## 次の優先順
1. 実開催の許諾・真正性が立証された公式発走前PC/SP出馬表および馬連/枠連オッズ、取消、発売状態、正確な観測UTCをP1厳格受入口に入力。認証を研究用フラグで偽装しない。
2. 既存P3～P6の予測・EV・レース順位/予算・事前登録型仮想投資・公式結果精算を同一実開催データへ接続。実証出来なければ停止。P1-03/04等の固定32条件は証拠が無い限り合格にしない。
3. モデルの未使用時系列による独立進化・悪化復帰は研究成果から継続。ALG-01..13、EVO-01..08、P1..P8を維持。
4. 研究用テスト成功=実用成功ではない。実購入/本番app.py/main/Turso/Secretsに触れず、追加費用原則なし・スマホ優先。

## 復旧
- P1保存済み原本Artifact `13482994623`を維持。研究卒業100％時点のソース復旧ワークフロー `.github/workflows/kyoto-ai-milestone-recovery-archive.yml` が本書のpushで起動する。成功run/job/Artifactとdigestおよび同一SHA継続CIを確認してからバックアップ完成を名乗る。
- 再開時には最新HEAD/Actionsと復旧原本を独立照合し、研究卒業100％以外の進捗は新しい証拠で増減理由を報告する。
