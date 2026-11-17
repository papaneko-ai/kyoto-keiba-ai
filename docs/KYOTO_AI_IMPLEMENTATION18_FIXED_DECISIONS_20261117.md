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


## 2026-11-17 additional substantive milestone: main-hosted immutable source test

- `.github/workflows/kyoto-implementation18-pinned-collector-preflight.yml` was added to `main`, and its job checks out the **candidate SHA**, not the default-branch HEAD. It executes the existing no-JRA regressions and records a proof artifact with the exact candidate SHA, parent workflow SHA, test logs and their hashes.
- Candidate `6f4de9c8ad0f65949e2bd4584e7b652cb7459073`: GitHub Run **43999459665** SUCCESS, artifact **14291601541**, SHA256 digest `c10a321e6c6836159a442d20870e0c875c75602293bbded6cb1996a2e17dd388`.
- **Actual production-pinned collector** `17eae0ce3e1ffa04b75398555849740af6a22f0a`: GitHub Run **43999571979** SUCCESS, artifact **14291985786**, digest `5dd29f582e3b1dc6b11dc899cb497e42cc923ef252e8035f67c803221c4aa58c`. Runner reported `PINNED_COLLECTOR_PREFLIGHT_PASS=17eae0ce3e1ffa04b75398555849740af6a22f0a`.
- `.github/workflows/kyoto-implementation18-external-timer-probe.yml` on main is a deliberately **no-JRA, no-production-dispatch** endpoint. Main GitHub push Run **43999631475** succeeded; evidence artifact **14291207867**, digest `e8a0afb867ea1a8a430a36266eec87f656152788fc6a6c2f2d470ab458daea08`. Its `PROBE_EVENT=push` and `EXTERNAL_PROVIDER_PROVEN=False` are not evidence of an external timer. An external service must invoke its `workflow_dispatch` and the service execution log must independently establish origin/timing.
- **External provider setup is still missing**. No cron-job.org account/API key or GitHub token was made available to the execution tools. Do not claim creation of an external cron job, external triggering, startup latency improvement, or genuine unattended production capture. The old `schedule` remains the currently proven automated event path.
- **Deployment/promote limit**: these checks do not set `KYOTO_NOV22_VERIFIED_COLLECTOR_SHA` and do not change Turso/Secrets. The 21-to-22 patch promotion must still prove exact tested source code and safe rollback. The check above shows offline run reproducibility, not real market capture.

## Minimal external timer registration contract (not registered)

- For a no-JRA endpoint test: `POST https://api.github.com/repos/papaneko-ai/kyoto-keiba-ai/actions/workflows/kyoto-implementation18-external-timer-probe.yml/dispatches` with `{"ref":"main","inputs":{"sent_unix":"%cjo:unixtime%"}}`. This is safe to call before Nov 21 because it never fetches JRA. It records timestamps in an artifact. Authentication: an account-owned fine-grained GitHub token restricted to this repository with `Actions:write`, sent only as an HTTPS Authorization bearer header. Do **not** store it in source or documentation.
- The production endpoint already exists at `.../actions/workflows/kyoto-20261121-22-two-source-production-observer.yml/dispatches` with `race_day` and confirmation `NOV21-22-OBSERVE-READ-ONLY`. It must not be activated before service-level timing and token access are demonstrated, and its date and UTC guard deliberately prevents pre-event JRA HTTP.
- cron-job.org has configurable HTTPS POST headers/body, a REST API, and execution history. Confirm a successful provider execution, `workflow_dispatch` GitHub Run, measured startup time and artifact together; a 204 HTTP response by itself is not complete evidence.


## 2026-11-17 next milestone: contract-tested, disabled external provider specifications

