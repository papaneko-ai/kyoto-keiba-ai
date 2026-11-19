# Implementation 22: isolated Turso manual test setup (2026-11-19)

## Rules
- Do not edit or replace existing `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN`, production Turso, Streamlit secrets, scheduled eight collection slots, or main.
- The two *new* GitHub Actions repository secrets are `KYOTO_LAB_TURSO_DATABASE_URL` and `KYOTO_LAB_TURSO_AUTH_TOKEN`. Set them only after confirming the Turso database is exactly `kyoto-keiba-ai-test` at host `kyoto-keiba-ai-test-papaneko-ai.aws-ap-northeast-1.turso.io`.
- Secrets values belong in GitHub Settings, NEVER in commits, issues, messages, chats or logs.
- The workflow requires an explicit manual dispatch with text `YES-ISOLATED-CLAIMS-ONLY`. It creates only `__kyoto_ai_weekend_claims_isolated_lab_v1` and synthetic claims. It does not touch JRA, place bets or alter production tables.
- The workflow currently exists on PR #4 branch, NOT default `main`; do not assume it is executable from the Actions UI until a separate reviewed default-branch placement is approved.
- This two-GitHub-runner test does NOT certify GitHub-Actions-vs-Streamlit cross-environment execution. Step 7 / 10-of-10 is not completed from this test alone.

## Human-only setting steps
1. Sign in to Turso and locate the database `kyoto-keiba-ai-test`. Compare the displayed host name exactly; stop if different. Obtain a token scoped to that test database.
2. GitHub repository -> Settings -> Secrets and variables -> Actions -> New repository secret.
3. Add `KYOTO_LAB_TURSO_DATABASE_URL` with the **test** database URL from Turso (libsql:// or https:// expected host; no production URL). Do not modify the older `TURSO_DATABASE_URL`.
4. Add `KYOTO_LAB_TURSO_AUTH_TOKEN` with the **test** DB token. Do not modify `TURSO_AUTH_TOKEN`.
5. Report only that the two *names* appear in GitHub's secrets list; never disclose values.

## Review and acceptance
- Review PR #4 before any default-branch deployment. Changes are limited to lab-proof workflow and tests/diagnostics, not weekend production schedules.
- Explicit authorization for the synthetic test DB write and separate review of workflow placement are required.
- Collect actual job status + logs (redacted) + artifact and ensure results are not SKIP; then test remote competition, expired lease/fence, failure-retry, and separate GitHub/Streamlit behavior if possible.
- Preserve the fixed status 9/10 until all criteria and evidence are satisfied.
