# 京都競馬AI・P6-02研究開発87％節目／完全継続・復旧記録（2026-11-10）

## 0. 最新状態・引継ぎ正本
- GitHub: `papaneko-ai/kyoto-keiba-ai`、開発ブランチ `jra-html-diagnostic-20261105`。旧main/公開app.py・Turso・Secrets・実購入機能へ無断変更禁止。
- 最新の工程認定は**固定32項目87/100・27/32合格・未達5項目**。前回83/100・26/32に比べ+4点・+1項目。新規P6-02既定配点4点。固定基準は変更していない。
- 別の研究卒業条件は**100.0％・12/12**。独立実開催接続 **0/6**、独立検証済み実用能力下限 **0/100**。研究用の事前凍結は本物の開催日前予想を意味しない。
- 次回開始時はまず `KYOTO_AI_START_HERE.md`、本書、`docs/KYOTO_AI_20261110_P5_RANKING_83PCT_MILESTONE.md`、固定32項目と研究卒業12条件の両rubric・evidence、最新HEAD/Actions、保存済みP1実HTML原本Artifact `13482994623`、バックアップを実照合。

## 1. P6-02実装（結果を絶対に先読みしない研究用）
- `diagnostics/p6_source_bound_ranked_freeze_lab.py` を実装。入力は各レースのP1三原本bundle+snapshot+観測UTC+PC/SP+研究用事前固定モデル、P5ランキング、commit UTC、存在しない保存先のみ。
- 既存 `diagnostics/p4_source_bound_model_ev_research.py` を使って原本bytes・馬連/枠連価格・発走前時刻・モデルSHAに基づくP4比較を**毎回再実行**。改変したP4数値や捏造P5順位はP5ランキングを再計算して不一致拒否。
- P5の研究用買い目・予算上限・見送りを検証し、P3確率と原本価格を再度突合。P6既存 `freeze_fixture` と `append_record/read_journal` で同一コミット時刻、原本・P4/P5・モデルのハッシュに結び付くLAB予測を凍結。既存台帳への上書き禁止。
- 書き込み前に全レース検証、臨時フォルダで各ファイルを作成しハッシュ検証後に、新規保存先へ一括公開。結果・着順・払戻を凍結APIへ入力しない。発走後時刻・差し替えモデル・偽造レース・価格改変・重複・証拠欠損は保存前に遮断。研究用見送りは記録0件のmanifestのみ。
- 実ネットワークJRA取得、当日の外部時刻証明、公式発売・取消、実モデルの独立較正、公式結果・実際のペーパートレードは**このLAB認定で未実証**。
- `tests/test_p6_source_bound_ranked_freeze_lab.py` に13件の正常・破壊・再現性・上書き拒否テストを追加。
- 初回run `42768323613`はテストfixtureのcommit時刻が原本観測時刻より早く設定され失敗。時刻拒否条件を緩めず、fixture時刻を原本観測後に修正。

## 2. 独立可能なGitHub成功証拠
- P6-02テスト13件を含む継続CI成功 run **42768428949** / job **129670303904** / SHA `a32b1435e09561f9e578f62affbd3c957dd3d055`。この時点は工程83％。
- 固定得点台帳 `docs/diagnostics/kyoto_progress_evidence_v1.json` にP6-02を追記。根拠のrun/job/SHAと実装/テストパスはGitHub APIと過去コミット祖先性で照合。
- 固定採点 success run **42768604126** / job **129670867683** / SHA `e868cd920ca8867e18aac06ae709acc7a999ef78`。ログ：`KYOTO_PROGRESS_VERIFIED=87%`、`KYOTO_RESEARCH_GRADUATION=100.0%`、`KYOTO_RESEARCH_TO_LIVE_VERIFIED=0/6`、`KYOTO_OPERATIONAL_VERIFIED=0/100`。

## 3. 復旧・バックアップの必須確認
- 前回83％不足文書 `docs/KYOTO_AI_20261110_P5_RANKING_83PCT_MILESTONE.md` を補完。83％復旧run `42768220604` / artifact `13739904416` success。途中のP6-04「未認定」判断は誤りで、既に登録済みだったため重複加点なし。
- 本書のpushが `.github/workflows/kyoto-ai-milestone-recovery-archive.yml` を発火し、正本更新済みコミット全体のsource ZIP、SHA256SUMS、復旧manifestをGitHub Artifactで保管する。**そのrun・job・Artifact・同一SHA継続CI成功を照合した後でのみ復旧完了と報告**。元のP1 HTML原本は別Artifactに保管されるためソースZIPに含まれるとは限らない。
- 復旧ブランチは該当最終SHAに作成し、内容を正本と照合する。既存バックアップは消去しない。

## 4. 次の開発
- 固定未達5項目：**P3-02（4点）**、**P5-03（1点）**、**P6-03（4点）**、**P8-03（2点）**、**P8-04（2点）**。
- 優先は許諾・真正性と外部時刻を検証できる新開催日の実発走前JRA出馬表、馬連・枠連オッズ、取消/発売状態の取り込み、実予測→P5順位/予算→P6事前登録型仮想投資→公式確定結果の自動照合。過去確定結果やLABテストを「実開催の発走前予測成功」と偽らない。
- 合意済みALG-01～13、EVO-01～08、P1～P8、未使用時系列、悪化時復帰、馬連/枠連、スマホUI、追加費用原則0円、本番保護を維持。実用実証不足なら遮断。

## 5. 新チャット再開指示
「既存`papaneko-ai/kyoto-keiba-ai`・開発ブランチ`jra-html-diagnostic-20261105`を継続。最初に`KYOTO_AI_START_HERE.md`と本87％パック、全固定基準と証拠を実読し、最新HEAD・Actions・P1原本・復旧ZIPを照合。工程認定87％(27/32)、研究卒業100％(12/12)、独立実開催接続0/6、実用能力検証下限0/100を区別。P6-02のP1→P4→P5→凍結LAB接続を使い、実開催の真正な時点情報による予測・仮想投資・確定結果照合を開発する。再設計禁止、main/Turso/Secrets/旧公開アプリ/実購入への無断変更禁止。毎節目は成功run/job/SHAと同一SHA復旧ZIPを保全。」
