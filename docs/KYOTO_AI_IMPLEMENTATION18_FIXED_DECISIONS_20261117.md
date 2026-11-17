# Kyoto AI Implementation 18 — Permanent decisions (2026-11-17)

## User-approved fixed direction

1. The legacy `main/app.py` UI, fabricated MD5 predictions, fixed odds and old result lookup are **not** design inputs for the new Kyoto AI. Completely replace the old code; preserve its Git history for recovery only.
2. Retain the agreed P1–P8, ALG-01–ALG-13 and EVO-01–EVO-08 engineering work. Reuse verified new-system modules, not legacy UI logic.
3. Priority: unattended Nov 21 and Nov 22 authentic prerace capture, with official PC/SP acquisition, race ID, UTC, SHA256, encrypted evidence, and day-one failure diagnosis feeding verified day-two recovery.
4. Main launch route: **external timer → GitHub workflow_dispatch**. Backup launch route: existing **GitHub schedule**. No manually triggered operation as a normal dependency. Do not add a Cloudflare Workers/R2 data-collection platform.
5. The user explicitly approved experiments on `main`. Do not disclose credentials or change Turso or Secrets gratuitously. Preserve reliable rollback.
6. External timer setup and end-to-end scheduled dispatch are **not yet proven**; a GitHub workflow accepting dispatch is not evidence that the external service has actually fired.
7. An initial minimal new `main/app.py` only displays truthful read-only/unavailable states while real data-to-UI integration is incomplete. It is not a declaration of completed production predictions.

## Tracked changes and provenance

- Old `app.py` blob before replacement: `4db979d3c17411192d11e809b5afb66011bb2179`. Retrieve from its preceding Git revision; do not use as a design template.
- New independent `main/app.py`: commit `2418240d7a3561a2ae1687a83e30343755bce0d7`.
- Previously missing offline preflight workflow restored on main: commit `5172fb1f849aae257308ea2cdd95f2fa98d1c2ec`. Actual preflight run and collector SHA qualification must still be verified independently.
- New UI research prototype on diagnostic branch: `diagnostics/kyoto_new_mobile_paper_ui.py`. Its dependencies were absent on `main` at the 2026-11-17 review; do not blindly import it.
- External dispatch contract draft: branch `kyoto-external-launch-20261117`. This is not a successful external timer integration.
- Local Python syntax and legacy-predictor exclusion checks passed for entrypoint candidate; runtime Streamlit AppTest unavailable in local environment. Live public Streamlit deployment has not been confirmed.

## Invariants

- Do not display invented odds/runners, prediction confidence, results, or fictional profit.
- Do not turn a mock test, documentation commit, app replacement, or push event into evidence of actual unattended scheduled launch.
- Fixed management indicators remain: research 32/32; graduation 12/12; pre-data readiness 16/16; independent live connection 0/6; independent practical capability 0/100.
- First finish independently tested unattended capture and day-21/day-22 recovery procedure. UI integration follows, without preserving old app compatibility.


## 2026-11-17 additional verified GitHub Actions milestone

Independent evidence from real GitHub executions (all were `push`, **not** external timer or `schedule` events):

- Main entrypoint offline integrity: Run `43997794522`, completed success; artifact `14291280314`, digest `sha256:0ebb34bc358d137d4d3bdf28755d9b05cf91972154b59b3ff59149df2ece07fe`.
- External GitHub dispatch fake-server contract: Run `43998092685`, completed success; artifact `14290188600`, digest `sha256:2c3bb1a418418f6f0bf4b69e08c65baf98342f3bd62e5384ee97aab84e13a860`.
- Reused Nov21-22 offline preflight: Run `43809830663`, successful on candidate `6f4de9c8ad0f65949e2bd4584e7b652cb7459073`, artifact `14199284639`, digest `sha256:7c92daa886bbee563a5b81a9c817255e769a9e1cd2f50f669d380c5c4f024810`.
- New independent GitHub release-evidence checker: Run `43999091621`, completed success and printed `EXISTING_PREFLIGHT_EVIDENCE_MATCHED=PASS`; artifact `14289924834`, digest `sha256:ebe50bb8626b236e610496f0b6dc53d3823b15bf4059d8dfc915cd2e83a853ea`. Workflow source: `.github/workflows/kyoto-implementation18-preflight-evidence.yml`, commit `88825d1d055b56d6b76a3077901cca4f01de5d77`.
- The difference from preflight candidate `6f4de9c8...` to diagnostic HEAD `c97c6165...` is only `.github/workflows/kyoto-implementation16-source-recovery.yml` and the P1 roadmap markdown. Do **not** claim that c97c itself passed preflight: its SHA differs.
- The earlier migration ZIP's tracked source does not match the latest diagnostic branch in at least `diagnostics/kyoto_weekend_sp_discovery.py`: local historical blob `110842ed...`, current GitHub blob `b320ced1...`. A 154-test local suite on that historical extracted copy returned 1 failure and 2 errors; these cannot be ascribed to current GitHub source and must not overwrite real GitHub CI evidence.

**Important bounds:** No `KYOTO_NOV22_VERIFIED_COLLECTOR_SHA` variable was changed, no live collector was promoted, no external scheduler account was configured, and no external timer-to-GitHub event was demonstrated. Do not claim unattended production operation until provider setup plus a real timed workflow_dispatch run and artifact are verified. No JRA requests were made in these tests. Existing fixed certification metrics remain unchanged.
