# JRA release-time gates / 2026-11-06

Official JRA source: https://www.jra.go.jp/faq/pop02/2_2.html
Normal meetings publish unnumbered runners after Thursday 16:00 JST and numbered draws after the preceding day's 10:00 JST. Exceptional G1, other graded races and irregular meetings require officially evidenced overrides.

Reuses the locked docs/OPERATIONS_SCHEDULE_EVENT_TRIGGERS_20261105.md; does not replace it. The new offline diagnostic module diagnostics/jra_release_window.py distinguishes ENTRIES_UNNUMBERED vs DRAW_NUMBERED, handles JST/UTC and special-race exceptions, and **never certifies a source merely because the publication time has passed**. A real official HTML capture with byte hash, timestamp, cancellation and full-runner checks remains mandatory.

Local tests: 15/15 passed against an equivalent locally run module and test fixture. GitHub CI of committed module is not verified.

The previously committed one-shot JRA racecard GitHub workflow trigger is present, but its new run ID, success log and HTML Artifact cannot be retrieved via the currently available GitHub connector. Therefore **capture outcome is NOT CONFIRMED**. Do not retrigger bulk fetching or claim that pre-race originals have been recovered. Public main/app.py and Turso remain untouched.
