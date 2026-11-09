# Kyoto AI continuity incident INC-20261109-REUSE-GATE — root cause and finite delivery definition

## Incident and evidence

**Symptom**: Implementation 06 already corrected lost-artifact discovery and introduced a source-integrity resume gate; Implementation 07 again proposed new acquisition work despite existing PC/SP/JRA acquisition, parsing, comparison, and research components. A second round of isolated synthetic market gates was pursued without first mapping existing production-adjacent code.

**Immediate mechanism**: `.github/workflows/kyoto-ai-resume-evidence-gate.yml` was restricted by `paths:`, so an unrelated code push could skip it. `diagnostics/kyoto_resume_gate.py` checked old frozen evidence, not the reuse/duplicate status of existing functional code.

**Root cause**: The pre-existing evidence-integrity gate and the development decision/commit route were not coupled. Correct original-source checks did not guarantee an inventory of reusable modules or prevent an already existing function being described as absent.

**Invariant**: No development change is counted as accepted until the authoritative historical artifact is recoverable, existing capability paths and known successful evidence are enumerated, the proposed change is identified as REUSE/REPAIR/INTEGRATE or justified genuinely NEW, and current commit CI is verified with actual push workflow jobs.

**Same-root scope**: PC racecard GET, SP runner/parity, PC profile, historic final odds vs live odds, current odds menus, 3-original market intake, P3-P6 research and paper-trade ledger. Future changes to all P1-P8 capabilities must register reuse/remaining scope before declaring a newly designed subsystem.

## Repair implemented

- `docs/diagnostics/kyoto_feature_reuse_inventory_v1.json`: file-path-grounded existing capability inventory (existing code, evidence, precisely remaining scope); do not reclassify PC/SP and P6 code as nonexistent.
- `docs/diagnostics/kyoto_change_intent_v1.json`: current reuse/repair/integrate decision and justification.
- `diagnostics/kyoto_development_preflight.py`: reject missing required capabilities, code/evidence paths, duplicate-new intent for existing code, missing rationale.
- `tests/test_kyoto_development_preflight.py`: positive, duplicate-new negative, removed code negative, dropped feature negative, missing rationale negative, determinism and nonmutation tests.
- `.github/workflows/kyoto-ai-always-run-continuity.yml`: **no paths filter**, fires on every dev-branch push; executes preflight and regression tests, obtains latest official recovery Artifact metadata with GitHub API, and runs existing `diagnostics.kyoto_resume_gate` again.

## Independent Github evidence

- Prior dual market standalone run **42571331090: success**.
- Prior dual-market bridge CI run **42571309013: success** (specific commit only).
- Three-original market regression run **42571593815: success**.
- New always-run continuity gate run **42574677833: success** at commit `ccdadcbe9a43b7a576b41e468a8bfeb053ed552f`. Later commits must each be rechecked.
- Local isolated candidate preflight: 7 tests pass; destructive and three repeated deterministic checks included.

## What the fix does not prove

GitHub integration cannot read the repository's branch protection endpoint (403), and repository ruleset listing was empty. Therefore an Actions success **does not block a direct push** on its own. Administrators must enable a required status check/branch protection for genuine server-side enforcement. No claim that source reading is human/AI-understanding-proof. The intent inventory is an explicit declaration and can be incomplete for future new feature IDs; expand the inventory when work scopes expand. Legacy original registry v1 remains unmodified. New Actions success is not proof of live JRA odds capture.

## Completion-oriented project milestones (P1-P8 unchanged)

| Gate | Real-world completion criterion | Not sufficient |
|---|---|---|
| C0 Continuity | Actual HEAD, main, independent backup, source artifact, reuse inventory and same-commit CI checked before work | Existing documentation alone |
| C1 PC/SP retrieval | Existing PC and SP modules both exercised on authentic racecard/profile/market data; fallback and sources/UTC logged, permitted method verified | HTML from historic races alone |
| C2 P1 input | 12-race racecard, current quinella/bracket odds, scratches, sale status and time frozen from genuine accepted input, including missing-data skip | Synthetic 153+36 combinations |
| C3 P2–P5 forecasts | Chronologically disjoint training/evaluation and calibrated pair probabilities, price/EV, budget allocation and no-bet controls measured against baselines | Research math fixtures |
| C4 P6 paper trading | Preregistered *before* post time, immutable replayable predictions, official result/payout/returns/refunds, nonduplicated scorekeeping | Post-event reconstructed paper wagers |
| C5 P7 evolution | EVO-01..08, independent time-out-of-sample certification/rollback, comparable baseline, tracked failures | Unvalidated self-updating |
| C6 P8 usability | New lightweight mobile Streamlit app built independently of deprecated app.py, user-facing live-to-result flow, read-only diagnostics and backup recovery | Mock UI only |

A gate is not complete without reproducible evidence on one exact commit. Avoid endless micro-milestones: continue to the next substantive gate when subordinate components already exist. PC/SP automatic acquisition remains the first functional bottleneck, and legal data-rights discovery must progress in parallel without derailing offline and existing-component integration.

## Protected boundaries

Do not write `main/app.py`, Turso, secrets, or actual purchase records without explicit user consent. No unauthorized scraping or automatic real wagers. Preserve official source artifacts and former CI receipts. Prefer repair of known source modules over new parallel wrappers.

## Outstanding genuine operational boundary

GitHub rulesets are empty and branch-protection API is not accessible to this integration. Without administrative protection, an always-run workflow is an independently checked alarm, not an unbypassable lock. User-facing reports must state this limitation until settings are actually verified.
