# Impl25 production capture pin release evidence (2026-11-19 JST)

## Scope and predecessor
- Previous pinned collector: `ba6b62bdbb25abf5605ea3b2b2ecb7f288b1d320`
- Candidate pinned collector: `139cba807761f7f74d5c44a44f06d5070fd3f47b`, immutable release branch `release/impl25-pinned-partial-g03-g04-g05-20261119`
- Exact comparison shows six changed files only: new subset proof verifier and tests, minimal G04/G05/PC entrypoint changes, and CI workflow. G06, lease/Turso, AES-GCM, SP and observer/network code remain unchanged.
- GitHub Actions candidate offline tests: Run `44488405265` (30 cases) and Run `44488511691` (30 + 55 = 85 tests) SUCCESS. No JRA HTTP tests.
- 12R all-correct path retains strict `kyoto_g03_proof_verify.verify` and original G04/G05 reports; subset path does not certify full data or predictions.
- 11R valid + 1R failed tests: G04 saves 33/33 tested profiles and prior history (synthetic 3 horse/race); G05 retains conditions for 11 races; corrupted source, fake roster, post-start or wrong day are not promoted.
- Do not claim real live capture before Nov21/22 scheduled runs.
- Only modifications to production main are replacement of 6 occurrences of exact previous pin in the weekend observer workflow and its static test constant. The eight schedule slots and job flags, secrets, Turso and other work remain unchanged.

## Limits
This release fixes one cross-race blanket-blocking cause, not PC/SP all-12 guaranteed connectivity, independent training-source discovery, external cron exact timing, or data source access. The job timeout and JRA publication timing may constrain G04/G05 retrieval even if the source code supports them. Preserve all originals and write missingness states. On regression, revert the main workflow pin to the prior commit.
