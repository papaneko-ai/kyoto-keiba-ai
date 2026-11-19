# Impl22 -> Nov21/22 live collector integration gate — 2026-11-19

## Proven / preserved
- Original live collector pinned by main scheduler: `a96a249250cb074c451e746228a6775169c025ed`.
- This candidate adds the smallest safe correction for actual Hrana v2 `{"type":"null"}` cells. No automatic replay of uncertain mutations.
- GitHub Actions offline source-level tests: Run 44450440163, 32/32 PASS. No production network requests.
- Real isolated Turso GitHub runners passed: 44443836669. Streamlit readback (run 44443836669) and independent hold refusal (run 44449491883) were confirmed by user screenshot.
- Production scheduler has eight existing cron slots; do not delete/reorder.

## Release blockers (must be resolved before 21 Nov pre-race source capture)
1. **Immutable SHA mismatch**: main weekend workflow still checks out `a96a249...`; new fix is NOT in that checkout. Its explicit day21 static guard enforces exactly that old SHA. Patching only the code on a branch does not deploy it.
2. **Feature not activated**: `diagnostics.kyoto_weekend_remote_claim_runtime.active_claims_for_weekend` requires `KYOTO_SHARED_CLAIM_ACTIVATE=YES`, `KYOTO_SHARED_CLAIM_TURSO_URL`, `KYOTO_SHARED_CLAIM_TURSO_TOKEN`, scheduled event and known cron. Main scheduler does not currently populate this activation/URL/token path.
3. **Safety policy**: the runtime only accepts the isolated test database hostname. The tested lab token/DB must not silently become the durable production coordination authority. Decide and verify the intended production/shared-coordination database separately, without touching wager/virtual-investment tables or production Secrets.
4. **Availability**: enabling the strict coordinator on a failed/unreachable credential causes G06 market HTTP to stop for affected races. Before enabling, prove failover and recovery behavior and preserve the no-silent-duplicate constraint; do not reduce live source success rate to claim a feature is activated.
5. **Exact preflight gate**: review release source SHA, the day21 hardcoded equality check, day22 reviewed-commit/preflight machinery, static workflow tests, both PC/SP paths, source sealing, and 8-slot timings together. Promote only after release-gate CI is green.

## Safest deployment order
- Merge only the candidate into a *versioned release source* after code review, keep SHA immutable.
- Implement and independently test the shared claim's **production-safe** runtime policy and credentials (not lab-only assumptions); prove 2-process/2-runner and source retrieval failure recovery.
- Build a reviewed weekend scheduler change that swaps the pinned SHA and matching pre-HTTP guards together. Verify schedule is still exactly eight slots, encryption, URL allowlists and no-replay controls remain unchanged.
- Confirm on GitHub that main runs the approved SHA, and store release receipt plus backup. Do not assert deployed until those checks succeed.
- If the complete live gate cannot be proven by the Nov21 schedule, retain the current source-observation path to avoid losing the unique live pre-race data opportunity; explicitly mark shared coordinator as **not live**, rather than claiming integration.
