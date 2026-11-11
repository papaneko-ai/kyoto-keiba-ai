# 京都競馬AI・2026年11月11日 P5-03研究開発92％節目／継続・復旧記録

## 1. 不変の前提
- GitHub `papaneko-ai/kyoto-keiba-ai`、開発ブランチ `jra-html-diagnostic-20261105`。作業前に `KYOTO_AI_START_HERE.md`、この文書、固定32条件rubric/evidence、研究卒業12条件、最新HEAD/Actions、P1原本 `13482994623`、復旧ZIP・branchを確認。
- 研究・開発工程 **92/100（29/32合格、残り3条件）**。昨日の91％よりP5-03既定配点1点のみ加算。採点基準・配点の変更なし。
- 研究卒業 **100.0％（12/12）**、実開催接続の独立検証 **0/6**、実用能力の独立検証下限 **0/100**。研究での成功を新開催日の公式発走前予測成功とは記録しない。
- 未達：P3-02（4点）、P8-03（2点）、P8-04（2点）。研究認定100％は実用完成率ではない。

## 2. 今回実装した機能
- `diagnostics/p5_bounded_risk_capital_lab.py`。既存 `diagnostics/p5_source_bound_race_ranking_lab.py` のP4原本照合済みLAB期待値・順位レシートをSHA再検証し、100円単位で1日、1レース、1点の投資上限を重ねて満たす資金配分を追加。
- 下振れ後期待値の閾値を満たさなければ投資額0、予算の使い切りなし。最大の買い目額・レース額を明示。未較正確率に対する便宜的な上限設計であり、Kellyの統計的最適性・実利回りを主張しない。
- 不正なNaN/Inf、古いハッシュ、不正順位、重複レース、偽公式フラグ、予算不整合、過度な集中上限、不正馬番、100円未満の賭け金を拒否。正式な馬券発注機能・実開催ペーパートレードは不接続。
- `tests/test_p5_bounded_risk_capital_lab.py` 13件、既存全体CIの `Verify real manual market and ratio Streamlit controls` に追加。最初のテスト用低期待値条件を正しく作り直したが、資金安全条件は緩めていない。

## 3. 証拠
- 新機能テスト13件＋継続CI success：run **42931361336** / job **130230624011** / SHA `471a738a00d562c6a62d9cdd79c06031193bd38d`。
- 固定証拠台帳 `docs/diagnostics/kyoto_progress_evidence_v1.json` にP5-03を追加。固定再採点 success：run **42931579865** / job **130231369056** / SHA `474dd907b59b8b3f60fef0af40116303fe102ff0`。CI表示：`KYOTO_PROGRESS_VERIFIED=92%`、`KYOTO_RESEARCH_GRADUATION=100.0%`、`KYOTO_RESEARCH_TO_LIVE_VERIFIED=0/6`、`KYOTO_OPERATIONAL_VERIFIED=0/100`。
- 初回のCI run `42931298672` のfailureを合格に流用しない。後続runの全件successを採用。

## 4. 復旧と安全保持
- 本文書追加時に `.github/workflows/kyoto-ai-milestone-recovery-archive.yml` が当該SHAの `git archive` ZIP、SHA256SUMS、復旧manifestをArtifact化する。**その成功run/job/artifactと同一SHAのcontinuity CIまで実測してから復旧完成**を宣言。
- 91％の復旧branch `backup/kyoto-ai-development-91pct-20261110` とArtifact `13741471613`、独立のJRA実HTML原本Artifact `13482994623` は維持。新規branchは `backup/kyoto-ai-development-92pct-20261111`。
- main、Turso、Secrets、旧公開アプリ、実購入機能、仕事用Work/Codexの作業環境は無断変更しない。

## 5. 次に進める仕事
- 次の優先は実開催データへの独立した正本取得・観測UTCの真正性・許諾・出走/発売/取消の真正照合。P1→P3実モデルと原本オッズ比較→P5資金管理→P6事前登録型仮想投資→公式結果確定精算→P7未使用時系列進化→P8スマホ表示を接続する。
- 研究用テスト通過を実際の開催実績として報告しない。16:00終業のため、作業区切りではHEADと同一コミットのCI/ZIP証拠を保存し、進捗数値は増減理由とともに通知する。
