# Kyoto AI P1 dual-market offline intake integration milestone (2026-11-09)

## Scope, not a declaration of live P1 acceptance
This milestone ties an existing raw-byte/UTC intake bridge to a separate dual-market structural audit. It checks quinella and bracket pair sets, within-bracket pairs, runner withdrawal/withdrawal-stale-pair rejection, sales-state claims and UTC cutoff. No JRA site was requested, no prediction was enabled, and no real tickets were purchased.

## Exact components
- Existing immutable-entry checks: `diagnostics/jra_p1_offline_handoff.py`, `diagnostics/jra_p1_snapshot_gate.py`, `diagnostics/jra_p1_intake_bridge.py`.
- Added standalone dual market checks: `diagnostics/p1_dual_market_offline_audit.py`.
- New explicit entry point: `inspect_bundle_and_dual_snapshot(bundle, snapshot, observed_utc=...)`.
- Regression code: `tests/test_p1_dual_market_offline_audit.py` (13 new isolated tests), `tests/test_jra_p1_intake_bridge.py` (10 new end-to-end integration tests plus its earlier 16).
- Push-triggered CI: `.github/workflows/kyoto-p1-dual-market-offline.yml` runs all three suites (dual, quinella, bridge); the existing future-market workflow also runs when the bridge changes.

## Fail-closed behavior
1. Preserve the race/date, exact source SHA, captured UTC, prediction cutoff and bounded archived bytes prior to examining market claims.
2. Require a complete active-horse quinella pair set and complete possible bracket pair set, including a same-bracket pair only when two active horses occupy the bracket.
3. Block duplicate, unavailable and malformed pairs; block absent or non-open claimed market state; reject timestamps beyond the cutoff.
4. A scratch/withdrawal is never assumed authenticated. If legacy snapshot/market data still contains withdrawn horses, the strict path fails closed, rather than quietly deleting their historical prices.
5. The audited market values, sales status and withdrawal status are user-supplied; this implementation **does not parse or authenticate official odds or withdrawal announcements**.
6. The current evidence bundle holds racecard and one pre-race-odds original, not independently locked original bytes for both markets. Consequently `bracket_original_independently_verified=false` even when structural checks pass.
7. Every return explicitly forces `prediction_ready=false`, `actual_orders_authorized=false`, `network_requests=0`.

## Existing verified evidence retained, without relaunching prior downloads
- Resume evidence artifact: 13482994623 (API-confirmed non-expired at this session; SHA already recorded in immutable registry).
- Historic 84 original HTML profiles / 485 rows / 335 recomputed features, separately from 96 detailed profiles and 52 unqueried horses.
- Earlier dual-free 24 tests successful in Actions run 42569049451; this does NOT validate newly added tests.
- Stable production main SHA: `471b60e632d878b52b6dcb4aa1a622becba40882`.
- The previous dual-market code checkpoint: `8775fe51f285f3402a2b55c2f3fd032983153d90`.

## Current validation limits
The new GitHub commits and corresponding file/blob reads can be verified via GitHub; **new push Actions run/job/log evidence must still be fetched before writing CI_PASS**. The available GitHub fetch-commit-workflow-runs action only includes PR-triggered workflows; an empty result is not proof that push Actions did not run. No current local Python run was claimed as equivalent to GitHub Actions. If CI fails, inspect the actual job log and repair the root cause, not re-run historical JRA GETs.

## External access decision
JRA official general usage information was consulted at https://jra.jp/use/ . That page covers JRA web domains and usage notices, but did not establish an explicit general authorization for our automated current-odds bulk retrieval. No permission is inferred from mere page accessibility. The official JRA App terms at https://sp.jra.jp/app/terms.html apply to that service and cannot be treated as authorization for website automation. Do not silently migrate to paid JRA-VAN or bypass rate limits.

## Next larger acceptance milestone
Resolve legally permitted source/data rights and actual source capture (official racecard, both market originals, race-day scratched/withdrawn runners and sales windows), independently bind market prices and timestamps to original bytes, pass end-to-end negative cases and actual GitHub push CI, then forward-only frozen paper-trade validation. Until then P1 is NOT accepted, even if every synthetic structural test passes.
