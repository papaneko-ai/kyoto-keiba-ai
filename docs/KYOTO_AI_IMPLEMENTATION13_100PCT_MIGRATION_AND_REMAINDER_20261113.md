# 京都競馬AI・実装13｜取得前準備100％移行・継続資料

作成日：2026-11-13。対象：`papaneko-ai/kyoto-keiba-ai`、開発ブランチ `jra-html-diagnostic-20261105`。

## 重要：認定はCIとバックアップが同一HEADで成功した場合のみ

この資料そのものは成功証明ではない。GitHubの当該HEADのActions `Kyoto AI objective progress and continuity gate` と `Kyoto Implementation12 verified migration source and history backup` の双方がSUCCESS、かつR16復元・固定採点が16/16であることを確認してから取得前準備100％と確定する。最新HEADはGitHubから確認し、以前のHEADを再利用しない。

## 固定16項目

R01～R15は既存の合格受入テストを保持。R16は `diagnostics/r16_full_lab_e2e.py` と `tests/test_r16_full_offline_e2e_acceptance.py` にて合成LAB入力をP2→P3→P4→P5→P6→P7→P8へ通す。7系統特徴量の検証、予測、全組合せ合成市場、100円単位の予算、仮想凍結、確定払戻・訂正と永続台帳、8種類のEVO反証・後続期間ロールバック、スマホ安全停止を同一固定packetに束ねる。異なる2つの一時環境で再生し、さらに台帳を別ディレクトリへ複製・SHA検査・再読込する。

**注意：この統合はLABの配線・再現性確認。実際のJRA出走・オッズの真正性、予測精度、実開催のペーパートレード成功、P7の本番モデル昇格、実馬券の取引を認証しない。**

## 原来の正式評価に戻す条件

固定16ゲートを同一HEADのCIで16/16 PASSした場合、`kyoto_predata_readiness.py` は `revert_to_original_scoring_now=True` とする。以後、取得前準備完成率で進捗を表示・加点し続けない。原来の工程認定、研究段階卒業、実開催接続、実用能力等の指標は、原来の固定算出コードと当該HEADの実際のCI出力で表示する。旧値や推定を自動的に加点しない。

## R04の独立残課題（取得前準備100％に含めない）

Bolton–Chapman型・Benter型の市場連動正式式、P4市場確率と独立予測確率の結合、当日オッズ時点の整合、独立時系列データによる較正・回収率検証は未完了。研究用近似版を原論文完全実装と呼ばない。既存 `p3_r04_model_families_lab.py`、`p3_same_cutoff_market_model_bridge.py`、`p4_source_bound_model_ev_research.py` を再利用し、R15/R16終了後も並行改修する。

## 引継ぎ運用と保護境界

- `main`、本番Turso、Secrets、公開Streamlit、実馬券購入経路を無断変更しない。
- R01～R16の固定分母・受入条件を変更しない。既存研究コード・テストを新実装前に確認し、修理・統合を優先する。
- 再開時はGitHubのHEAD、Actions Run/Job/Artifact、SHA256・Git bundle・復元テストを照合する。復旧ZIPには外部Turso、Secrets、外部JRA原本Artifactは含まれない。
- セクションが長くなる前にこの資料と最新HEAD・CI・復旧Artifact・正式進捗を用いて移行アラートを出す。
- 次段階は実開催のJRA取得成功（11月14日・失敗時15日の二段構え）、P1の時点別原本取得・独立証明、R04市場モデルの市場連動化、P1～P8の実開催接続を優先する。2026-11-07終了開催の情報を現在の発走前情報に流用しない。

## 新セクション開始指示文

「京都競馬AI開発・実装14として継続。まず本移行資料と恒久研究再利用規則、固定評価の受入記録をGitHubで実読し、開発ブランチの最新HEADと同一HEADのCI・復旧ZIPを照合する。取得前準備16/16を証拠により確定した場合は元の正式評価基準に復帰する。R04市場連動モデル完全化とJRA実開催接続を並行して進め、過去の成功テストの再実施を無意味に繰り返さず、main・Turso・Secrets・公開アプリを保護。正式指標を毎回定量報告し、次の大きな節目まで継続する。」
