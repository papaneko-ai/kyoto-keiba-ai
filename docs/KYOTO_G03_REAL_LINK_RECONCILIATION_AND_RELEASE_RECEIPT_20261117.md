# Kyoto AI implementation19 G03 receipt — 2026-11-17

## Source baseline and release refs
- Original migration baseline main: 3d057b8fe69da53e4e4b6acbc718154274157199; no old ZIP overwrite.
- Development live-source-only collector pinned for 2026-11-21/22:
  e3d93491ff4da35176107c58e43f95a8efa28b01
- Main production CI acceptance after re-pin: Run 44024756678, SUCCESS,
  code HEAD c6748c856790a3ea11f5f25b80201e5ec6c7ebf3.
- G03 integrated development CI: Run 44024591481, SUCCESS,
  20+59+42+15=136 tests at c4ea746d344a6114d913b794f30b3114b96ee9d2.
  This test commit differs from pinned collector only by later test files.
- Source-first FMEA preflight: Run 44024341610 SUCCESS at the pinned source commit.

## Critical root cause found and repaired
The 2026-11-06 saved real official navigation discovery proved that JRA Kyoto
2026-11-07 race-selector anchors may have EMPTY human-visible labels, yet
contain real race CNAME hrefs, one each for 1R-12R:
pw01dde01082026050101... through pw01dde01082026050112...
(the actual suffix/checksum is always observed, never guessed).
G03 previously required a nonempty label, so it would miss ALL 12 real links.
The collector now parses the exact observed PC Kyoto /JRADB/accessD.html
CNAME schema, independently binds venue=08, 2026 season, race 01..12
and YYYYMMDD, rejects conflicting labels and duplicate URLs, and preserves
origin/redirect guards. Observer's prior 12R selection now accepts the same
official observed empty-label anchors; historical mocked tests remain separate.

## Historic actual data reuse
docs/diagnostics/JRA_KYOTO_FULL_DAY_ACCEPTANCE_20261106.json:
real 2026-11-07 12R structured snapshots, 148 runners, 396 prior dates,
counts = [9,15,13,15,8,11,11,9,10,14,16,17].
Independent G03 regression at Run 44024591481 reconciles all 12 existing
structured snapshots, horse numbers, frames, SHA fields and source link samples.
**Original racecard HTML BYTES were not independently revalidated in that
historical acceptance** (html_bytes_independently_verified_by_ci=false).
An archived GitHub artifact 13482994623 was separately recovered and contains
86 real HTML originals for individual horse profiles, NOT 12 raw racecards;
therefore it cannot be repurposed as 12R racecard-byte proof.

## Strict fixed progress — NO UNJUSTIFIED PASS
- 12 fixed gates: previous 2/12 (16.7%); current 2/12 (16.7%); delta 0.
- 9 preliminary experiments: previous 2/9 (22.2%); current 2/9 (22.2%); delta 0.
- G03: integrated implementation + historic real-link/structured-snapshot
  regressions PASS, **Nov21/22 real JRA all-12R source capture NOT VERIFIED**.
- G08: external actual timed trigger NOT independently VERIFIED.
- Production forecast and virtual settlement remain separate downstream gates.
- This receipt is evidence of source-only readiness, NOT a model prediction,
  betting recommendation or authorization to release the 12-gate counter.

## Remaining criteria for G03 promotion to 3/12
Real upcoming Kyoto source observation must produce 12 distinct official
racecard HTML bytes, all observed official links, each race's 1..N runner
number/name/frame, exact day/race/venue, start time, source SHA256 and
captured-at-UTC, encryption and independently inspectable release receipt.
Classify COMPLETE/PARTIAL/FAILED/NOT_RUN separately. Keep every acquired
original even if one race fails. The Nov21 capture result must inform the
independently tested Nov22 repair (without invalidating historical source
or replaying succeeded races). No prospective proof is to be fabricated.
