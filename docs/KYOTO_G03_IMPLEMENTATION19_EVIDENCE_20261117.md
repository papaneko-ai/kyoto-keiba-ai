# G03 Kyoto 1R-12R status — 2026-11-17

Baseline is main 3d057b8fe69da53e4e4b6acbc718154274157199. Previous migration ZIP was NOT applied over main.

## Implemented
- diagnostics/kyoto_g03_all_races.py: discover same-day racecard links solely from a saved official meeting HTML, require unique 1R-12R URLs, parse and preserve each raw racecard, extract horse number/name and profile navigation, validate unique contiguous numbers and unique explicitly observed start time, preserve URL/SHA256/UTC and machine-readable per-race partial-failure receipts.
- tests/test_kyoto_g03_all_races.py: nine synthetic/offline scenarios.
- .github/workflows/kyoto-g03-all-races-offline.yml: workflow run and evidence artifact.

## Executed evidence
- Initial run 44017730398 failed: Python non-ASCII bytes literal in test fixture.
- Fixed in 333578d4ce7ddd1b2371696e83f350b63f6d085b.
- Successful Run 44017787672, 9 tests passed, Artifact 14299337333.
- G03 12-race real-source verification: NOT ACHIEVED. This CI is deliberately synthetic and makes no JRA HTTP calls.

## Remaining before G03 PASS
1. Wire 12-race collector into the verified production capture implementation (existing weekend workflow currently uses a pinned older collector and R12-only observation).
2. Validate parser against actual saved JRA Kyoto racecard originals; adjust observed DOM differences without lowering evidence quality.
3. Validate authoritative scheduled start time and individual runner coverage against original per race, no invented permanent horse IDs.
4. Re-test integrated source capture and AES-GCM sealed original artifacts in GitHub Actions, with zero-HTTP preflight and partial-failure provenance.
5. Only after actual 12-race source provenance and full runner match, update the fixed 12-gate counter from 2/12 to 3/12.

No modifications to old-app design, market prices, virtual purchases, or existing fixed main backup guards.
