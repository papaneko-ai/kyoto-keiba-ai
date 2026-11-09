# 京都競馬AI｜開発再開の唯一の入口（2026年11月9日以降）

**このファイルはチャット移行・開発再開の最初に必ず読む。** 静的な移行パックの「原本未発見」「次のバッチ番号」を、そのまま現在の事実と解釈しない。

## 1. 最初に読む正本
- `docs/diagnostics/kyoto_ai_resume_evidence_registry_v1.json`：固定済み原本、Artifact、保存済みSHAと参照先の機械可読台帳
- `docs/KYOTO_AI_20261109_REAL_HTML_84_REPARSE_AND_RECOVERY_MILESTONE.md`：再発見・再解析済みの**本物のHTML84頭・過去走485件・特徴量335項目**
- `docs/KYOTO_AI_20261106_FINAL_BACKUP_VERIFIED_RECEIPT.md`：既存復旧用Artifact `13482994623` の発見・保存事実
- `docs/diagnostics/jra_p1_batch14_96_profiles_20261106/status.json`：歴史的累積96頭／未取得52頭／592件
- `docs/KYOTO_AI_ALGORITHM_REQUIREMENTS_REGISTER_v1_20261106.md`、`docs/KYOTO_AI_ALGORITHM_AND_EXECUTION_ROADMAP_20261106.md`、`docs/KYOTO_AI_CONTINUITY_AND_STAGE_GATE_RULES_20261106.md`：ALG-01～13、P1～P8、EVO-01～08を維持

## 2. 開発開始前の必須実行
対象：`papaneko-ai/kyoto-keiba-ai`、ブランチ `jra-html-diagnostic-20261105`。現在HEADは毎回GitHubに実問い合わせを行う。古いドキュメント記載HEADを最新値として使わない。

GitHub保存済みのアーティファクトの存在を **GitHub APIから毎回** 再確認し、保存したJSONを使って以下を実行：

```bash
gh api repos/papaneko-ai/kyoto-keiba-ai/actions/artifacts/13482994623 > /tmp/kyoto_recovery_metadata.json
python -m diagnostics.kyoto_resume_gate --root . --artifact-json /tmp/kyoto_recovery_metadata.json --out /tmp/kyoto_resume_receipt.json
```

API上のArtifactを利用できない場合は、保存済みの復旧ZIPを指定して独立SHA照合できる（ZIPは保管先から取り出す必要がある）：

```bash
python -m diagnostics.kyoto_resume_gate --root . --local-recovery /path/to/KYOTO_AI_P1_REAL_ORIGINAL_84_REPLAY_VERIFIED_20261109.zip --out /tmp/kyoto_resume_receipt.json
```

**ゲート終了コード2なら新規実装・再収集へ進まない。** 記録された原因を確認し、既存原本・正本の所在を修復する。実行レシートの「合格」は既知資料の参照整合だけを意味し、JRAライブ自動取得や予測を許可しない。

CIも `.github/workflows/kyoto-ai-resume-evidence-gate.yml` で同じ処理を行う。CIログ・run IDが実際に確認されない段階ではGitHub Actions成功と主張しない。

## 3. 再調査禁止ではなく、**無駄な再調査禁止**
- 「HTML原本がない」と即断しない。まず復旧Artifact ID `13482994623` とダウンロード済み別保全ZIPの照会。
- 2026-11-07京都の148頭：96詳細確認済み。そのうち**84頭の原本を復旧・再解析済み**、残る**12頭（各レース1番）の元PC原本は未復元**。未取得52頭は別分類。
- 原本84頭の有効過去走485件、残る12頭の台帳記録107件、合計592件。335特徴量の再計算一致。
- 原本が見つかったことを「発走前の新開催日データ取得」「公式オッズ取得」「予測準備完了」とは混同しない。
- 完了済みURL・バッチを重複してGETしない。JRAの利用許可未確認の自動アクセス禁止。
- **新しい問題**が見つかったら対象・証拠・原因・修正・検証・残りの問題を保存し、同根の事故を検索。復旧したバックアップは消さない。

## 4. 次の実開発位置
P1は未完了。**新開催日の許容されたデータ取得経路と発走前の馬連／枠連オッズを確立する工程**が優先。過去に解決したZIP復旧・84頭の再解析・研究用P6数理テストを、証拠なしに繰り返して進捗とみなさない。P1の未完がある間、P3～P6は研究用コードであり実用運用完了ではない。

## 5. 安全保護
本番 `main/app.py`、Turso、Secrets、公開モデル、実購入履歴はユーザー承認なしに変更しない。無料／スマホ中心を維持し、趣味を業務用Work/Codexと分ける。

## 6. チャット移行時に貼る短文
「京都競馬AI既存開発を継続。まずGitHubの `KYOTO_AI_START_HERE.md` を読み、`kyoto_ai_resume_evidence_registry_v1.json` と `kyoto_resume_gate.py` で原本・バックアップ・最新進捗を照合。84頭の実原本再解析と485過去走・335特徴量は既達で繰り返さない。Artifact 13482994623と携帯用復旧ZIPを先に探し、原本不在と誤認しない。P1～P8・ALG01～13・EVO01～08を維持。現在の未完P1（新開催日の合法的な出馬表と発走前馬連/枠連オッズ）から進め、本番main/Turso/Secretsは保護する。ゲートの証拠確認なしに工程を進めない。」
