# Kyoto AI 2026-11-09 — P1 dual-market independent-three-originals integration v2

## Why this is a wider development milestone
Prior work checked quinella pair coverage and then bracket pairs as a standalone synthetic structure. This cycle joins that audit to the established archived-bytes intake and adds a **separate, reproducible SHA-bound original for racecard, quinella odds and bracket odds**. It preserves the original two-source research interface for backward compatibility. No original is fetched from JRA in this cycle.

## Implemented on the development branch
- `diagnostics/p1_dual_market_offline_audit.py`: active-runner quinella pairs; possible bracket pairs including same-bracket entries; official-claim sales state; withdrawal/unknown status fail-closed; pre-cutoff UTC check; no readiness escalation.
- `diagnostics/jra_p1_intake_bridge.py`: new `inspect_bundle_and_dual_snapshot` wraps existing SHA/time/identity checks with the dual-market audit. Legacy two-source snapshots remain research-only and explicitly have **no independent bracket original**.
- `diagnostics/jra_p1_future_evidence.py`: new third offline source kind `bracket_odds`; existing `racecard` and `pre_race_odds` retained.
- `diagnostics/p1_three_original_dual_intake.py`: new `inspect_three_original_dual_intake` validates a bounded offline ZIP's three distinct source-byte SHA values, race/date/cutoff/UTC, matching snapshot source bindings, currency of market originals (30-minute snapshot lag cap), and complete dual-market structure. This does **not** certify JRA authorization or source authenticity.
- `tests/test_p1_dual_market_offline_audit.py`: 13 new standalone cases; `tests/test_jra_p1_intake_bridge.py`: 10 new integrated dual cases (existing 16 retained); `tests/test_p1_three_original_dual_intake.py`: 14 third-original cases. All test code is synthetic; no real race-day price evidence claimed.
- `.github/workflows/kyoto-p1-dual-market-offline.yml` and `.github/workflows/kyoto-p1-three-original-dual.yml`: push-triggered Python 3.11 suites for both old and new entry points.

## Acceptance split
1. **Code committed and Github blobs checked** — can be certified by repository read-back.
2. **Push CI passed** — must be established with run ID, job conclusion, log and commit SHA, not assumed from the workflow file and not inferred from PR-only search.
3. **Three independent original files bound** — demonstrated ONLY in fixture data; neither actual JRA current-market HTML nor its copyright/use authorization has been checked.
4. **Official source authenticity and use-rights** — NOT MET. `official_origin_authenticated=false`; no automated JRA HTTP activity authorized by this cycle.
5. **True prerace odds + scratches + open sales evidence + calibrated model + immutable paper trade** — NOT MET. `prediction_ready=false`; P1 unaccepted.

## Traceability and preservation
- Development branch: `jra-html-diagnostic-20261105`.
- Stable production `main`: `471b60e632d878b52b6dcb4aa1a622becba40882` (verify again after edits).
- Source originals recovery Artifact: `13482994623`; historical 84 PC HTML originals / 485 past finishes / 335 matching features remain a separate, completed fact, not a present-day market feed.
- Former successful CI `42569049451` covers the earlier 24 synthetic two-source market checks only, not the current commits.
- Before accepting code, inspect actual push Actions logs and fix any failure; never infer success from a new YAML file.

## Legal/data right gate
Consult JRA general usage at https://jra.jp/use/ (scope includes JRA PC and SP sites). No explicit permission for unattended bulk collection of pre-race odds has been established. Independently assess the exact acquisition method and applicable terms; if still unresolved, accept only appropriately obtained offline source originals and do not add live scraping. Keep the free/smartphone architecture; no JRA-VAN paid migration or business Work/Codex crossover.

## Next P1 acceptance work
Obtain permitted **actual future-race** three original source captures with trustworthy UTC and explicit official issue/sales status; parse and cross-check racecard/quinella/bracket/withdrawals from each original (rather than from self-declared snapshot JSON), verify market freshness and complete coverage, then run strict forward-only paper trade and official payout settlement. Preserve each incident and CI receipt independently; no real purchase without explicit user approval.
