# JRA horse-profile history verification — 2026-11-06

Input: GitHub Actions artifact 13393704408 previously captured JRA real HTML file `jra_feature_discovery/jra_one_horse_history.html` for マルモリマイベスト (not committed to public repository).

**Local real-HTML result:** 6 history rows, 5 strictly earlier dated rows for hypothetical cutoff prior to 2026-10-31 Kyoto 1R, 1 same-day 2026-10-31 result excluded. Earlier dates: 2026-10-18, 2026-09-05, 2026-08-15, 2026-07-11, 2026-07-04. Parse errors 0. Offline test suite: 13 tests passed, including one using recovered real JRA HTML.

The parser records source SHA256 and timestamps, checks JRA hostname and 14-column schema, matches horse name, excludes same-day/future runs, calculates field-size-adjusted placing percentile, and rejects incomplete fields. **Not proof of an actual pre-race snapshot**: archived profile fetched after the target race. Do not backfill original predictions; profile lifetime summary stats cannot be used. `jra_horse_id_verified=false`, `prediction_ready=false` always. JRA navigation CNAME is not a validated permanent horse ID.

Next: validate the pre-race racecard source and full-roster counts independently; normalize official IDs; acquire explicitly time-proven pre-race input only under approved collection conditions. Do not alter `main/app.py` or production Turso.

The companion complete test scripts and local test log are in the separately delivered project ZIP. CI has not yet independently verified these new code files.
