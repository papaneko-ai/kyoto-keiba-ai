# 京都競馬AI・2026-11-11 P3同一原本・同一締切モデル比較の実装／研究開発94％維持節目

## 1．正本・固定の開発状況
- GitHub `papaneko-ai/kyoto-keiba-ai`、開発ブランチ `jra-html-diagnostic-20261105`。起点：`KYOTO_AI_START_HERE.md`、`docs/KYOTO_AI_20261111_P8_SHADOW_PIPELINE_94PCT_MILESTONE.md`、固定rubric `docs/diagnostics/kyoto_progress_rubric_v1.json` と証拠台帳、研究卒業12条件、P1実原本復旧Artifact `13482994623`、HEAD/Actions、旧94％バックアップ。
- **固定研究・開発工程認定94/100（30/32合格）**：前回94％から**増減0**。未達：P3-02（4点）とP8-04（2点）、計2条件・6点。
- **研究段階卒業達成率100.0%（12/12）**：前回同値。
- **実開催接続独立検証0/6、独立実用能力下限0/100**：前回同値。研究用の比較エンジンは公式発走前の実開催モデル比較を立証せず、実用認定・馬券購入につながらない。

## 2．今回実装したエンジニアリング上の節目
- `diagnostics/p3_same_cutoff_market_model_bridge.py` を追加。既存P1三原本・観測時刻・P4原本照合付き期待値を**両モデルに対して同じbundleとsnapshot**で再計算。
- 新旧2モデルは別version、同一研究用特徴量SHAの申告、両者が観測以前に凍結、同じ京都レース・出走馬・予測締切という条件でのみ比較可能。
- 馬連・枠連の市場全組合せについて、両モデルの期待値、下振れ期待値、両者の差をペアごとに保存。同一原本・スナップショット・市場監査SHAをレシートで固定。結果ラベル、払戻や事後成績は比較入力に使わない。
- `tests/test_p3_same_cutoff_market_model_bridge.py` に新規13件。市場価格偽装、異なる特徴量、出走馬欠落、未来凍結時刻、偽公式フラグ、締切後観測、別レースなどを拒否する。
- 初回のfail CI run `42934731950`はfuture-freeze違反を一般例外で包む問題を発見。`diagnostics/p3_same_cutoff_market_model_bridge.py` の例外捕捉を正しい境界に分離して、未来時刻による拒否理由を保持。安全判定は変更せず、CI再実行。
- **全13件と全体CI success**：run `42934841261` / job `130242221876` / SHA `46ebbcd44b71990ae6f4ef9808f79b964b2a9519`。最終CIログ：`KYOTO_PROGRESS_VERIFIED=94%`、`KYOTO_RESEARCH_GRADUATION=100.0%`、`KYOTO_RESEARCH_TO_LIVE_VERIFIED=0/6`、`KYOTO_OPERATIONAL_VERIFIED=0/100`。
- **P3-02の固定4点は今回加点しない**。使用モデルはLAB_SYNTHETIC_ONLYであり、特徴量SHAは同一性のみ検査し独立した実証ではない。実開催の公式発走前データ、正式採用モデルの予測と較正、同一時刻の市場との比較は未実証。この不足を単にテスト通過で上書きしない。
- 比較に用いたサンプル研究原本は2頭の最小fixture。2頭の場合馬連の成立組合せは1つなので、今回のテストは結線・照合・改変拒否の証拠であり、**多頭数の実市場における新旧モデルの識別力検証の証拠ではない**。

## 3．次に必要な独立証拠
- 許容されたPC/SP取得経路で新開催日の公式出馬表、発売中の馬連/枠連全組合せ、取消/発売状態を発走前に捕捉。**公式由来・取得UTC・対象レースIDを外部証拠で認証**。
- 学習済みモデルと比較モデルの双方について、凍結前の特徴量・モデル版・事前予測を固定し、結果を見ない同一cutoffの出力で市場と比較。馬連/枠連の全ペア、Brier・対数損失等は別の未使用開催日に独立採点。データ不足時はfail closed。
- もう一つの未達P8-04は**実際に公開されたStreamlit Community CloudのURL、画面動作・復旧動作・費用の実測**が必要。ローカルChromium二回起動成功は代替証拠にならない。
- ユーザー指定の進捗報告は**2列・7行の「最終確認項目／結果」**で固定。項目順：研究・開発工程認定率、研究段階卒業達成率、前回からの進捗、最終HEADの継続CI、ソースZIP・SHA256記録、復旧専用ブランチ、未達の固定項目。成功未確認時には「未確認」と書く。
- main、旧公開app.py、Turso、Secrets、実購入機能を変更しない。原本Artifact、既存バックアップを消さない。

## 4．復旧工程
- 本書およびルート `KYOTO_AI_START_HERE.md` のpushで `.github/workflows/kyoto-ai-milestone-recovery-archive.yml` を起動。**同一HEAD**のGit source ZIP、`SHA256SUMS.txt`、`RECOVERY_MANIFEST.txt`、全体CIの成功を確認して節目完了とする。
- 今回のバックアップ分岐名は `backup/kyoto-ai-p3-paired-market-94pct-20261111`。run/job/Artifact ID、最終SHAはAPI実確認したものだけ最終報告で記載する。
- 新チャットでは、研究開発94％・研究卒業100％・実開催接続0/6・実用下限0/100を区別し、このP3比較処理を再実装せず、真正な公式原本と実モデルに結び付ける。