- Added `tests/test_kyoto_external_launch_prod_contract.py` and `.github/workflows/kyoto-implementation18-external-timer-contract-gate.yml`. Checks the current main production workflow, exact two-day dispatch JSON, both PC/SP day guards, six original GitHub backup cron slots, no-JRA probe contract, and intentional invalid-input mutations. It uses **zero JRA requests**. GitHub Run `44000116211` SUCCESS with artifact (first five contract tests); the revised job-template test must pass separately.
- Added disabled JSON specs at `docs/diagnostics/KYOTO_AI_20261117_EXTERNAL_TIMER_DISABLED_JOB_SPECS.json`; expected cron-job.org `PUT /jobs` requests are one safe external probe (Nov18, 09:15 JST) and two scheduled race-day jobs (Nov21 and Nov22, 09:15/10:15 JST). Every template is `enabled=false`, expires at `2026-11-23T00:00:00+09:00`, leaves the GitHub token as a deliberately invalid placeholder, has no real credentials, and never submits anything by itself. Two-day requests use `workflow_dispatch` and the exact existing production `confirmation` value; **no legacy `app.py` dependencies**.
- Provider documentation: https://docs.cron-job.org/rest-api.html confirms `PUT /jobs`, `schedule.timezone`, `schedule.expiresAt`, `extendedData.headers`, `extendedData.body`, `requestMethod=1` for POST; https://docs.cron-job.org/creating-cron-jobs.html confirms `%cjo:unixtime%` expansion in the probe body.
- **Still not connected**: actual external provider account and GitHub fine-grained token restricted to `papaneko-ai/kyoto-keiba-ai` with Actions:write. Neither was available through the connected tools. Do not create any live cron job, use a fake token, or claim external dispatch proven. A token entrusted to a scheduling provider is a credential; configure it only in the provider's secured interface, never in repository/ZIP/chat.
- Before enabling live jobs, require the no-JRA probe's actual `workflow_dispatch` GitHub run, artifact receipt, and independent cron-job.org execution history to agree. API acceptance alone, a push-triggered test, or a stored schedule template is **not** proof. After Nov22, revoke external dispatch token and remove/disable provider entries to avoid stale credential exposure.
- The first external live attempt is intended at 09:15 JST and the second at 10:15 JST; existing GitHub backup jobs begin 10:05 JST. Early availability of JRA market data is not guaranteed, and GitHub job startup still may queue. Preserve no-postrace and content-quality gates.


## 2026-11-17 decisive API-level milestone: real workflow_dispatch, no JRA

- Added one-shot workflow `.github/workflows/kyoto-implementation18-dispatch-real-api-rehearsal.yml` on `main`, commit `ad16085e0f5c841c7a55eb840a2ea766447b4145`. Triggered by this file's `push` event only. Its GitHub-provided ephemeral `github.token` had `actions:write` and posted an authenticated **real** HTTP POST to the **safe no-JRA probe**, not the production acquisition workflow. No user token was stored.
- Requester Run **44000813185**, event `push`, result **success**, log explicitly states `GITHUB_API_DISPATCH_HTTP_STATUS=204`, artifact **14291972311**, digest `sha256:79c67e703c9ecbeca8a181d2c52ea99800e254c224ecd25f22cb8e300c176b70`.
- Independently triggered receiver Run **44000823360**, event **workflow_dispatch**, result **success**, log explicitly states `PROBE_EVENT=workflow_dispatch`, `JRA_HTTP_REQUESTS=0`, `EXTERNAL_PROVIDER_PROVEN=False`. Artifact **14291434383**, digest `sha256:71bd0f4f66c4aee4858e45a3d03a8b54fdd9ec74e408355a35b56935d01b40cc`.
- Github observed receiver run created at `2026-11-17T02:08:55Z`; received runner log `PROBE_EVENT` at `02:09:01Z`. This is a bounded internal API-to-job demonstration in seconds, **not** an external cron latency benchmark, and timestamps do not independently prove exact HTTP POST-to-job latency.
- This confirms a real GitHub API acceptance and dispatch-triggered GitHub execution including receipts, improving the prior only-mock state. **Still blocked**: independent cron-job.org provider account, provider-side secure GitHub token setup, time-triggered provider execution history, and corresponding external-origin run. Do not assert that external scheduling or Nov21/22 live JRA capture is proven.
- The existing production `main` workflow and old six `schedule` backup slots remain unchanged, no public `app.py` rollback, no credentials, no Turso mutation.


## 2026-11-17 major milestone: repaired unattended Nov21 -> Nov22 evidence handoff

