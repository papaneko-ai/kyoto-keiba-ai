# Impl30 integration receipt — 2026-11-24

Scope: isolated software development and offline evidence. No production activation or live JRA GET, no main/Secrets/Turso changes.

## Exact evidence

- Historical main parent: 5d6c369c33b7e2d8e731e2ab56ba110235bb48b0.
- Original migration source: 3cbeb3280362dab5cbe01525b5f10e3e21c7a6a0 (recovery branch retained).
- Collector candidate: 4886e62bebc8b954e970e7d3fe34ee9e8564dae7; draft PR #93.
- Exact collector preflight run 45327578098: 165 root + 119 integration + 37 legacy + 18 risk tests = 339 pass, no JRA HTTP approval. Artifact 14890855692, ZIP SHA256 4da8092fd87293f9c8e009786ef00f3649c3a69f63ecfe3fc1a99f318a1bae0f.
- Separate historical SP regressions: 45327578063, 45327577993, 45327578011 success.
- Production candidate draft PR #94, pre-receipt HEAD a9e68f9cbbe7fb3d0219618eb0e16e1d6f26970f. Actual deployment YAML contract run 45327725434 success; protected Nov21 schedule contract 45327725404 success. Reuse metadata check 45327725399 initially failed because the PR body omitted mandatory fields; fields were added without changing policy.
- 8 slots match existing retry guard and Turso map. Two scheduled evidence-only all-run handoffs at 21:00 JST. Same selected immutable collector in PC/SP; Sunday override requires exact same-repository successful preflight, otherwise baseline. Baseline is offline-tested, not live-certified.

## Actual changes and boundaries

- Market originals preserved on parser rejection; malformed numeric cells rejected, cancellation/unavailable classified separately, bracket parser unified; full cancellation eligibility from independently verified official roster is not complete.
- SP historical R1 test uses a pinned historical clock, saved receipt JSON newline fixed, failed-race state explicit. Next-week real navigation remains unverified.
- Adaptive profile deadline uses verified G03 start UTC and existing G06 cutoff; never extends previous cap. No new cutoff or traffic permission.
- C10/C11/C12 next-week dates, authenticated evidence recomputation, exact run/artifact identities and all-run inventory are integrated. No claim that summary success equals full live source capture.
- Existing FMEA strict byte lock retained; 29 registered modules and 103 functions matched; changed functions reopened. 25 risk records remain open (13 high severity), 21 reachable dependencies, 94 top-level functions and 10 class methods still independently unreviewed. No completeness claim.
- Actual next-week start, complete source coverage, official final results/payouts, autonomous repair qualification and final bug audit remain unverified. Fixed five completion gates stay 0/5. No default-branch merge authorized.

## Recovery

Continue from the above immutable collector SHA and isolated integration branch. Do not repeat passed regressions unless changed source requires it. Preserve the existing original migration and prior GitHub evidence. Do not deploy or use the candidate for predictions solely because CI is green.
