# 京都競馬AI｜実装06・GitHub同一ソースでP6実行検証した拡大節目（2026年11月9日）

## 1. この区切りで解消した問題
前回HEAD `d56521640a73234db03139f464a3cbf59d8b9225` はP6永続型LAB台帳の保存・ローカル15件PASSまで進んだが、「**ローカルで実行した互換ファイルとGitHubに保存した現行ファイルのバイト同一性が未確認**」という重要な証拠欠落があった。今回その実原因を追跡し、GitHubの原本3ファイルに合うようローカル複製を修正、GitオブジェクトのSHA-1（blob）を直接再計算して同一性を証明してから、改めて実行・判定した。

| GitHub上のファイル | 確認済みGit blob SHA |
|---|---|
| `diagnostics/p6_virtual_settlement_fixture_lab.py` | `a847b3daced6e77a171ca8839a909df9ca15ec97` |
| `diagnostics/p6_fixture_durable_ledger.py` | `1680f2c421cdb44d545e76e63204ce2a9feca4b8` |
| `tests/test_p6_fixture_durable_ledger.py` | `e064fdc35334a11ed2ad607322e379d346ef61aa` |

**3ファイルともローカルGit blobとGitHub connectorの現行Git blobが完全一致。**
これは今回初めて確認できた、GitHub保存版P6の正確なローカル実行証拠である。その他のP1～P5・P6数理テスト36件・Streamlit画面のバイト同一性まで証明したわけではない。

## 2. 実際に実行した受入試験
- 同一3ファイルのPython3実行で `python -m unittest discover -s tests -v` を実行。**Ran 15 tests; OK**。
- 外部署名のない研究用 `LAB-` 例を作成し、予想のフリーズ→速報（未確定）→払戻（合成）→訂正（合成）を4件ディスクに追記。Python別プロセスでファイル・独立保管したHEADを照合し再計算。**再起動相当の復元 PASS**。
- 元の最後の正常行を削除すると、保存HEADが食い違い拒否することを実測（PASS）。
- 合成200円のチケット、合成払戻100円につき500円→400円の訂正は、1,000円→800円に**置換**、合成損益は+600円。公式競馬の記録でも投資成績でもない。
- 新受入証拠：`docs/diagnostics/p6_source_locked_local_execution_20261109.json`。
- ローカル実行レシート：`/mnt/data/kyoto_p6_durable/github_byte_identical_acceptance_20261109.json`。持ち運び用検証パック `KYOTO_AI_P6_GITHUB_EXACT_VERIFIED_LAB_20261109.zip`（SHA-256：`c44f4ff26a30be03f36de1c2af4059a135aa63c0314b03fb064f33d362233236`）。ZIPのCRC確認済み。ローカルファイルはユーザーにsandbox添付で提供。

## 3. GitHub Actionsの実際の不具合と修正
従来 `.github/workflows/jra-p3-p6-research-no-bet.yml` で研究用 `fixture replay` JSONと外部HEADを保存するPythonの `write_text` に、**改行ではなく文字列 `\\n` を連結する不具合2箇所**があった。生成されたJSONに不要な末尾文字を残し、そのままではJSONとして読めない可能性があった。今回どちらも1文字の改行エスケープへ修正。

さらに別ワークフロー `.github/workflows/jra-p6-byte-identical-acceptance.yml` を新設：
- Github checkoutされた上記3ファイルのGit blob SHAとローカル合格版の期待値を一対一検査。
- 同一コード上で15件テストを実行。
- 専用LAB台帳のファイル生成、別Pythonプロセスで再読込、独立HEADによる末尾削除検出。
- 実行時コミット・受入試験結果を7日期限付きJSON artifactとして記録。
- **GitHub Actions新ワークフローのrun ID、job ID、ログおよびPASS結果は今回取得できていない。** combined statuses空やworkflow runs空は成功・失敗いずれの確証にもならない。従来P3～P6合計51件CI成功も未確認。

## 4. 新開催日のデータと利用条件
- JRA公式一次情報 https://jra.jp/use/ （2026-11-09確認）：JRAホームページの範囲は`www.jra.go.jp`・`jra.jp`・`sp.jra.jp`。この文書だけでは、持続的な自動収集・転載/保存に関する包括的許可を証明できない。新しい自動GETは行わない。
- https://jra-van.jp/dlb/ は正式なデータ提供方式だが、2026-11-09表示で月額2,090円、Windows10/11のJV-Linkが必要。ゼロ円・スマホ主体の合意に基づき無断採用しない。
- 2026-11-07京都の既存出馬表148頭、過去走592件（プロフィールあり77頭・本人確認済みの履歴なし19頭・未取得52頭）は保持。P2履歴特徴量CSVは作成済み。
- **今なお未達の最重要点**：未発走の新京都開催の公式出馬表・全馬ID・馬連/枠連の実発走前オッズ・出走取消・正式発走時刻を適切な権限・UTC/SHAで捕捉し、P3較正モデルと結んで凍結型ペーパートレードへ運用すること。原本長期保全、JRA利用条件、合法的な無料自動取得方式は未解決。

## 5. 次の「大きな節目」の合格条件
1. GitHub Actionsから新しいbyte-locked CIとP3～P6統合CI（51件）の**実行ログ**を取得し、失敗があれば再現・修正。Streamlitの実UIも別途検証。
2. 実際の公式未発走京都出馬表とオッズの取得経路、利用条件、事前凍結、レース後の公式結果・払戻の区別を**実データで実証**。無許可取得、実購入、Turso本番書込みはしない。
3. P1・P2の出典完全性とP3較正・P4公式オッズ・P5予算・P6公式採点を通過して初めて実用予測候補を評価。単に計算可能・LABテスト成功で完成とは認めない。
4. P7のEVO-07独立認定・ロールバック、EVO-08の反証発見まで合意を保持する。

## 保護と節目判定
**今回の大きな節目：GitHub保存版にバイト完全一致した研究用P6台帳を初めて独立実行して15/15 PASSし、別プロセス復元・アンカー削除検出まで実証。CI出力不具合を修正し、新しい同一性確認ゲートと持運び可能なオフライン検証パックを追加。**

P1～P8、ALG-01～13、EVO-01～08、スマートフォン/無料条件を維持。本番main/app.py、Turso、Secrets、実馬券購入台帳は変更しない。P1～P6の**本番受入は未達**。
