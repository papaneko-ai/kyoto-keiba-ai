# 2026-11-06: Offline source reconciliation / no duplicate acquisition

## Input evidence
- Archived official JRA post-race results HTML, 2026-10-31 Kyoto 1R-12R, GitHub Actions Artifact 13393704408.
- Archived official one-horse profile HTML for マルモリマイベスト from the same Artifact. Both files were downloaded earlier; no further network requests.
- Existing `diagnostics/parse_jra_result_roster.py` and `diagnostics/jra_prior_form_offline.py`, reused rather than replaced.

## Executed locally against real saved HTML
- 12 result tables; 154 result rows; 154 horse-profile links.
- One profile result-link ↔ profile-title match: マルモリマイベスト, Kyoto race 1, horse no. 5, frame 3.
- That horse's six displayed history rows: five earlier dated rows retained, same-day Oct 31 winner row excluded.
- Nine local offline regression tests passed, including missing/false evidence, wrong race, mismatched name and repeatability.

## Limitations
- This verifies a **single name-to-profile linkage**, not 154 profiles, not a JRA permanent horse ID, not independent pre-race racecards, and not an as-of pre-race snapshot.
- The official results hyperlink's `CNAME` is a navigation token; do not infer the permanent ID from it.
- Pre-race snapshot, field-size independent audit, and stable-ID crosswalk remain blocked pending authorized source evidence.
- Do not use post-race results/odds as pre-race inputs; no prediction is certified.
- No production main/app.py or Turso access, no new JRA scraping, no model training and no live scheduler activation.

## Next
Inspect available pre-race sources and their terms, identify verifiable racecard row structure and permanent horse IDs, build one-to-many reconciliation with count/cancelled-runner checks, then wire timestamp/provenance gates. Keep these separate from model training.
