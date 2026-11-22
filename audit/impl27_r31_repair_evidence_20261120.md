# Impl27 R31 focused correction: immutable evidence record

- Scope: R31 GitHub Actions upload retry false-negative conclusion only.
- Baseline: main `2c807afadb389f0441e74d7a25f2d8d6bfc0e353`.
- PR: #72; source-only isolated review branch.
- Targeted GitHub independent CI: run `44684808192`, SUCCESS; five focused tests passed; protected eight schedule/YAML gate passed.
- Frozen collector: 2026-11-21 `de2544c1e9f9951a265419461267146b4023c2ab`; unchanged.
- Protected production observer: all eight cron values unchanged; PC->SP dependency unchanged.
- Prior reuse gate run `44684808071` failed on missing PR metadata fields; run retry is pinned to the original event payload, so it cannot verify edited PR description. A *new pull_request synchronize event* is required.
- Root-cause repair: continue-on-error on primary PC and SP artifact-upload steps only, preserving `steps.*.outcome == failure` for retry; strict retry failure remains fatal.
- Outstanding: no full GitHub-outage alternate archive, no durable beyond-30-days route, no live fault injection. R31 remains OPEN.
- Review: CI green is not evidence of live JRA collection or of encrypted artifact restoration under a real outage.
