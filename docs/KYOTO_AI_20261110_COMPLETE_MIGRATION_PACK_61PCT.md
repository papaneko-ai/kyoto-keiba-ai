# 京都競馬AI・61%節目／新チャット移行パック（2026-11-10）

## 正本と再開地点
- リポジトリ `papaneko-ai/kyoto-keiba-ai`、作業ブランチ `jra-html-diagnostic-20261105`。main・旧app.py・Turso・Secrets・実購入は変更しない。
- 最新固定32項目ルーブリック `docs/diagnostics/kyoto_progress_rubric_v1.json`、採点証拠 `docs/diagnostics/kyoto_progress_evidence_v1.json`、実用能力別採点 `diagnostics/kyoto_operational_readiness.py`。
- 今回P7-01：`diagnostics/p7_approved_evo_capability_screen.py` は正式な `docs/diagnostics/kyoto_ai_evolution_requirements_manifest_20261106.json` のEVO-01..08を別々に扱い、研究用候補の不足・反証を検査する。HYP-01..08とは別物。実際の独立進化認定・モデル自動採用は未実装。
- CI受入 run `42757592297` / job `129635465960` / SHA `e6e908e3eef00ac6ea8b749bdee3a9d1fedb5a27` success。採点run `42757698770` / job `129635808906` / SHA `18cf965aa361825b57a9c9e1eead8a359e339c89` success。研究工程**58→61点、20/32合格、12未達**。独立検証済み実用能力の下限**0/100**。両者を混同しない。

## 確定済み工程・原本
- P1の過去開催JRA実結果HTMLと保存済み原本、2026-11-07京都12R148頭、96頭プロフィール確認等を再取得し直さない。履歴最終オッズを発走前価格として使わない。原本の復旧・SHA・証拠台帳を尊重。
- 直近の研究工程の実装節目：P5-04馬連/枠連・手動比率UI 52→53、P8-02履歴モニタ＋予算スマホ統合53→56、P4-04下振れ・市場歪み56→58、P7-01正式EVO8機能の研究用候補・反証58→61。
- 合意済みALG-01..13、EVO-01..08、P1..P8、仮想投資と実購入の厳密分離、モデルの新旧比較・悪化時復帰・未使用時系列検証、ビッグデータ条件発見は維持。旧公開app.pyを新設計の土台にしない。

## 未完・次に優先
1. 許諾済み新開催日の公式PC/SP出馬表、発走前馬連/枠連オッズ、発売・取消・取得時刻の独立証拠を得てP1-03/04を実証。許諾のないHTTP取得をしない。
2. 同時点実データによるモデル比較P3-02、実EV P4-02/03、実レース最適化P5-02/03、実発走前事前登録型仮想投資P6-02と公式払戻精算P6-03、独立進化認定P7-02、実開催のエンドツーエンドP8-03/04。合格根拠なしに点数を上げない。
3. 実用能力採点は現状0点の**検証済み下限**。証拠なしで「アプリ全体0%完成」とは表現しない。CIで独立証拠を検証する具体的機構も未完。
4. 再開時はGitHub HEAD/Actions/保存済み原本所在と `KYOTO_AI_START_HERE.md` を実読し、`python -m diagnostics.kyoto_resume_gate --root . --artifact-json /tmp/kyoto_recovery_metadata.json --out /tmp/kyoto_resume_receipt.json` を実行。既存成功を再実験しない。

## 継続指示
ユーザーの「次の大きな節目」は**固定進捗%が前回値を超え、実装とCIで確認されること**。研究点と実用点を必ず別々に表示。確認質問を繰り返さず次の認定節目まで進めるが、独立証拠のないライブ能力を認定しない。節目ごとに証拠run/job/SHA・復旧ブランチ・移行文書を保存する。個人趣味のため業務用Work/Codexと分離。
