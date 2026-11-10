# 京都競馬AI P1｜実HTML原本と構造化名簿の一致検証（2026-11-10）

## 既存成果の再利用
KYOTO_AI_START_HERE.md、既存機能台帳、再開ゲート、PC/SP解析器、3独立原本検証器を先に照合。新規解析器は作らず、diagnostics/p1_three_original_dual_intake.py の既存経路に厳密な実原本照合モードを追加。

## 解消した具体的欠陥
従来の3原本チェックはHTMLのSHA256と時刻を照合する一方、構造化snapshotの馬番・枠番・馬名がracecard原本の内容と一致することを保証しなかった。保存済み原本を再パースして完全一致するか検証する racecard_channel=PC または SP を追加。偽造名簿、パース失敗、不明なチャンネルを拒否。従来の呼び出しは互換維持し、構造チェックのみで予測を許可しない。

## 同一コミットCIの独立確認
- GitHub開発HEAD 19c334280ecc5ff88868a57299e5300e56016a75
- 3原本ワークフロー run 42732185562、job 129552681634、success。3原本17件、その他13+26+8件成功。
- 再開・客観採点ワークフロー run 42732185888、job 129552686494、success。再開7件、採点14件、3原本17件、PC/SP13件成功。
- 進捗ログ KYOTO_PROGRESS_VERIFIED=31%、KYOTO_PROGRESS_DELTA=0、KYOTO_PROGRESS_REMAINING=24。
- 既存解析器依存のbeautifulsoup4をCIへ追加し、初期のSyntaxError・ModuleNotFoundErrorを修正。失敗履歴も保持。

## 完了の限界と次の実用工程
これは保存済み原本から構造化名簿への一致検証であり、JRA実サイトへの新規通信、当日公式馬連・枠連価格、取消、発売状態、許諾、予測開始を証明しない。3原本の価格表はなお構造化snapshotの主張に依存し、価格のHTML実内容との一致検証が未完。次は既存の公式オッズ解析器と保存済み市場原本の内容照合を進める。P1-03/04は未合格、固定進捗31％を維持。

本番main、Turso、Secrets、購入履歴は不変更。
