# Kyoto AI Impl22: Streamlit cross-environment proof boundary (2026-11-19)

## Established evidence
- GitHub Actions run 44443836669: real isolated Turso, two independent GitHub runners, singleton claim, persisted completion and reuse PASS.
- Production acquisition schedule in main remains eight existing slots.
- This branch adds a **separate** Streamlit entrypoint, not a change to production app.py.
- Offline GH Actions run 44444238941 checks the Streamlit-to-same-DB client behavior; this is **not** proof of actual Streamlit Cloud access.

## Requirements before real Streamlit Cloud execution
1. Deploy an independently named **private/gated diagnostic app** from branch `feature/impl22-streamlit-isolated-turso-proof-20261119`, entrypoint `streamlit_turso_cross_environment_proof_impl22.py`. Do not replace the existing production app.
2. In that diagnostic app only, set Streamlit app secrets `KYOTO_LAB_TURSO_DATABASE_URL`, `KYOTO_LAB_TURSO_AUTH_TOKEN`, `KYOTO_LAB_STREAMLIT_PROOF_PASSWORD` (random secret >=16 characters). These are **not** GitHub Actions Secrets and are never committed or pasted in chats. Test DB URL host must equal `kyoto-keiba-ai-test-papaneko-ai.aws-ap-northeast-1.turso.io`.
3. Open test-only app, authenticate and enter GitHub run ID `44443836669`. Click the READ-ONLY receipt verification button. Expected: `REMOTE_GITHUB_RECEIPT_OBSERVED` and `DONE`. Preserve screenshot with no secrets.
4. A *separate* live GH-held lease is required to test the ACTIVE_LEASE refusal path; the already completed run is not valid for this test. Design a coordinated explicit manual lab-only lease window first. Never infer a simultaneous cross-environment test from a previously completed record.
5. Verify persisted evidence and safe failure/expiry/fencing semantics before treating step 7 as complete.

## Constraints
- No changes to default main's production app, scheduled eight slots, production Turso, or existing Secrets.
- No JRA requests or betting. No unattended lab writes, no automatic retry on ambiguous mutations.
- The probe's optional write-button requires an exact separate opt-in and refuses to write if a live GH lease cannot first be observed.
- The actual cross-environment proof is not yet executed and the fixed 9/10 (90%) readiness remains unchanged.
- Short-lived Turso test token issued November 19 expires approximately November 26, 2026, so failed/expired credentials must never be silently treated as a concurrency failure.

## Streamlit Community Cloud UI setup (distinct from production app)
- Go to https://share.streamlit.io/ and choose **Create app** -> **Yup, I have an app**.
- Repository: `papaneko-ai/kyoto-keiba-ai`.
- Branch: `feature/impl22-streamlit-isolated-turso-proof-20261119`.
- Main file path: `streamlit_turso_cross_environment_proof_impl22.py`.
- Choose a distinct diagnostic app URL. **Never change the production app's GitHub branch, file path, domain or settings.**
- In **Advanced settings** enter *diagnostic-app-only* secrets in TOML (actual values are supplied by the user only within the Streamlit settings):
  ```toml
  KYOTO_LAB_TURSO_DATABASE_URL = "libsql://kyoto-keiba-ai-test-papaneko-ai.aws-ap-northeast-1.turso.io"
  KYOTO_LAB_TURSO_AUTH_TOKEN = "<test-only-token, never publish>"
  KYOTO_LAB_STREAMLIT_PROOF_PASSWORD = "<unique randomly generated secret >=16 chars>"
  ```
- Do not copy placeholders literally. The 7-day token is the dedicated test token, never the production token. Do not put its value into the repository, PR, issues, logs or chat.
- For safety, restrict app access where supported; the in-app password is an extra gate, **not a guarantee of private deployment**.
- On first launch, check that the app requests a diagnostic password; authentication alone does not prove database access. Then use run ID `44443836669` for READ-ONLY verification, with no lab write.
- Save only a redacted screenshot showing the result. If credentials are missing, stop; do not modify the existing production Streamlit app.
