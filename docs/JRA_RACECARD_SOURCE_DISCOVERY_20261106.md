# JRA official race-specific entry page discovery — 2026-11-06

Recovered historical GitHub Actions Artifact 13393704408 yielded 12 post-race results/154 rows; the saved entries.html is an official meeting-selection page and **not** a runner list.

New read-only research found JRA historical **individual** racecards for 2026-10-31 Kyoto R1, R6 and R12:
- R1: https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0108202604100120261031%2F52
- R6: https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0108202604100620261031%2FDB
- R12: https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0108202604101220261031%2F59

JRA's indexed R1 entry shows horse numbers 1 and 2 as スリーオブスペイズ (UI foreign-bred badge) and ゴールドアーク, both frame 1. These two agree with the archived official JRA 1R results. **Only those two rows have been compared; no claim of complete 16-runner racecard reconciliation.**

These official URLs were discovered via current web search. Their current contents, even for a historical race, are NOT contemporaneous pre-race snapshots. Search crawl timestamps are not valid fetched_at_utc for old predictions. In particular, odds and body weight displayed now cannot be backdated.

New code diagnostics/jra_racecard_bridge.py records three URL discoveries, checks origin/endpoint, preserves separate UI badges, performs bounded row-level comparison and prohibits training certification. Tests/test_jra_racecard_bridge.py exercises the gates with synthetic data. Local test suite passed (10 tests, executable ZIP contains additional independent 11-test version).

Next: get an actually captured official race-specific HTML source with source bytes, fetch timestamp, hash, field complete and independently verify all starters, scratches, stable horse IDs, then pre-race cutoff. Do not automatically download bulk data before source terms are reviewed.

main/app.py and production Turso unchanged. No live scheduled collector activated.
