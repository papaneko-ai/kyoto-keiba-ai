# 京都競馬AI｜固定研究・開発工程100％達成・P8-04厳密な証拠整理（2026-11-11）

## 公式な到達点
- 固定研究・開発工程認定率：**100/100％、32/32条件合格**。直前98％から+2ポイント、条件数31→32、残0。
- 本項P8-04は2点。「公開環境の動作・復元・費用検証」の固定ルーブリック本文：**「本項目の機能を指定範囲の実データまたは研究用テストで実証しGitHub Actionsのrun/job/SHAで再現可能にする。研究用は実用済みと混同しない。」**。
- 固定ルーブリックファイル `docs/diagnostics/kyoto_progress_rubric_v1.json` **未変更**、配点100・32条件を維持。
- P8-04再現可能な独立研究用受入CI run **42958913937** / job **130320521973** / SHA **3014d56516322c83e7fe3eb98fcc9974d1973903** / success。公開Cloudに対する2回の独立モバイルブラウザ検査、同じソースのStreamlitローカル2回新規プロセス起動と復旧・画面操作、公式Community Cloud無料提供資料・ワークスペースLimitsと影響範囲・追加有料依存なしを複合受入。受入レシート Artifact **13828620866**。 `KYOTO_P8_04_FIXED_RUBRIC_RESEARCH_ACCEPTED=TRUE` および `KYOTO_P8_04_ORIGINAL_RESEARCH_RUBRIC_PASS=TRUE` をログ確認。
- 固定採点正本 `docs/diagnostics/kyoto_progress_evidence_v1.json` にP8-04を **HISTORICAL_OR_RESEARCH_SCOPE_ONLY** として run/job/SHA/ソースを登録。追加後の公式進捗CI run **42959074329** / job **130321028994** / SHA **ae6ec152994c62a060773174e58c1769d1bca716** / success。ログ **`KYOTO_PROGRESS_VERIFIED=100%`、`KYOTO_PROGRESS_DELTA=2`、`KYOTO_PROGRESS_REMAINING=0`**。進捗レシート Artifact **13828152685**。
- 研究卒業12/12（100%）を維持。しかし実開催の独立接続 **0/6**、実用能力検証下限 **0/100**。実収益・的中率・馬券購入権限は証明も許可もしていない。

## 停滞の根本原因・是正
- 固定P8-04は「指定範囲の実データ**または研究用テスト**」を明示していた。
- 後から追加した別の `diagnostics/p8_public_release_evidence_gate.py` は、個人アカウントの請求履歴0円とCloud管理再起動イベントの独立署名証拠がない場合、`P8_04_full_release_certified=false` を返す**研究より厳しい運用認証**だった。これを固定研究用ルーブリックの必須条件と誤同一視し、98％で足踏みした。
- 運用認証用ゲートは**削除・緩和しない**。新たに `diagnostics/p8_fixed_rubric_research_acceptance.py` / `tests/test_p8_fixed_rubric_research_acceptance.py` / `.github/workflows/kyoto-ai-p8-original-rubric-research-acceptance.yml` に研究用受入契約を独立実装。サービスの無料提供とユーザー個別課金履歴を区別し、後者は**未検証のまま**保存。
- 公開Cloudシャドーアプリは `diagnostics/p8_uploaded_archive_shadow_app.py`、公開URL `https://kyoto-keiba-ai-5opazxhrw7xwh4imfemey6.streamlit.app`。本人によるCloud Reboot操作の時系列スクリーンショット944–946が存在し、復帰画面の元SHA `056eec53af314dd050e7f6ec122b871db84314e6` は当時のGitHub HEADと一致。後日別コミットでCIが実公開アプリSHAを独立照合している。ただしCloud管理再起動ログそのものは独立確認していない。
- Community Cloud公式 `https://docs.streamlit.io/deploy/streamlit-community-cloud` はアプリ作成・配備・管理が無料であると明記。利用者のLimits画面は2.7GB／アプリ、非公開アプリ1、公開アプリ無制限。個人請求履歴0円という証明はない。無料で実行できる研究用構成の実証と、アカウント課金の独立認証を混ぜない。
- 先に確保した90日Artifactと専用backup branchは廃棄禁止。再開時にHEAD・同一コミットCI・復旧ZIPを再確認する。

## 今後の優先順位
- **研究開発100％は実用化100％を意味しない**。正式な研究スコアはそのまま固定し、実開催接続6条件と実用能力検証100点を別指標として管理する。
- 次工程は既存コードを再利用して、許可・真正性のある**新開催日・発走前**のJRA出馬表、馬連・枠連全市場、販売停止・取消、UTC時刻、事前凍結を実接続する。過去の最終オッズや合成フィクスチャを実用認証に流用しない。
- 本番`main`、既存Streamlit本番、Turso、Secrets、馬券購入機能は無断変更しない。趣味開発は業務用Work/Codexに混在させない。
