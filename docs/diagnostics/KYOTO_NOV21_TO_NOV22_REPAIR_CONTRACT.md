# Kyoto Nov21/22 read-only source recovery contract

Validated immutable source SHA: `e2a48f8b58ae13c210eead22533ee107004a45cd`.

## Day21 (2026-11-21)
- Source-only independent PC/SP collection; evidence AES-GCM encrypted; no prediction or purchase authorization.
- An automatic workflow_run plus 21:00 JST scheduled backup gathers exact job/artifact metadata.
- It privately downloads each matching run's artifact, verifies ciphertext authentication, saved original SHA256/UTC, and whether both raw markets exist. It retains only sanitized classifications, never decrypted HTML.
- An absent run is classified as absent; a pre-HTTP configuration error is not called an unsuccessful JRA GET.

## Day22 (2026-11-22)
- Independently scheduled PC and SP collectors, even if Day21 did not run.
- SP uses six bounded real-link official navigation pages rather than Saturday's three; multiple genuine official links are explored in a controlled order, with no synthetic CNAME or guessed host.
- Extra SP navigation originals 4..6 are included in SHA/UTC verification and AES-GCM encrypted upload.
- A new source commit is permitted only after matching offline preflight success; unseen code cannot be auto-promoted.
- Missing Secrets, GitHub API permission failure, and new official site structures may still require intervention. These are reported as action items, not silently treated as fixed.

## Passing and failure
An Actions job's success or encrypted artifact's presence does not prove authentic Kyoto racecards, valid quinella / bracket-quinella markets, or a pre-start prediction. These require source verification and real-world source bytes.

No unconditional claim of successful Day22 data retrieval is made. This contract provides pretested, independent fallback and an evidence-driven Day21 repair decision.

## 2026-11-16 additional preventive fixes
- GitHub Actions logs of 2026-11-14 Run 43547344697 and 2026-11-15 Run 43669118231 both show five pre-HTTP source-timestamp fixture errors, followed by absent safe-stop destination and no artifact. Historical timestamp/negative fixtures and safe-stop directory creation are covered in release tests.
- PC and SP remain distinct source collectors but execute sequentially to prevent simultaneous JRA HTTP from separate jobs. SP executes after PC failure by an explicit always condition, with a three-second network spacing step.
- PC and SP intermediate market navigation pages are now included in postflight SHA256/UTC rows. Decrypted market evidence is only counted as fully preserved when both originals have independent SHA256 and UTC records.
- Offline acceptance evidence: source commit e2a48f8b58ae13c210eead22533ee107004a45cd, run 43804330420 (code) and 43804425506 (scheduled workflow contract), both successful. Live source remains unverified.

## Final weekend race-identity prevention
PC and SP both target exact observed Kyoto 12R. Source evidence stores the explicitly *local* KYOTO:date:12 key and postflight rejects conflicting observed race number. Same-day test isolation, fixed collector e2a48f8b58ae13c210eead22533ee107004a45cd, source preflight 43805494867, backup run 43805649211.

## Nov16 recovery anti-blocker change
The prior blanket "any earlier same-day run" veto is removed. A first run's status or JRA HTTP attempt never proves both official markets were actually saved; suppressing the backup on this basis is incorrect. Each day now has one primary and one backup schedule; GitHub date-based concurrency serializes runs, original JRA URLs remain observed-only and paced, and source crypto/UTC evidence remains mandatory. An explicit operator rerun is no longer refused solely for attempt>1. The test-only GitHub schedule event still needs a recorded live scheduler trigger to be considered proven. Dev offline source SHA: e2a48f8b58ae13c210eead22533ee107004a45cd, preflight 43809830663.
