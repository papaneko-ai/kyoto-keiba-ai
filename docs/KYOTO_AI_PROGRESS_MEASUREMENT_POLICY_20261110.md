# 京都競馬AI｜完成率の固定100点・検証証拠に基づく測定（2026-11-10）

## 目的
従来の「45％」は主観的な見積りであり、実測値に引き継がない。P1～P8を25／10／15／10／5／15／10／10点、32の固定合格条件に分解し、合格をGitHub Actionsのrun・job・コミットSHAと現存する根拠ファイルで確認した分だけ加点する。

根拠の正本は docs/diagnostics/kyoto_progress_rubric_v1.json、docs/diagnostics/kyoto_progress_evidence_v1.json、減少理由の台帳は docs/diagnostics/kyoto_progress_regressions_v1.json。採点器は diagnostics/kyoto_progress_metrics.py、破壊テストは tests/test_kyoto_progress_metrics.py。

## 運用
- 既存の「Kyoto AI always-run resume and reuse gate」の同じワークフローへ採点処理を組み込む。開発ブランチのpushで、まず既存の原本復旧・再利用ゲートを実行し、破壊テストと既存のGitHub CI run/job/SHAのAPI確認を実施する。Actionsを新設して通知を倍増させない。
- ワークフローは採点の成功時、Artifact「kyoto-ai-progress-report」に kyoto-progress.json を保存する。次回は前回の同名Artifactから固定基準の差分を計算する。Artifact有効期限により前回結果が見つからなければ、比較不能と明記し差分を推測しない。
- 発行済みの合格条件が減る場合、事故台帳に条件ID・減少理由（IMPLEMENTATION_REGRESSION または PREVIOUS_ACCEPTANCE_ERROR）・説明・GitHub証拠URL・復旧条件がないとCIを失敗させる。基準やテスト数の変更だけで減点しない。
- 新たな機能追加は固定100点に混ぜず、別スコープの進捗を作成する。過去の固定基準の完成率と混同しない。
- 実行方法（認証済みGitHub Actions環境）：python -m diagnostics.kyoto_progress_metrics --root . --out /tmp/kyoto-progress.json
- ローカル実行でもGitHub認証された gh と GH_TOKEN が必要。オンライン証拠が取得できない場合は安全停止し、得点を「実測」と偽らない。

## 評価範囲の明示
歴史的実JRA出馬表12R/148頭、実原本84頭再解析、研究用の理論確率・期待値・上限見送り・P6仮想清算、読取専用診断UIは「各部分機能の合格」とする。一方で、許容された実発走前出馬表・馬連/枠連オッズ・取消・学習済較正モデル・公式結果自動採点・P7自己進化・P8新スマホ本番アプリは未合格とする。

**成果としての確率・勝率・利益を示す指標ではない。** 現状のコードが存在するだけでは合格としない。32条件の配点が完了までの開発時間の割合を意味するわけでもない。

## 検証・保護
初回は過去4系統の成功runをGitHub APIで再照合してから実測値を確定し、同一コミットのCI実ログとArtifactを確認する。既存の原本復旧Artifactを削除せず、本番main、Turso、Secrets、実購入履歴を変更しない。固定基準を変更する場合は過去基準の値を残し、旧・新の両方の指標を比較する。
