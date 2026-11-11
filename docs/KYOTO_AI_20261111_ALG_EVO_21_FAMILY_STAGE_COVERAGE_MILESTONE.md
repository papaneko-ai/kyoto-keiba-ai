# 京都競馬AI・研究合意21機能群の工程組込台帳（2026-11-11）

**判定範囲**：ALG-01〜13・EVO-01〜08の21機能群。A=実証済み、B=明確な実装工程と受入条件あり、C=未反映。

**今回の節目：この21機能群についてB=21、A=0、C=0と認定。** A=0はコードがない意味ではなく、この台帳では既存研究コードの存在を実用完成扱いしないための保守的な計上。すべての657原文行・過去チャット固有の合意までA/B=100%と認定したものではない。

既存コードは新規に作り直さず保護する。以下の「コード」は参考実装・保管先であり、全受入条件を満たした証明ではない。P段階では実原本・時点・テスト・CI run/job/SHA・失敗注入・再現性を独立検査する。

| 要件 | 担当工程 | 今後の具体的受入条件 | 既存コードの主な所在 |
|---|---|---|---|
| ALG-01 | P1 | 時点固定の馬・騎手・調教・馬場等の取得。原本SHA/UTC/欠損と発走後漏洩の拒否 | `diagnostics/jra_multi_capture_20261106.py` |
| ALG-02 | P2 | 勝馬・2着・敗退群の差と相互作用。未使用時系列で特徴採否 | `diagnostics/p2_three_way_discovery.py` |
| ALG-03 | P1/P2 | 京都・芝ダ障害・距離・騎手・展開を区別し、欠損と母数も検証 | `diagnostics/p2_historical_feature_matrix.py` |
| ALG-04 | P2/P3 | 市場基準/Harville/PL/Bolton–Chapman/Benter/ML混合の同時点・未使用時系列比較。Brier/対数損失/較正 | `diagnostics/p3_same_cutoff_market_model_bridge.py` |
| ALG-05 | P3 | 馬連順序付き確率合算、枠連同枠、取消、発売停止の処理と正規化 | `diagnostics/rg02_dual_market_integrated_lab.py` |
| ALG-06 | P1/P4 | 実発走前馬連・枠連オッズによる期待値、控除率、鮮度、変動、市場歪み | `diagnostics/p4_source_bound_model_ev_research.py` |
| ALG-07 | P3/P7 | 確率較正・Brier・対数損失・券種/人気帯/期間母数の独立評価 | `diagnostics/p3_research_calibration.py` |
| ALG-08 | P5 | 日次予算上限使い切り不要/原則2〜3R最大4R/原則2点最大3点/100円/見送りと手動調整 | `diagnostics/p5_bounded_risk_capital_lab.py` |
| ALG-09 | P6 | 発走前のモデル/確率/買い目/オッズ/原本SHA/UTCの変更困難な凍結。実購入分離 | `diagnostics/p6_source_bound_ranked_freeze_lab.py` |
| ALG-10 | P6 | 公式速報/確定/払戻/返還/訂正の正確な採点・二重計上防止・最大損失集計 | `diagnostics/p6_final_html_settlement_lab.py` |
| ALG-11 | P7 | 基準・旧新モデルの未使用時系列比較、不採用/改善採用/劣化時復帰 | `diagnostics/p7_guarded_research_rollback.py` |
| ALG-12 | P1/P8 | 公式PC/SP比較・双方向切替・安全な取得・SHA/UTC・合法/無料運用 | `diagnostics/p1_authorized_pc_sp_fallback.py` |
| ALG-13 | P8 | 新スマホUIで予算/券種/順位/価格鮮度/仮想成績を表示。旧公開アプリは設計流用禁止 | `diagnostics/p8_mobile_readonly_planner_app.py` |
| EVO-01 | P1/P2/P4 | 必須全頭情報を欠落させず追加特徴の情報価値と収集費を比較 | `diagnostics/p1_authorized_pc_sp_fallback.py` |
| EVO-02 | P2/P3/P7 | 条件別弱点と相互作用を検出し反証可能な実験を優先 | `diagnostics/p7_evo_candidate_falsification.py` |
| EVO-03 | P3/P6/P7 | 現行・単純基準・候補の同条件・同時点の影のAI選手権 | `diagnostics/p3_same_cutoff_market_model_bridge.py` |
| EVO-04 | P4/P5/P6/P7 | 結果前に凍結した買い目/配分/見送り戦略の反実仮想比較 | `diagnostics/p5_bounded_risk_capital_lab.py` |
| EVO-05 | P3/P5/P7/P8 | 確率較正・欠落・鮮度・ドリフト監視、不確実時の見送り・現行維持 | `diagnostics/p7_guarded_research_rollback.py` |
| EVO-06 | P2/P3/P6/P7/P8 | 弱点→候補→独立検証→採否→監視を結ぶ閉ループ。任意自己改変は禁止 | `diagnostics/rg04_integrated_evolution_cycle_lab.py` |
| EVO-07 | P6/P7/P8 | 改善候補生成と独立の進化認定、母数/多重比較/継続評価、証拠不足では不採用 | `diagnostics/p7_independent_research_certification.py` |
| EVO-08 | P2/P6/P7/P8 | 意外性・逆例に基づく仮説と反証、未使用時系列検証 | `diagnostics/p7_evo_candidate_falsification.py` |

## 全合意事項の精査は別途継続
14正式文書657行は出典とSHA256で保存。直接機能IDや工程が明記されている行も構文候補の段階であり、横断的な禁止事項や履歴・保守事項を含む **372行は意味的照合が必要**。1行に複数独立要件が含まれるため、657行=657機能と見なさない。すべての原子要件をA又はBとしC=0を確認するまでは「全合意事項に漏れなし」と宣言しない。

## その他の固定条件
- 32/32=研究100%、12/12=卒業100%、実開催0/6、実用能力独立検証下限0/100を区別。
- P1→P8を順守。ALG-04の実比較はP2/P3、EVO連結実証はP6/P7、UIはP8。98%は歴史的途中記録として改ざんせず、復元時には最新の32/32を使用する。
- 現行の本番main/app.py、Turso、Secrets、公開アプリ、実馬券記録には無断変更しない。旧公開アプリを新設計の参考にしない。
- Gitの全履歴、クラウド設定と隔離復元は現在のソースZIPだけでは認定しない。

参考：`docs/KYOTO_AI_ALGORITHM_REQUIREMENTS_REGISTER_v1_20261106.md`、`docs/KYOTO_AI_ALGORITHM_AND_EXECUTION_ROADMAP_20261106.md`、`docs/KYOTO_AI_20261111_THREE_ISSUES_STAGED_RESOLUTION_GATES.md`。独立証拠型の最終監査（RELEASED）は未実施である。
