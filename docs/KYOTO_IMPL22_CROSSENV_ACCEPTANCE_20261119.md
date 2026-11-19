# Kyoto AI Impl22 — Isolated Turso cross-environment acceptance (2026-11-19 JST)

## Evidence
- GitHub Actions: run 44449491883, workflow `Kyoto isolated Streamlit cross-environment active lease (manual only)`, conclusion SUCCESS. Main SHA at run: `34844f1fc91ca91e51b95e0bbeb992a41c5bcf04`.
- GitHub job evidence: `LAB_STREAMLIT_GITHUB_LEASE_READY=TRUE`, `LAB_GITHUB_RUN_ID=44449491883`, `LAB_LEASE_SECONDS=600`, `PRODUCTION_TABLE_MUTATED=FALSE`.
- User-supplied Streamlit Cloud screenshot in current conversation (2026-11-19 about 12:11 JST), diagnostic app `kyoto-ai-impl22-turso-lab.streamlit.app`. The app submitted run ID `44449491883` and displayed `status=REMOTE_LEASE_RESPECTED`, `must_fetch=false`, `owner_unchanged=true`, `generation_unchanged=true`.
- Prior separate cross-runner real Turso result: GitHub Actions run `44443836669` SUCCESS; prior Streamlit readback `REMOTE_GITHUB_RECEIPT_OBSERVED`, `DONE`, generation 1, in user screenshot.
- Isolated offline regression (21 tests): run `44447538326` SUCCESS.

## Verdict
**PASS — fixed pre-acquisition readiness criterion 10/10 (100%).** The previously unverified condition of cross-environment lease ownership and generation stability has now been verified on the isolated test database. This does **not** assert any live JRA pre-race data acquisition, actual race results/odds, prediction accuracy, or production Streamlit/Turso deployment.

## Safeguards and scope
- No production Turso tables or Secrets modified by this validation.
- Production `main` and its 8 pre-existing scheduled slots are preserved.
- Lab lease lasts 600 seconds; historical run IDs must not be treated as live active leases.
- The Streamlit diagnostic app may remain separate, and lab token should be rotated/revoked when no longer needed.
- Resume canonical practical-evidence tracking: live-event connection 0/6 and independently verified practical capability lower bound 0/100 until supported by separate evidence.
