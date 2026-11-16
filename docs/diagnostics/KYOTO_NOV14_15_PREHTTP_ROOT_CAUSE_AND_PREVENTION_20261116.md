# November 14/15 acquisition failure root causes and November 21/22 regression closure

## Original GitHub evidence
- 2026-11-14 Actions Run 43547344697, job 132301624220: pre-HTTP offline regression failed with five `mandatory_original_capture_timestamp_missing` errors. Subsequent attempted safe-stop save failed `FileNotFoundError: nov14_unattended_evidence/safe_stop.json` and upload-artifact found no files.
- 2026-11-15 Actions Run 43669118231, job 132674992095: the same five pre-HTTP timestamp fixture failures, then `FileNotFoundError: nov15_unattended_evidence/safe_stop.json`, then no artifact. No credible evidence of actual official GET exists for either run.
- This is not a novel JRA HTML schema defect. It was an avoidable deterministic pre-HTTP fixture and save-directory defect.

## Current verifiable fixes
1. Offline fixtures now require and supply actual saved original UTC capture timestamps; a missing/non-UTC receipt is independently rejected. The unchanged historical regressions execute on both weekend source paths.
2. The safe-stop implementation creates its own output directory. Failure to begin a capture leaves an explicit no-HTTP artifact; crash-partial originals are sealed as unauthenticated evidence.
3. Both lanes perform postflight, sealing and Artifact upload under `if: always()`. AES-GCM retains raw bytes without uploading plaintext.
4. PC/SP jobs are network-serialized; SP runs even when PC fails; this is a failover instead of competing HTTP requests.
5. SP Sunday probes at most six observed navigation pages, with encrypted originals 1..6. Every page and navigational odds intermediate is compared to its saved SHA/UTC.
6. The 21st-run handoff downloads and decrypts the actual official-source artifacts, independently checks hashes and timestamps and presents next-day repair or tested fallback, without treating existence of artifacts as a prediction success.
7. All production collector source code is bound to immutable SHA `980365257e2bbe4b5b44d63f708a6ce761cf1ad5`. Source-level preflight 43804330420 and workflow-level preflight 43804425506 both passed with zero JRA HTTP.

## Remaining live-only conditions
A passing simulated capture proves only the configured workflow and mock response handling. A 2026-11-21/22 live original cannot be certified before the actual scheduled execution. The official racecard/market presence, official start time and live SP menu structure are still unproved. Those facts are reported as not verified, not covered up by a green test count.

## Non-success criterion
Never label an offline PASS, uploaded Artifact, or a fetched raw menu as verified pre-start market odds, a funded bet, or an authenticated prediction.