- Root cause identified in `.github/workflows/kyoto-20261121-22-result-handoff.yml`: scheduled discovery set shell variable `OBSERVED_RUN` within one step, but later artifact-download/decryption/assessment steps read the original **job-level empty env value**. This could make the scheduled Nov21 observation-to-Nov22 repair chain unable to load valid artifacts, even if a real capture succeeded. This is not a JRA source or collector bug.
- Minimal fix: after validating the selected numeric run ID, export `OBSERVED_RUN=$OBSERVED_RUN` into `$GITHUB_ENV` and save `day_result_handoff/observed_run_id.txt`. Use `echo` to avoid escaped-format ambiguities. Original day-21 acquisition workflow, backup schedules, encrypted originals, job-level step separation, and no-unapproved-semantic-change conventions remain intact.
- New negative regression test `tests/test_kyoto_nov21_handoff_cross_step.py` and real GitHub cross-step mock-only workflow `.github/workflows/kyoto-implementation18-day21-handoff-gate.yml`. It runs four tests (actual configuration, missing persistence, missing receipt, missing downstream binding), then simulates selecting a numeric run ID in one GitHub job step and consuming it in another. All tests are **offline and zero JRA HTTP**.
- Initial run **44001716978** FAILED because test string escaping was too strict, not because the collector failed. Corrected, Run **44001794878** SUCCESS. Final newline-safe revision Run **44001865077** SUCCESS; artifact **14292038796**, SHA256 digest `e799412eee58078756ec7c469f6ccb8a8672b84e7305f56d2d5a691f677ba286`. Job log: `Ran 4 tests` and `DAY21_HANDOFF_CROSS_STEP_PASS`. The test framework also proved a missing cross-step persistence line is detected.
- **Bounded achievement**: This is concrete repair of the automated Nov21→22 diagnostic handoff and real GitHub runner env-propagation verification. There is no claim that Nov21/22 official JRA data has been collected, that a timed external provider has run, or that self-modifying fixes are automatically authorized. The source of the user-approved day22 correction still requires factual Nov21 evidence, candidate test, review, and exact SHA binding.


## 2026-11-17 next milestone: real Nov21→Nov22 diagnostic handoff with NO_DAY_RUN

- Audited main `.github/workflows/kyoto-20261121-22-result-handoff.yml` and pinned source `e2a48f8b58ae13c210eead22533ee107004a45cd`. The source module `diagnostics.kyoto_weekend_day21_artifact_triage` imports `cryptography` through `diagnostics.kyoto_nov15_encrypted_evidence`, but the main handoff workflow had no dependency installation. Added `python -m pip install 'cryptography>=43,<47'` before metadata and decryption work; commit `7c9ef63cce15bb370a3fc5ac5b806b94b26118b6`.
- Added temporary one-shot proof workflow `.github/workflows/kyoto-implementation18-day21-actual-handoff-rehearsal.yml` with `actions:write` only for posting a real authenticated `workflow_dispatch` to the actual diagnostic handoff, with `observed_run_id=0`. This means **synthetic missing observation**: it is not a live JRA run, contains no user credential and triggers no JRA HTTP.
- Real GitHub request sender Run **44002252973**, completed with proof artifact **14292268732**, digest `sha256:7e8113d487d67c6df0c75e1ef3b00919e66c5331b015edba461846feb7f0c8ad`.
- Actual receiving production diagnostic workflow Run **44002262620**, event `workflow_dispatch`, **SUCCESS**; runner logged `DAY21_ACTUAL_SOURCE_TRIAGE=NO_DAY_RUN,NO_DAY_RUN` and `FIRST_DAY_SECOND_DAY_HANDOFF=NEEDS_HUMAN_TRIAGE_OR_PREVALIDATED_NEXT_DAY_FALLBACK`. Proof artifact **14291884651**, digest `sha256:a7935c9eeb43806ee254ec985291127f0f7e453fd23d130c25bb63710b65deb5`. This proves real API dispatch, pinned source checkout, encryption-reader import, synthetic zero-run diagnosis, next-day strategy summary, and evidence artifact end-to-end on GitHub runners.
- **Do not overstate**: This is a no-source branch simulation; it does not prove decrypting and authenticating actual Nov21 original artifacts, success of official PC/SP links, nor automatically editing a new source revision. The existing daytime production capture schedule, secrets and Turso were not changed.
- Future hazard: the scheduled handoff currently selects just the latest completed observation run when several runs exist. That selection may not reflect the most useful verified originals. Address by evidence-based multi-run aggregation rather than treating the most recent successful Actions conclusion as authenticated acquisition.
