# 京都競馬AI・P6-03研究開発91％・本日最終節目／完全引継ぎ・復旧記録（2026-11-10）

## 1. 最新HEAD検証で継続すること
- 対象リポジトリ `papaneko-ai/kyoto-keiba-ai`。開発ブランチ `jra-html-diagnostic-20261105`。必ず最初に `KYOTO_AI_START_HERE.md`、本書、固定32条件rubricとevidence、研究卒業12条件rubricとclaims、前回 `docs/KYOTO_AI_20261110_P6_RANKED_FREEZE_87PCT_MILESTONE.md`、最新GitHub HEAD/Actions、P1実原本Artifact `13482994623`、復旧Artifactを実照合する。
- **研究・開発工程認定91/100、固定32条件中28合格、未達4**。前回87/100、27/32よりP6-03既定配点**+4点、+1項目**。配点・基準の事後変更なし。
- **研究段階卒業100％・12/12**維持、**実開催接続の独立検証0/6**維持、**独立実用能力下限0/100**維持。研究用の自動精算は本物の新開催日の発走前予測・公式払戻実績ではない。
- 未達4項目と固定点：P3-02（4点、実データで市場とモデル同条件比較）、P5-03（1点、実モデル資金リスク最適化）、P8-03（2点、実開催データ・予測・仮想精算連携）、P8-04（2点、公開環境の動作・復元・費用検証）。

## 2. 今回実装したP6-03
- 新規 `diagnostics/p6_final_html_settlement_lab.py` は、以前に実装した `diagnostics/p6_source_bound_ranked_freeze_lab.py` の**書換不能な元LAB凍結台帳**と、保存済みJRA形式のオフライン結果HTMLを接続。既存 `diagnostics/extract_kyoto_payouts.py` のVisibleText、`diagnostics/p6_fixture_durable_ledger.py` のSHAハッシュ連結台帳・追記/再読込、`diagnostics/p6_virtual_settlement_fixture_lab.py` の訂正・収支数理を再利用。
- 事前凍結台帳とmanifestの外部SHA256照合、開催日/レース番号/券種/結果見出しの一致、馬連と枠連の明示的な区分、重複/曖昧な払戻表・締切以前の結果・偽公式scopeの拒否を実装。結果/払戻情報を発走前凍結へ逆流させない。
- 精算前にレース単位で全結果を解析・検証し、別の新規ディレクトリへ結果イベントを追加した台帳コピーを保存。元の凍結台帳は変えず、結果訂正版はversion=2以降の新規スナップショットとして保存する。重複/旧version、改変/古いSHA、既存保存先への上書きを拒否。
- 新規テスト `tests/test_p6_final_html_settlement_lab.py` 15件。勝ち/外れ、払戻訂正、同一入力再現、元台帳保全、日付・レース・券種の誤対応、不正な時刻/HTML/公式scope、欠損、ハッシュ改変、重複禁止を実際にテスト。
- **許容性と限界**：入力HTMLはテスト用JRA形式LABであり、GitHubの研究CIは外部のJRA発表・公式払戻の真正性、原本捕捉UTC、公式取消/返還全パターンを証明しない。抽出済みの過去結果情報を、実開催発走前予測の検証実績に流用しない。実運用の自動精算は未達。

## 3. 今回発見したルート原因と再発防止
- P6-03の新機能15件/全体CI初回は成功：run `42769571233` job `129673934089` SHA `60b82ed29847fb867d4a54e83f1a0afd3047f7ed`。
- 証拠登録後run `42769762278`で既存P4-02同一入力再現テストに偶発FAIL。原因は `diagnostics/jra_p1_offline_handoff.py` 内ZIPのファイル作成時刻属性が2秒単位で変わり、同一原本でもZIP SHAが異なること。同一値再実行の整合問題でありP6-03の精算数理失敗ではない。
- バグをテストだけで抑えず、共通export_bundleで各ZIPメンバーのZipInfo日時 `1980-01-01 00:00:00` とファイル属性 `0600` を明示固定。従来形式のZIPのimport互換性は維持。 `tests/test_jra_p1_offline_handoff.py` に決定論と過去形式受入の破壊テストを追加し、全体CIに組込み済み。保存済み原本Artifact/以前のバックアップを上書きしない。
- ルート原因修正後の最終採点成功 **run `42769933332` / job `129675093819` / SHA `2730f4f23ef406dd7101b6494f4ac3e95d8b6448`**。CIログ：`KYOTO_PROGRESS_VERIFIED=91%`、`KYOTO_RESEARCH_GRADUATION=100.0%`、`KYOTO_RESEARCH_TO_LIVE_VERIFIED=0/6`、`KYOTO_OPERATIONAL_VERIFIED=0/100`。
- 固定証拠台帳 `docs/diagnostics/kyoto_progress_evidence_v1.json` はP6-03に初回成功run/job/SHAを格納し、現HEADの全体再実行でP6-03の固定4点を再確認する。

## 4. 正本と復旧バックアップの検証
- ルート `KYOTO_AI_START_HERE.md` には現行91％とP6-03の取得・精算内容、ZIPルート原因修正、認定run/job/SHA、未達4条件を記録済み。
- `.github/workflows/kyoto-ai-milestone-recovery-archive.yml` は本書追加をトリガーに、**同一HEADのソースZIP**、`SHA256SUMS.txt`、`RECOVERY_MANIFEST.txt` をGitHub Artifactに保存する。実際の成功run/job/Artifact・最後の同一SHAのcontinuity CI successを確認してから復旧完了を報告。
- 既存の87％バックアップ専用ブランチ `backup/kyoto-ai-development-87pct-20261110` とArtifact `13740747635`、元JRA実HTML復旧Artifact `13482994623` を削除しない。ソースZIPには別保管の原本が含まれないことがある。
- 新規バックアップbranchは`backup/kyoto-ai-development-91pct-20261110`を当該HEADに固定する。成功run/job/SHA/digest/Artifactは確認できた値だけ報告する。

## 5. 次回の開発
- ユーザーの本日終了指示により**この節目で作業を終える**。次のセッションでは、許諾済みの新開催日JRA公式発走前データ・出馬表・馬連/枠連オッズ・観測時刻・発売・取消の独立証拠を優先し、P1→P3/P4→P5→P6凍結→公式確定結果→P7未使用時系列/自動復帰→P8スマホ画面の実接続を行う。
- ALG-01～13・EVO-01～08・P1～P8の合意事項維持。既存機能の再実装、研究実績の実績詐称、main/Turso/Secrets/旧公開アプリ/実購入/公開モデルの無断変更は禁止。

## 6. 新チャット継続指示
「既存`papaneko-ai/kyoto-keiba-ai`の`jra-html-diagnostic-20261105`を継続。最初に`KYOTO_AI_START_HERE.md`と本91％パック、固定32基準・研究卒業12条件のrubric/claims、GitHub最新HEAD、Actions、原本・復旧ZIPとSHAを照合。研究・開発工程91％(28/32)、研究卒業100％(12/12)、独立実開催接続0/6、独立実用能力下限0/100は別指標。P6-03研究用自動精算とP1 ZIP決定論修正を引き継ぐ。残りP3-02、P5-03、P8-03、P8-04を旧実装から継続し、実開催発走前の真正・許諾証拠を最優先。main/Turso/Secrets/旧公開アプリ/実購入への無断変更禁止。節目は固定得点の増減理由、全体CI success run/job/SHA、同一SHA復旧バックアップまで実証してから報告。」
